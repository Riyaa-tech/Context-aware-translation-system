"""Compute all metrics for a run from stored predictions (+ human ratings if a batch is given).
No translation is re-run.

  python scripts/evaluate_run.py <experiment_id> [--batch <annotation_batch_id>] [--bootstrap 1000]

Writes experiments/metrics/<experiment_id>__eval_<UTC>.json and experiments/reports/<experiment_id>__eval_<UTC>.md
"""
import argparse
import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.annotation.store import DEFAULT_DB, AnnotationStore  # noqa: E402
from app.evaluation.report import evaluate_run  # noqa: E402

NA = "n/a"


def fmt(x, nd=2):
    return NA if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def markdown(rep: dict) -> str:
    L = [f"# Evaluation: `{rep['experiment_id']}`", "", f"- Split: **{rep['split']}**; reportable: **{rep['reportable']}**",
         *(f"- NOTE: {n}" for n in rep["notes"]), f"- Examples: {rep['n_examples']}; directions: {', '.join(rep['directions'])}", ""]
    L += ["## General quality (reference-based; per direction, no averaging)", ""]
    for c, g in rep["general_quality"].items():
        if g.get("available") is False:
            L.append(f"- `{c}`: unavailable ({g['reason']})")
            continue
        for d, s in g["by_direction"].items():
            L.append(f"- `{c}` {d} (n={s['chrfpp']['n']}): BLEU(13a) {fmt(s['bleu_13a']['score'])} · "
                     f"spBLEU(flores200) {fmt(s['spbleu_flores200']['score'])} · chrF++ {fmt(s['chrfpp']['score'])}")
        for d, t in g.get("paired_bootstrap_vs_A", {}).items():
            for name, r in t.items():
                L.append(f"  - vs A, {d}, {name}: Δ {fmt(r['delta'])} (95% CI {r['ci95']}; p(B≤A)={r['p_b_not_better']}; "
                         f"{r['n_samples']} bootstrap samples)")
    sig = next((s["chrfpp"]["signature"] for g in rep["general_quality"].values() if g.get("available", True)
                for s in g["by_direction"].values()), None)
    if sig:
        L += ["", "Signatures:"] + list({f"- `{s[k]['signature']}`" for g in rep["general_quality"].values()
                                          if g.get("available", True) for s in g["by_direction"].values() for k in s})
    L += ["", "## Controller", "", "| Condition | Coverage | Abstention | Control false-intervention | Output changed vs A |",
          "|---|---:|---:|---:|---:|"]
    for c, m in rep["controller"].items():
        L.append(f"| {c} | {fmt(m['intervention_coverage'], 3)} | {fmt(m['abstention_rate'], 3)} | "
                 f"{fmt(m['control_false_intervention_rate'], 3)} | {m['output_changed_vs_baseline']}/{m['n']} |")
    L += ["", "## Detectors (gold labels; development data is optimistic)", ""]
    for c, d in rep["detectors"].items():
        i, x = d["idiom"], d["context"]
        L.append(f"- `{c}` idiom: " + (f"P {fmt(i['precision'], 3)} R {fmt(i['recall'], 3)} F1 {fmt(i['f1'], 3)} (n={i['n_items']})"
                                        if i.get("available", True) else f"unavailable ({i['reason']})")
                 + " · context: " + (f"state acc {fmt(x['state_accuracy'], 3)}, sense acc {fmt(x['sense_accuracy'], 3)} (n={x['n']})"
                                      if x.get("available", True) else f"unavailable ({x['reason']})"))
    L += ["", "## Strict SPR (human ratings)", ""]
    s = rep["semantic"]
    if not s.get("available"):
        L.append(f"Unavailable: {s['reason']}")
    else:
        if s["single_rater_limitation"]:
            L.append("> LIMITATION: only one rater; no agreement statistic.")
        L += ["| Condition | Rated | SPR % (95% CI) | Partial % | ΔSPR pp vs A (95% CI) | McNemar p | Harmful-intervention % |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        for c, e in s["per_condition"].items():
            d = e.get("delta_vs_A", {}).get("overall", {})
            h = e.get("harmful_intervention", {})
            L.append(f"| {c} | {e['n_rated']}/{e['n_total']} | {fmt(e['overall']['spr'])} ({e['overall']['spr_ci95']}) | "
                     f"{fmt(e['overall']['partial_rate'])} | {fmt(d.get('delta_pp'))} ({d.get('delta_pp_ci95', NA)}) | "
                     f"{fmt(d.get('mcnemar', {}).get('p_value'), 4)} | {fmt(h.get('harmful_intervention_rate'))} |")
        L += ["", f"Aggregation: {s['aggregation_rule']}; counts {s['aggregation_counts']}",
              f"Inter-rater agreement: {json.dumps(s['inter_rater_agreement'], default=str)[:600]}"]
    L += ["", "## Latency (ms)", ""] + [f"- `{c}`: {v}" for c, v in rep["latency"].items()]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment_id")
    ap.add_argument("--batch")
    ap.add_argument("--bootstrap", type=int, default=1000)
    a = ap.parse_args()
    store = AnnotationStore(os.getenv("ANNOTATION_DB", str(DEFAULT_DB))) if a.batch else None
    rep = evaluate_run(a.experiment_id, store=store, batch_id=a.batch, bootstrap_samples=a.bootstrap)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (ROOT / "experiments" / "metrics").mkdir(parents=True, exist_ok=True)
    (ROOT / "experiments" / "reports").mkdir(parents=True, exist_ok=True)
    j = ROOT / "experiments" / "metrics" / f"{a.experiment_id}__eval_{stamp}.json"
    md = ROOT / "experiments" / "reports" / f"{a.experiment_id}__eval_{stamp}.md"
    j.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    text = markdown(rep)
    md.write_text(text, encoding="utf-8")
    print(text)
    print(f"saved -> {j.relative_to(ROOT)}\nsaved -> {md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
