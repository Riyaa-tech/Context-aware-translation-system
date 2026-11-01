"""Assemble all metrics for one experiment run.

Separate sections (never mixed):
  general_quality   BLEU / spBLEU / chrF++ on items that HAVE a reference (e.g. FLORES)
  controller        intervention coverage, abstention, control false-intervention rate
  detectors         idiom P/R/F1 and context state/sense accuracy (from gold labels)
  semantic          strict SPR from HUMAN ratings (unavailable until ratings exist)
  latency           per-condition module / translation latency from the run manifest
Metrics that cannot be computed are returned as {"available": False, "reason": ...}, never as 0.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.evaluation.overlap_metrics import paired_bootstrap, score_all
from app.evaluation.run_metrics import context_metrics_from_run, controller_metrics, idiom_metrics_from_run
from app.evaluation.spr import delta_spr, harmful_intervention_rate, spr_by, spr_summary
from app.evaluation.statistics import cohens_kappa
from app.experiments.runner import read_predictions, read_run

ORDER = {"not_preserved": 0, "partial": 1, "preserved": 2}
ADJUDICATOR = "adjudicator"


def unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def aggregate_rating(by_rater: dict[str, str]) -> tuple[str | None, str]:
    """Adjudicated rating if present; else the single rating; else agreement; else the most conservative."""
    if not by_rater:
        return None, "unrated"
    if ADJUDICATOR in by_rater:
        return by_rater[ADJUDICATOR], "adjudicated"
    vals = list(by_rater.values())
    if len(vals) == 1:
        return vals[0], "single_rater"
    if len(set(vals)) == 1:
        return vals[0], "agreement"
    return min(vals, key=ORDER.get), "conservative_minimum"


def evaluate_run(exp_id: str, store=None, batch_id: str | None = None, runs_dir=None,
                 bootstrap_samples: int = 1000) -> dict:
    kw = {"runs_dir": runs_dir} if runs_dir else {}
    m = read_run(exp_id, **kw)
    preds = {c: read_predictions(exp_id, c, **kw) for c, s in m["conditions"].items() if s["status"] == "complete"}
    if "A" not in preds:
        raise ValueError("baseline condition A is not complete")
    base = {r["example_id"]: r for r in preds["A"]}
    report = {
        "experiment_id": exp_id, "evaluated_at": datetime.now(timezone.utc).isoformat(), "split": m["split"],
        "reportable": m["reportable"], "notes": m["notes"], "n_examples": m["n_examples"], "directions": m["directions"],
        "conditions": {c: m["conditions"][c]["label"] for c in preds},
        "general_quality": _general_quality(preds, bootstrap_samples),
        "controller": {c: controller_metrics(recs, base) for c, recs in preds.items()},
        "detectors": {c: {"idiom": idiom_metrics_from_run(recs) or unavailable("no idiom gold labels or idiom module off"),
                          "context": context_metrics_from_run(recs) or unavailable("context module off or no gold labels")}
                      for c, recs in preds.items() if c != "A"},
        "latency": {c: m["conditions"][c].get("latency_ms") for c in preds},
        "semantic": _semantic(preds, store, batch_id) if store and batch_id else unavailable(
            "no human annotation batch given; strict SPR requires human ratings"),
    }
    return report


def _general_quality(preds: dict, n_boot: int) -> dict:
    out = {}
    for c, recs in preds.items():
        with_ref = [r for r in recs if r.get("reference_translation")]
        if not with_ref:
            out[c] = unavailable("no reference translations in this run")
            continue
        by_dir = defaultdict(list)
        for r in with_ref:
            by_dir[f"{r['source_lang']}-{r['target_lang']}"].append(r)
        out[c] = {"by_direction": {d: score_all([r["final_translation"] for r in rs], [r["reference_translation"] for r in rs])
                                   for d, rs in sorted(by_dir.items())},
                  "n_with_reference": len(with_ref), "n_total": len(recs),
                  "averaging": "none; per-direction scores only (paper III-B)"}
    # paired bootstrap vs A, per direction, chrF++ and spBLEU
    if "A" in out and out["A"].get("available", True):
        a_by = {r["example_id"]: r for r in preds["A"] if r.get("reference_translation")}
        for c, recs in preds.items():
            if c == "A" or not out[c].get("available", True):
                continue
            tests = {}
            by_dir = defaultdict(list)
            for r in recs:
                if r["example_id"] in a_by:
                    by_dir[f"{r['source_lang']}-{r['target_lang']}"].append(r)
            for d, rs in by_dir.items():
                refs = [r["reference_translation"] for r in rs]
                ha = [a_by[r["example_id"]]["final_translation"] for r in rs]
                hb = [r["final_translation"] for r in rs]
                tests[d] = {name: paired_bootstrap(name, ha, hb, refs, n_samples=n_boot) for name in ("chrfpp", "spbleu_flores200")}
            out[c]["paired_bootstrap_vs_A"] = tests
    return out


def _semantic(preds: dict, store, batch_id: str) -> dict:
    ratings = store.ratings_for(batch_id)  # {(example_id, translation): {rater: rating}}
    if not ratings:
        return unavailable(f"batch {batch_id} has no ratings yet")
    raters = sorted({r for v in ratings.values() for r in v})
    per_cond, agg_counts = {}, defaultdict(int)
    rated: dict[str, dict[str, str]] = {}  # cond -> {example_id: rating}
    for c, recs in preds.items():
        rated[c] = {}
        for r in recs:
            val, how = aggregate_rating(ratings.get((r["example_id"], r["final_translation"]), {}))
            if val:
                rated[c][r["example_id"]] = val
                agg_counts[how] += 1
    full = {c: len(rated[c]) == len(preds[c]) for c in preds}
    base_recs = {r["example_id"]: r for r in preds["A"]}
    for c, recs in preds.items():
        items = [{"rating": rated[c][r["example_id"]], "category": r["category"],
                  "direction": f"{r['source_lang']}-{r['target_lang']}"} for r in recs if r["example_id"] in rated[c]]
        entry = {"n_rated": len(items), "n_total": len(recs), "fully_rated": full[c],
                 "overall": spr_summary([i["rating"] for i in items]),
                 "by_category": spr_by(items, "category"), "by_direction": spr_by(items, "direction")}
        if c != "A":
            common = [eid for eid in rated[c] if eid in rated["A"]]
            entry["delta_vs_A"] = {"overall": delta_spr([rated["A"][e] for e in common], [rated[c][e] for e in common])}
            cats = defaultdict(list)
            for e in common:
                cats[base_recs[e]["category"]].append(e)
            entry["delta_vs_A"]["by_category"] = {k: delta_spr([rated["A"][e] for e in v], [rated[c][e] for e in v])
                                                  for k, v in sorted(cats.items())}
            var = {r["example_id"]: r for r in recs}
            entry["harmful_intervention"] = harmful_intervention_rate([
                {"intervened": var[e]["controller_decision"] == "INTERVENE" or bool(var[e].get("concat_window")),
                 "baseline_rating": rated["A"][e], "variant_rating": rated[c][e]} for e in common])
        per_cond[c] = entry
    agreement = {}
    for i, r1 in enumerate(raters):
        for r2 in raters[i + 1:]:
            pairs = [(v[r1], v[r2]) for v in ratings.values() if r1 in v and r2 in v]
            if pairs:
                agreement[f"{r1}|{r2}"] = {"three_class": cohens_kappa([p[0] for p in pairs], [p[1] for p in pairs]),
                                           "strict_binary": cohens_kappa([p[0] == "preserved" for p in pairs],
                                                                         [p[1] == "preserved" for p in pairs])}
    return {"available": True, "batch_id": batch_id, "raters": raters,
            "single_rater_limitation": len([r for r in raters if r != ADJUDICATOR]) < 2,
            "aggregation_counts": dict(agg_counts),
            "aggregation_rule": "adjudicated > single rater > agreement > conservative minimum",
            "inter_rater_agreement": agreement or unavailable("fewer than two raters on shared items"),
            "per_condition": per_cond}
