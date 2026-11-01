"""Detector metrics (paper Section IV-J): precision, recall, F1, false-positive rate.

Kept separate from translation quality: a correct detection can still yield a bad translation.
Positive class = "figurative idiom that the controller should act on".
"""
from __future__ import annotations


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def idiom_detector_metrics(items: list[dict]) -> dict:
    """items: dicts with gold_idiom_id, gold_usage (figurative|literal|none),
    pred_figurative_ids (list), pred_any_ids (list), decision (PASS_THROUGH|INTERVENE|ABSTAIN)."""
    tp = fp = fn = 0
    neg_total = neg_fp = 0
    abstain = intervene = 0
    errors = []
    for it in items:
        gold_pos = it["gold_usage"] == "figurative"
        acted = it["pred_figurative_ids"]
        hit = gold_pos and it["gold_idiom_id"] in acted
        tp += int(hit)
        wrong = [i for i in acted if not (gold_pos and i == it["gold_idiom_id"])]
        fp += len(wrong)
        if gold_pos and not hit:
            fn += 1
            errors.append({"example_id": it["example_id"], "type": "false_negative", "decision": it["decision"]})
        if wrong:
            errors.append({"example_id": it["example_id"], "type": "false_positive", "ids": wrong})
        if not gold_pos:
            neg_total += 1
            neg_fp += int(bool(acted))
        abstain += it["decision"] == "ABSTAIN"
        intervene += it["decision"] == "INTERVENE"
    n = len(items)
    out = prf(tp, fp, fn)
    out.update({
        "n_items": n,
        "false_positive_rate": neg_fp / neg_total if neg_total else None,
        "intervention_coverage": intervene / n if n else None,
        "abstention_rate": abstain / n if n else None,
        "errors": errors,
    })
    return out
