"""Strict Semantic Preservation Rate (paper Section IV-J).

  SPR (%) = meaning-preserved / evaluated x 100     (only "preserved" counts as success)
Overall SPR is pooled from counts (never an average of category rates). The partial-preservation
rate is reported separately. ΔSPR is in absolute percentage points; Δrel is labelled as relative.
"""
from __future__ import annotations

from collections import defaultdict

from app.evaluation.statistics import bootstrap_ci_proportion, mcnemar_exact, paired_bootstrap_delta

RATINGS = ("preserved", "partial", "not_preserved")


def spr_summary(ratings: list[str], seed: int = 12345) -> dict:
    bad = [r for r in ratings if r not in RATINGS]
    if bad:
        raise ValueError(f"invalid ratings {set(bad)}")
    n = len(ratings)
    if n == 0:
        return {"n": 0, "spr": None, "partial_rate": None, "not_preserved_rate": None, "spr_ci95": None}
    succ = [1 if r == "preserved" else 0 for r in ratings]
    ci = bootstrap_ci_proportion(succ, seed=seed)
    return {
        "n": n,
        "preserved": sum(succ),
        "partial": ratings.count("partial"),
        "not_preserved": ratings.count("not_preserved"),
        "spr": round(100 * sum(succ) / n, 2),
        "partial_rate": round(100 * ratings.count("partial") / n, 2),
        "not_preserved_rate": round(100 * ratings.count("not_preserved") / n, 2),
        "spr_ci95": [round(100 * ci["ci95"][0], 2), round(100 * ci["ci95"][1], 2)],
    }


def spr_by(items: list[dict], key: str) -> dict:
    """items: [{'rating':..., key: group}] -> {group: spr_summary}"""
    groups = defaultdict(list)
    for it in items:
        groups[it[key]].append(it["rating"])
    return {g: spr_summary(r) for g, r in sorted(groups.items())}


def delta_spr(baseline: list[str], variant: list[str]) -> dict:
    """Paired comparison on the same items (same order)."""
    if len(baseline) != len(variant):
        raise ValueError("baseline and variant must be rated on the same items")
    a = [1 if r == "preserved" else 0 for r in baseline]
    b = [1 if r == "preserved" else 0 for r in variant]
    n = len(a)
    if n == 0:
        return {"n": 0, "delta_pp": None}
    spr_a, spr_b = 100 * sum(a) / n, 100 * sum(b) / n
    boot = paired_bootstrap_delta(a, b)
    return {
        "n": n,
        "spr_baseline": round(spr_a, 2),
        "spr_variant": round(spr_b, 2),
        "delta_pp": round(spr_b - spr_a, 2),
        "delta_pp_ci95": [round(100 * boot["ci95"][0], 2), round(100 * boot["ci95"][1], 2)],
        "delta_relative_pct": round(100 * (spr_b - spr_a) / spr_a, 2) if spr_a else None,
        "mcnemar": mcnemar_exact(a, b),
    }


def harmful_intervention_rate(pairs: list[dict]) -> dict:
    """pairs: [{'intervened': bool, 'baseline_rating': str, 'variant_rating': str}].
    Paper IV-J: share of ACTIVATIONS that turn a baseline output rated 'preserved' into one that is not."""
    acts = [p for p in pairs if p["intervened"]]
    harmful = [p for p in acts if p["baseline_rating"] == "preserved" and p["variant_rating"] != "preserved"]
    helpful = [p for p in acts if p["baseline_rating"] != "preserved" and p["variant_rating"] == "preserved"]
    n = len(acts)
    return {"activations": n, "harmful": len(harmful), "helpful": len(helpful),
            "harmful_intervention_rate": round(100 * len(harmful) / n, 2) if n else None,
            "helpful_intervention_rate": round(100 * len(helpful) / n, 2) if n else None}
