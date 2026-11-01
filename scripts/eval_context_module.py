"""Score the context module on a labelled JSONL split (no translation model needed).

Reports state accuracy, sense accuracy on items with a gold sense, a state confusion table,
and controller decisions. Writes a timestamped file to experiments/metrics/.
Usage: python scripts/eval_context_module.py [dataset.jsonl]
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.controller.semantic_controller import SemanticController  # noqa: E402
from app.modules.context_selector import ContextSelector  # noqa: E402
from app.modules.sense_inventory import load_inventory  # noqa: E402


def main(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    sel, ctrl = ContextSelector(), SemanticController()
    items, confusion = [], Counter()
    for r in rows:
        a = sel.analyze(r["source_text"], r["source_language"], r["context"])
        out = ctrl.decide([], a)
        pred_sense = next((w.resolved_sense for w in a.words if w.resolved_sense), None)
        items.append({"example_id": r["example_id"], "category": r["category"], "gold_state": r["gold_context_state"],
                      "pred_state": a.state, "gold_sense": r["gold_sense"], "pred_sense": pred_sense,
                      "decision": out.decision, "selected_context": a.selected_context})
        confusion[(r["gold_context_state"], a.state)] += 1
    n = len(items)
    state_ok = sum(i["gold_state"] == i["pred_state"] for i in items)
    with_sense = [i for i in items if i["gold_sense"]]
    sense_ok = sum(i["gold_sense"] == i["pred_sense"] for i in with_sense)
    # false intervention = rewrite on an item whose gold state is not RELEVANT_CONTEXT_SELECTED
    neg = [i for i in items if i["gold_state"] != "RELEVANT_CONTEXT_SELECTED"]
    false_int = sum(i["decision"] == "INTERVENE" for i in neg)
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(Path(path).relative_to(ROOT)), "n_items": n,
        "inventory_version": load_inventory()[0].get("inventory_version"),
        "context_config": sel.config.as_dict(),
        "state_accuracy": state_ok / n, "sense_accuracy": (sense_ok / len(with_sense)) if with_sense else None,
        "n_with_gold_sense": len(with_sense),
        "false_intervention_rate": false_int / len(neg) if neg else None,
        "decision_counts": dict(Counter(i["decision"] for i in items)),
        "confusion": [{"gold": g, "pred": p, "count": c} for (g, p), c in sorted(confusion.items())],
        "items": items,
    }
    out_dir = ROOT / "experiments" / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"context_module_{Path(path).stem}_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"n={n}  state_acc={report['state_accuracy']:.3f}  sense_acc={report['sense_accuracy']:.3f} "
          f"(n={len(with_sense)})  false_intervention_rate={report['false_intervention_rate']:.3f}  decisions={report['decision_counts']}")
    for i in items:
        if i["gold_state"] != i["pred_state"] or (i["gold_sense"] and i["gold_sense"] != i["pred_sense"]):
            row = next(r for r in rows if r["example_id"] == i["example_id"])
            print(f"  MISMATCH {i['example_id']}: gold={i['gold_state']}/{i['gold_sense']} pred={i['pred_state']}/{i['pred_sense']}"
                  f"  | {row['source_text']} ctx={row['context']} [{row.get('note', '')}]")
    print(f"saved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "experiments/datasets/challenge_set/context_dev.jsonl"))
