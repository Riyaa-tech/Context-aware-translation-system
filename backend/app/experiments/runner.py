"""Reproducible experiment runner with checkpoint/resume.

Layout (never overwritten):
  experiments/runs/<experiment_id>/
      config.json          frozen copy of the experiment config (+ its hash)
      manifest.json        status, dataset versions, run info, per-condition progress and timing
      predictions/<COND>.jsonl   one decision record per example, appended after every batch
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.experiments.conditions import get_condition
from app.experiments.datasets import DatasetError, load_challenge_files
from app.pipeline import SemanticPipeline
from app.translation.run_info import collect_run_info, hardware_info

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = ROOT / "experiments" / "runs"


class ExperimentError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    cfg["_config_file"] = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    return cfg


def config_hash(cfg: dict) -> str:
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:12]


def validate_config(cfg: dict) -> None:
    for key in ("name", "datasets", "conditions", "split", "seed"):
        if key not in cfg:
            raise ExperimentError(f"config missing '{key}'")
    for c in cfg["conditions"]:
        get_condition(c)  # raises ConditionError for unknown / unimplemented conditions
    if cfg["split"] == "test":
        rule = cfg.get("decision_rule_file")
        if not rule or not (ROOT / rule).exists():
            raise ExperimentError("test-split runs require 'decision_rule_file' pointing to a committed, pre-registered "
                                  "decision rule (paper Section VII-B)")
        doc = yaml.safe_load((ROOT / rule).read_text(encoding="utf-8")) or {}
        if doc.get("frozen") is not True or "TO_BE_SET" in json.dumps(doc):
            raise ExperimentError(f"{rule} is not frozen: fill in every TO_BE_SET value, set frozen: true and commit it "
                                  "BEFORE running on the test split")
    elif cfg["split"] != "dev":
        raise ExperimentError("split must be 'dev' or 'test'")
    if "A" not in cfg["conditions"]:
        raise ExperimentError("condition A (baseline) must be included so every variant has a paired baseline")


class ExperimentRunner:
    def __init__(self, engine, runs_dir: Path = RUNS_DIR, batch_size: int | None = None):
        self.engine = engine
        self.runs_dir = Path(runs_dir)
        self.batch_size = batch_size

    # ---------- setup ----------
    def create(self, cfg: dict) -> str:
        validate_config(cfg)
        ds = load_challenge_files(cfg["datasets"], ROOT)
        if ds.errors:
            raise DatasetError("dataset validation failed:\n" + "\n".join(ds.errors[:20]))
        rows = [r for r in ds.rows if r["split"] == cfg["split"]]
        if cfg.get("limit"):
            rows = rows[: int(cfg["limit"])]
        if not rows:
            raise ExperimentError(f"no rows with split '{cfg['split']}' in {cfg['datasets']}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        exp_id = f"{cfg['name']}_{stamp}_{config_hash(cfg)}"
        d = self.runs_dir / exp_id
        if d.exists():
            raise ExperimentError(f"{d} already exists; refusing to overwrite")
        (d / "predictions").mkdir(parents=True)
        (d / "config.json").write_text(json.dumps({**cfg, "_config_hash": config_hash(cfg)}, ensure_ascii=False, indent=1))
        manifest = {
            "experiment_id": exp_id,
            "name": cfg["name"],
            "description": cfg.get("description", ""),
            "created_at": _now(),
            "status": "created",
            "reportable": cfg["split"] == "test",
            "split": cfg["split"],
            "seed": cfg["seed"],
            "config_file": cfg["_config_file"],
            "config_hash": config_hash(cfg),
            "decision_rule_file": cfg.get("decision_rule_file"),
            "datasets": ds.files,
            "n_examples": len(rows),
            "example_ids": [r["example_id"] for r in rows],
            "directions": sorted({f"{r['source_language']}-{r['target_language']}" for r in rows}),
            "categories": _count(rows, "category"),
            "conditions": {c: {"status": "pending", "pipeline": get_condition(c).as_dict(),
                               "label": get_condition(c).condition_name, "done": 0, "errors": 0} for c in cfg["conditions"]},
            "run_info": collect_run_info(self.engine.info()),
            "notes": [] if cfg["split"] == "test" else ["DEV RUN - development data, not reportable as results"],
        }
        self._write_manifest(d, manifest)
        return exp_id

    # ---------- execution ----------
    def run(self, exp_id: str, stop_after_batches: int | None = None) -> dict:
        """Run (or resume) all conditions. `stop_after_batches` is for tests of interruption."""
        d = self.runs_dir / exp_id
        manifest = self._read_manifest(d)
        cfg = json.loads((d / "config.json").read_text())
        ds = load_challenge_files(cfg["datasets"], ROOT)
        current = {f["path"]: f["sha256"] for f in ds.files}
        changed = [f["path"] for f in manifest["datasets"] if current.get(f["path"]) != f["sha256"]]
        if changed:
            raise ExperimentError(f"dataset files changed since the run was created: {changed}; start a new run")
        by_id = {r["example_id"]: r for r in ds.rows}
        rows = [by_id[i] for i in manifest["example_ids"]]
        self.engine.load()
        manifest["status"] = "running"
        if manifest.get("started_at"):
            manifest.setdefault("resumed_at", []).append(_now())
        else:
            manifest["started_at"] = _now()
        manifest["run_info"]["model"] = self.engine.info()
        self._write_manifest(d, manifest)
        bs = self.batch_size or cfg.get("batch_size") or 8
        batches_done = 0
        try:
            for cond in cfg["conditions"]:
                cstate = manifest["conditions"][cond]
                if cstate["status"] == "complete":
                    continue
                pred_path = d / "predictions" / f"{cond}.jsonl"
                removed = _repair(pred_path)
                if removed:
                    cstate.setdefault("repaired_lines", 0)
                    cstate["repaired_lines"] += removed
                done_ids = _done_ids(pred_path)
                todo = [r for r in rows if r["example_id"] not in done_ids]
                pipe = SemanticPipeline(self.engine, get_condition(cond))
                cstate["status"] = "running"
                cstate.setdefault("started_at", _now())
                t0 = time.perf_counter()
                for direction, group in _group_by_direction(todo).items():
                    for start in range(0, len(group), bs):
                        batch = group[start:start + bs]
                        recs = self._run_batch(pipe, batch, cond, manifest)
                        with open(pred_path, "a", encoding="utf-8") as f:
                            for rec in recs:
                                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            f.flush()
                        cstate["done"] = len(_done_ids(pred_path))
                        cstate["errors"] += sum(r["translation_status"] == "error" for r in recs)
                        cstate["wall_seconds"] = round(cstate.get("wall_seconds", 0) + time.perf_counter() - t0, 2)
                        t0 = time.perf_counter()
                        self._write_manifest(d, manifest)
                        batches_done += 1
                        if stop_after_batches is not None and batches_done >= stop_after_batches:
                            raise _Interrupted()
                cstate["status"] = "complete"
                cstate["finished_at"] = _now()
                cstate.update(_latency_summary(pred_path))
                self._write_manifest(d, manifest)
        except _Interrupted:
            manifest["status"] = "interrupted"
            self._write_manifest(d, manifest)
            return manifest
        except Exception as e:
            manifest["status"] = "failed"
            manifest["failure"] = f"{type(e).__name__}: {e}"
            self._write_manifest(d, manifest)
            raise
        manifest["consistency"] = self._consistency(d, manifest)
        manifest["status"] = "complete" if manifest["consistency"]["ok"] else "inconsistent"
        manifest["finished_at"] = _now()
        manifest["run_info"]["hardware_at_end"] = hardware_info()
        self._write_manifest(d, manifest)
        return manifest

    def _run_batch(self, pipe: SemanticPipeline, batch: list[dict], cond: str, manifest: dict) -> list[dict]:
        prepared = [pipe.prepare(r["source_text"], r["source_language"], r.get("context", [])) for r in batch]
        src, tgt = batch[0]["source_language"], batch[0]["target_language"]
        t0 = time.perf_counter()
        results = self.engine.translate_batch([p[0]["nllb_input"] for p in prepared], src, tgt)
        batch_ms = (time.perf_counter() - t0) * 1000
        out = []
        for r, (rec, ev), res in zip(batch, prepared, results):
            SemanticPipeline.finalize(rec, ev, res)
            module_ms = round(sum(e["duration_ms"] for e in ev if e["stage"] in ("idiom_detection", "context_analysis", "controller")), 3)
            rec.update({
                "experiment_id": manifest["experiment_id"], "condition_key": cond,
                "example_id": r["example_id"], "category": r["category"],
                "source_lang": src, "target_lang": tgt,
                "intended_meaning": r["intended_meaning"], "reference_translation": r.get("reference_translation"),
                "latency_ms": {"modules": module_ms, "translation_batch_avg": round(batch_ms / len(batch), 1)},
                "written_at": _now(),
            })
            for k in ("gold_idiom_id", "gold_usage", "gold_context_state", "gold_sense"):
                if k in r:
                    rec[k] = r[k]
            out.append(rec)
        return out

    def _consistency(self, d: Path, manifest: dict) -> dict:
        expected = set(manifest["example_ids"])
        report, ok = {}, True
        for cond in manifest["conditions"]:
            ids = [json.loads(l)["example_id"] for l in open(d / "predictions" / f"{cond}.jsonl", encoding="utf-8")]
            dup = len(ids) - len(set(ids))
            missing = sorted(expected - set(ids))
            report[cond] = {"n": len(ids), "duplicates": dup, "missing": missing[:20], "n_missing": len(missing)}
            ok = ok and dup == 0 and not missing
        return {"ok": ok, "same_example_ids_across_conditions": ok, "per_condition": report}

    # ---------- io ----------
    @staticmethod
    def _write_manifest(d: Path, m: dict) -> None:
        tmp = d / "manifest.json.tmp"
        tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1))
        tmp.replace(d / "manifest.json")  # atomic replace: a crash never leaves a half-written manifest

    @staticmethod
    def _read_manifest(d: Path) -> dict:
        if not (d / "manifest.json").exists():
            raise ExperimentError(f"no experiment at {d}")
        return json.loads((d / "manifest.json").read_text())


class _Interrupted(Exception):
    pass


def _done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ids.add(json.loads(line)["example_id"])
            except (json.JSONDecodeError, KeyError):
                pass  # a torn last line from a crash is ignored and that example is redone
    return ids


def _repair(path: Path) -> int:
    """Drop unparsable lines (e.g. a line torn by a crash) so later appends stay valid JSONL.
    Removed text is kept in <file>.torn.log for auditing; those examples are simply redone."""
    if not path.exists():
        return 0
    good, bad = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
            good.append(line)
        except json.JSONDecodeError:
            bad.append(line)
    if bad:
        with open(path.with_suffix(".torn.log"), "a", encoding="utf-8") as f:
            f.write("\n".join(bad) + "\n")
        path.write_text("".join(g + "\n" for g in good), encoding="utf-8")
    return len(bad)


def _group_by_direction(rows: list[dict]) -> dict[tuple, list[dict]]:
    g: dict[tuple, list[dict]] = {}
    for r in rows:
        g.setdefault((r["source_language"], r["target_language"]), []).append(r)
    return g


def _count(rows, key) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def _latency_summary(path: Path) -> dict:
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not recs:
        return {}
    mods = sorted(r["latency_ms"]["modules"] for r in recs)
    tr = sorted(r["latency_ms"]["translation_batch_avg"] for r in recs)
    med = lambda xs: xs[len(xs) // 2]
    return {"latency_ms": {"modules_median": med(mods), "modules_max": mods[-1],
                           "translation_median": med(tr), "translation_max": tr[-1]},
            "decision_counts": _count(recs, "controller_decision"),
            "status_counts": _count(recs, "translation_status")}


def list_runs(runs_dir: Path = RUNS_DIR) -> list[dict]:
    out = []
    for d in sorted(runs_dir.glob("*/manifest.json"), reverse=True):
        m = json.loads(d.read_text())
        out.append({k: m.get(k) for k in ("experiment_id", "name", "status", "split", "reportable", "created_at",
                                          "finished_at", "n_examples", "directions")}
                   | {"conditions": {c: v["status"] for c, v in m["conditions"].items()}})
    return out


def read_run(exp_id: str, runs_dir: Path = RUNS_DIR) -> dict:
    p = runs_dir / exp_id / "manifest.json"
    if not p.exists() or "/" in exp_id or ".." in exp_id:
        raise ExperimentError(f"experiment '{exp_id}' not found")
    return json.loads(p.read_text())


def read_predictions(exp_id: str, condition: str, runs_dir: Path = RUNS_DIR) -> list[dict]:
    read_run(exp_id, runs_dir)
    p = runs_dir / exp_id / "predictions" / f"{condition}.jsonl"
    if not p.exists():
        raise ExperimentError(f"no predictions for condition '{condition}'")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
