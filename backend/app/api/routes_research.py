"""Research metrics computed from stored runs (+ human ratings when available). Nothing is simulated."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_store
from app.evaluation.report import evaluate_run
from app.experiments.runner import ExperimentError, list_runs

router = APIRouter(prefix="/api/research", tags=["research"])


def _pick(exp_id: str | None) -> str:
    if exp_id:
        return exp_id
    done = [r for r in list_runs() if r["status"] == "complete"]
    if not done:
        raise HTTPException(404, "no completed experiment runs")
    return done[0]["experiment_id"]


_CACHE: dict = {}


def _cache_key(exp_id: str, batch_id: str | None, store) -> tuple:
    from app.experiments.runner import RUNS_DIR

    p = RUNS_DIR / exp_id / "manifest.json"
    stamp = p.stat().st_mtime if p.exists() else 0
    ann = store.export(batch_id) if batch_id else []
    return (exp_id, batch_id, stamp, len(ann), max((a["updated_at"] for a in ann), default=""))


@router.get("/metrics")
def metrics(experiment_id: str | None = None, batch_id: str | None = None, store=Depends(get_store)):
    """Computed from stored data; cached until the run or its annotations change."""
    try:
        exp = _pick(experiment_id)
        key = _cache_key(exp, batch_id, store)
        if key not in _CACHE:
            _CACHE.clear() if len(_CACHE) > 32 else None
            _CACHE[key] = evaluate_run(exp, store=store, batch_id=batch_id, bootstrap_samples=300)
        return _CACHE[key]
    except (ExperimentError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/ablation")
def ablation(experiment_id: str | None = None, batch_id: str | None = None, store=Depends(get_store)):
    """Compact table: one row per condition. Unavailable values are null with a reason, never 0."""
    rep = metrics(experiment_id, batch_id, store)
    sem = rep["semantic"]
    rows = []
    for c, label in rep["conditions"].items():
        gq = rep["general_quality"].get(c, {})
        s = sem["per_condition"].get(c) if sem.get("available") else None
        cats = (s or {}).get("by_category", {})
        rows.append({
            "condition": c, "label": label,
            "bleu_13a": _dir_scores(gq, "bleu_13a"), "spbleu_flores200": _dir_scores(gq, "spbleu_flores200"),
            "chrfpp": _dir_scores(gq, "chrfpp"),
            "spr_overall": s["overall"]["spr"] if s else None,
            "spr_idiom": cats.get("idiom", {}).get("spr"), "spr_sarcasm": cats.get("sarcasm", {}).get("spr"),
            "spr_context": cats.get("context", {}).get("spr"),
            "delta_spr_pp": (s or {}).get("delta_vs_A", {}).get("overall", {}).get("delta_pp"),
            "intervention_coverage": rep["controller"][c]["intervention_coverage"],
            "harmful_intervention_rate": (s or {}).get("harmful_intervention", {}).get("harmful_intervention_rate"),
            "latency_ms": rep["latency"].get(c),
        })
    return {"experiment_id": rep["experiment_id"], "reportable": rep["reportable"], "notes": rep["notes"],
            "semantic_available": sem.get("available", False), "semantic_reason": sem.get("reason"), "rows": rows}


def _dir_scores(gq: dict, name: str):
    if not gq or gq.get("available") is False:
        return None
    return {d: v[name]["score"] for d, v in gq["by_direction"].items()}


# ---------------- dashboard helpers ----------------
import json as _json  # noqa: E402
from collections import Counter as _Counter  # noqa: E402

from app.experiments.datasets import load_challenge_files  # noqa: E402
from app.experiments.runner import ROOT  # noqa: E402

REPORTS = ROOT / "experiments" / "reports"
CHALLENGE = ROOT / "experiments" / "datasets" / "challenge_set"


@router.get("/datasets")
def datasets():
    """Counts for every challenge-set file (templates excluded) and the FLORES files present locally."""
    files = sorted(p for p in CHALLENGE.glob("*.jsonl") if not p.name.startswith("TEMPLATE"))
    out = []
    for p in files:
        ds = load_challenge_files([p], ROOT)
        rows = ds.rows
        out.append({"file": ds.files[0]["path"], "sha256": ds.files[0]["sha256"][:12], "n": len(rows),
                    "by_split": dict(_Counter(r.get("split") for r in rows)),
                    "by_category": dict(_Counter(r.get("category") for r in rows)),
                    "by_direction": dict(_Counter(f"{r.get('source_language')}->{r.get('target_language')}" for r in rows)),
                    "provenance": sorted({r.get("provenance") for r in rows}), "errors": len(ds.errors)})
    flores = sorted(p.name for p in (ROOT / "experiments" / "datasets" / "flores").glob("*.jsonl"))
    return {"challenge_files": out, "flores_files": flores,
            "test_split_present": any(f["by_split"].get("test") for f in out)}


@router.get("/reports")
def reports():
    items = sorted(REPORTS.glob("*.md"), reverse=True) if REPORTS.exists() else []
    return {"reports": [{"name": p.name, "bytes": p.stat().st_size} for p in items]}


@router.get("/reports/{name}")
def report_file(name: str):
    from fastapi.responses import PlainTextResponse

    p = REPORTS / name
    if "/" in name or ".." in name or not name.endswith(".md") or not p.exists():
        raise HTTPException(404, "report not found")
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/errors")
def error_analysis(batch_id: str, store=Depends(get_store)):
    """Primary error categories from HUMAN annotations, per condition. Empty until people rate items."""
    rows = store.export(batch_id)
    if not rows:
        return {"available": False, "reason": "no human annotations in this batch yet", "by_condition": {}}
    by = {}
    for r in rows:
        for c in r["conditions"]:
            by.setdefault(c, _Counter())[r["primary_error"] or "unspecified"] += 1
    return {"available": True, "n_annotations": len(rows), "by_condition": {c: dict(v) for c, v in by.items()}}
