"""Exploratory DEV run with the REAL model: translate a dev JSONL under several conditions.
Output is for inspection only (no human ratings => no SPR). Never overwrites earlier runs.

Usage:
  python scripts/run_dev_explore.py --dataset experiments/datasets/challenge_set/idiom_dev_v2.jsonl \
      --conditions A,B_hint,B_paraphrase
  python scripts/run_dev_explore.py --dataset experiments/datasets/challenge_set/context_dev_v2.jsonl \
      --conditions A,C_selected,C_concat
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.deps import get_engine  # noqa: E402
from app.pipeline import PipelineConfig, SemanticPipeline  # noqa: E402
from app.translation.run_info import collect_run_info  # noqa: E402

CONDITIONS = {
    "A": PipelineConfig(idiom_enabled=False),
    "B_hint": PipelineConfig(idiom_mode="hint"),
    "B_paraphrase": PipelineConfig(idiom_mode="paraphrase"),
    "C_selected": PipelineConfig(idiom_enabled=False, context_mode="selected"),
    "C_concat": PipelineConfig(idiom_enabled=False, context_mode="concat"),
    "D_paraphrase_selected": PipelineConfig(idiom_mode="paraphrase", context_mode="selected"),
}


def run_condition(engine, cfg, rows):
    pipe = SemanticPipeline(engine, cfg)
    prepared = [pipe.prepare(r["source_text"], r["source_language"], r.get("context", [])) for r in rows]
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault((r["source_language"], r["target_language"]), []).append(i)
    results = [None] * len(rows)
    for (s, t), idx in groups.items():
        for i, res in zip(idx, engine.translate_batch([prepared[i][0]["nllb_input"] for i in idx], s, t)):
            results[i] = res
    out = []
    for r, (rec, ev), res in zip(rows, prepared, results):
        SemanticPipeline.finalize(rec, ev, res)
        rec.update({"example_id": r["example_id"], "source_lang": r["source_language"], "target_lang": r["target_language"]})
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--conditions", default="A,B_hint,B_paraphrase")
    args = ap.parse_args()
    names = args.conditions.split(",")
    unknown = [n for n in names if n not in CONDITIONS]
    if unknown:
        sys.exit(f"unknown conditions {unknown}; choose from {list(CONDITIONS)}")
    path = Path(args.dataset).resolve()
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    engine = get_engine()
    engine.load()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / "predictions" / f"dev_explore_{path.stem}_{stamp}"
    out_dir.mkdir(parents=True)
    t0 = time.perf_counter()
    for n in names:
        recs = run_condition(engine, CONDITIONS[n], rows)
        with open(out_dir / f"{recs[0]['condition']}.jsonl", "w", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{recs[0]['condition']}: done ({time.perf_counter() - t0:.0f}s elapsed)", flush=True)
    manifest = {"created": stamp, "kind": "exploratory dev run (not an experiment; no human ratings)",
                "dataset": str(path.relative_to(ROOT)), "n_items": len(rows),
                "conditions": {n: CONDITIONS[n].as_dict() for n in names},
                "run_info": collect_run_info(engine.info()), "wall_seconds": round(time.perf_counter() - t0, 1)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"saved -> {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
