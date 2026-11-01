"""Score the idiom detector + controller on a labelled JSONL split (no translation model needed).

Usage:  python scripts/eval_idiom_detector.py experiments/datasets/challenge_set/idiom_dev.jsonl
Writes a timestamped JSON file to experiments/metrics/ (never overwrites).
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.controller.semantic_controller import SemanticController  # noqa: E402
from app.evaluation.detector_metrics import idiom_detector_metrics  # noqa: E402
from app.modules.idiom_detector import IdiomDetector  # noqa: E402
from app.modules.idiom_lexicon import load_lexicon  # noqa: E402


def main(path: str):
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    det, ctrl = IdiomDetector(), SemanticController()
    items, by_lang = [], defaultdict(list)
    for r in rows:
        cands = det.detect(r["source_text"], r["source_language"], r.get("context", []))
        out = ctrl.decide(cands)
        it = {"example_id": r["example_id"], "gold_idiom_id": r.get("gold_idiom_id"), "gold_usage": r["gold_usage"],
              "pred_figurative_ids": [c.idiom_id for c in out.accepted_idioms],
              "pred_any_ids": [c.idiom_id for c in cands], "decision": out.decision,
              "usages": {c.idiom_id: [c.usage, c.usage_score] for c in cands}}
        items.append(it)
        by_lang[r["source_language"]].append(it)
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(Path(path).relative_to(ROOT)),
        "splits": sorted({r["split"] for r in rows}),
        "lexicon_version": load_lexicon()[0].get("lexicon_version"),
        "detector_config": det.config.as_dict(),
        "controller_config": ctrl.config.as_dict(),
        "overall": idiom_detector_metrics(items),
        "by_language": {k: {kk: vv for kk, vv in idiom_detector_metrics(v).items() if kk != "errors"} for k, v in by_lang.items()},
        "items": items,
    }
    out_dir = ROOT / "experiments" / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"idiom_detector_{Path(path).stem}_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    o = report["overall"]
    fmt = lambda x: "n/a" if x is None else f"{x:.3f}"
    print(f"n={o['n_items']}  P={fmt(o['precision'])}  R={fmt(o['recall'])}  F1={fmt(o['f1'])}  "
          f"FPR={fmt(o['false_positive_rate'])}  coverage={fmt(o['intervention_coverage'])}  abstain={fmt(o['abstention_rate'])}")
    for lang, m in report["by_language"].items():
        print(f"  {lang}: n={m['n_items']} P={fmt(m['precision'])} R={fmt(m['recall'])} F1={fmt(m['f1'])} FPR={fmt(m['false_positive_rate'])}")
    for e in o["errors"]:
        row = next(r for r in rows if r["example_id"] == e["example_id"])
        print(f"  {e['type']:15s} {e['example_id']}: {row['source_text']}  [{row.get('note', '')}]")
    print(f"saved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "experiments/datasets/challenge_set/idiom_dev.jsonl"))
