"""Exploratory DEV run: translate idiom dev items under A (baseline), B-hint and B-paraphrase
with the REAL model. Output is for inspection only (no human ratings => no SPR).

Usage: python scripts/run_idiom_dev_demo.py [dataset.jsonl]
"""
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
    "A_baseline": PipelineConfig(idiom_enabled=False),
    "B_idiom_hint": PipelineConfig(idiom_enabled=True, idiom_mode="hint"),
    "B_idiom_paraphrase": PipelineConfig(idiom_enabled=True, idiom_mode="paraphrase"),
}


def main(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    engine = get_engine()
    engine.load()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "experiments" / "predictions" / f"dev_idiom_explore_{stamp}"
    out_dir.mkdir(parents=True)
    t0 = time.perf_counter()
    for name, cfg in CONDITIONS.items():
        pipe = SemanticPipeline(engine, cfg)
        # Prepare all inputs, then translate in batches grouped by direction.
        prepared = [(r, *pipe.prepare(r["source_text"], r["source_language"], r.get("context", []))) for r in rows]
        groups = {}
        for i, (r, rec, _) in enumerate(prepared):
            groups.setdefault((r["source_language"], r["target_language"]), []).append(i)
        outputs = [None] * len(rows)
        for (s, t), idx in groups.items():
            inputs = [prepared[i][1]["modified_sentence"] or rows[i]["source_text"] for i in idx]
            for i, res in zip(idx, engine.translate_batch(inputs, s, t)):
                outputs[i] = res
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for (r, rec, _), res in zip(prepared, outputs):
                rec.update({"example_id": r["example_id"], "source_lang": r["source_language"],
                            "target_lang": r["target_language"], "nllb_input": res.source_text,
                            "final_translation": res.translation, "translation_status": res.status})
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{name}: done ({time.perf_counter() - t0:.0f}s elapsed)", flush=True)
    manifest = {"created": stamp, "kind": "exploratory dev run (not an experiment; no human ratings)",
                "dataset": str(Path(path).relative_to(ROOT)), "n_items": len(rows),
                "conditions": list(CONDITIONS), "run_info": collect_run_info(engine.info()),
                "wall_seconds": round(time.perf_counter() - t0, 1)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"saved -> {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "experiments/datasets/challenge_set/idiom_dev.jsonl"))
