"""Controller / detector metrics computed from stored run predictions and gold labels
(no human ratings needed). Kept separate from translation quality."""
from __future__ import annotations

from collections import Counter

from app.evaluation.detector_metrics import idiom_detector_metrics

CONTROL_CATEGORIES = {"idiom_literal_control", "no_idiom_control", "sincere_control", "context_irrelevant_control",
                      "context_missing_control", "context_independent_control", "no_ambiguity_control",
                      "context_ambiguous_control"}


def controller_metrics(recs: list[dict], baseline: dict[str, dict]) -> dict:
    n = len(recs)
    dec = Counter(r["controller_decision"] for r in recs)
    ctrl = [r for r in recs if r["category"] in CONTROL_CATEGORIES]
    changed = sum(r["final_translation"] != baseline[r["example_id"]]["final_translation"] for r in recs)
    ctrl_changed = sum(r["final_translation"] != baseline[r["example_id"]]["final_translation"] for r in ctrl)
    return {
        "n": n,
        "intervention_coverage": dec["INTERVENE"] / n if n else None,
        "abstention_rate": dec["ABSTAIN"] / n if n else None,
        "pass_through_rate": dec["PASS_THROUGH"] / n if n else None,
        "control_items": len(ctrl),
        "control_false_intervention_rate": (sum(r["controller_decision"] == "INTERVENE" for r in ctrl) / len(ctrl)) if ctrl else None,
        "output_changed_vs_baseline": changed,
        "control_output_changed_vs_baseline": ctrl_changed,
    }


def idiom_metrics_from_run(recs: list[dict]) -> dict | None:
    items = []
    for r in recs:
        if "gold_usage" not in r:
            continue
        acted = [s["item_id"] for s in r["span_decisions"] if s["module"] == "idiom" and s["action"] == "accept"]
        items.append({"example_id": r["example_id"], "gold_idiom_id": r.get("gold_idiom_id"), "gold_usage": r["gold_usage"],
                      "pred_figurative_ids": acted, "pred_any_ids": [], "decision": r["controller_decision"]})
    return idiom_detector_metrics(items) if items else None


def context_metrics_from_run(recs: list[dict]) -> dict | None:
    items = [r for r in recs if "gold_context_state" in r and r.get("context_state") is not None]
    if not items:
        return None
    state_ok = sum(r["gold_context_state"] == r["context_state"] for r in items)
    with_sense = [r for r in items if r.get("gold_sense")]
    pred_sense = lambda r: next((p["resolved_sense"] for p in r["module_predictions"].get("context", []) if p["resolved_sense"]), None)
    return {"n": len(items), "state_accuracy": state_ok / len(items),
            "sense_accuracy": (sum(r["gold_sense"] == pred_sense(r) for r in with_sense) / len(with_sense)) if with_sense else None,
            "n_with_gold_sense": len(with_sense)}
