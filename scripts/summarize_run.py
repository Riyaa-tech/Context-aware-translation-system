"""Write a descriptive Markdown summary of a run (no quality metrics: those need human ratings).

Usage: python scripts/summarize_run.py <experiment_id>
Output: experiments/reports/<experiment_id>_summary.md
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(exp_id):
    d = ROOT / "experiments" / "runs" / exp_id
    m = json.loads((d / "manifest.json").read_text())
    P = {c: {r["example_id"]: r for r in map(json.loads, (d / "predictions" / f"{c}.jsonl").read_text(encoding="utf-8").splitlines())}
         for c in m["conditions"]}
    base = P["A"]
    cats = sorted({r["category"] for r in base.values()})
    L = [f"# Run summary: `{exp_id}`", "",
         f"- Status: **{m['status']}**; split: **{m['split']}**; reportable: **{m['reportable']}**",
         *(f"- NOTE: {n}" for n in m["notes"]),
         f"- Examples: {m['n_examples']}; directions: {', '.join(m['directions'])}",
         f"- Model: {m['run_info']['model'].get('model_id')} @ {m['run_info']['model'].get('resolved_revision')}",
         f"- Same example IDs in every condition: {m.get('consistency', {}).get('ok')}", "",
         "> Descriptive only. \"Output changed\" means the final translation differs from condition A; it says nothing",
         "> about whether meaning was preserved. That requires human ratings (strict SPR).", "",
         "## Per condition", "",
         "| Condition | Intervene | Abstain | Pass | Output changed vs A | Errors | Median module ms | Median translation ms/item |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c, recs in P.items():
        dc = Counter(r["controller_decision"] for r in recs.values())
        changed = sum(recs[i]["final_translation"] != base[i]["final_translation"] for i in recs)
        lat = m["conditions"][c].get("latency_ms") or {}
        L.append(f"| {c} | {dc['INTERVENE']} | {dc['ABSTAIN']} | {dc['PASS_THROUGH']} | {changed}/{len(recs)} | "
                 f"{m['conditions'][c]['errors']} | {lat.get('modules_median', 'n/a')} | {lat.get('translation_median', 'n/a')} |")
    L += ["", "## Output changed vs A, by category", "", "| Category | n | " + " | ".join(c for c in P if c != "A") + " |",
          "|---|---:|" + "---:|" * (len(P) - 1)]
    for cat in cats:
        ids = [i for i, r in base.items() if r["category"] == cat]
        cells = [f"{sum(P[c][i]['final_translation'] != base[i]['final_translation'] for i in ids)}" for c in P if c != "A"]
        L.append(f"| {cat} | {len(ids)} | " + " | ".join(cells) + " |")
    L += ["", "## Interventions on control items (possible over-intervention)", ""]
    controls = {"idiom_literal_control", "no_idiom_control", "sincere_control", "context_irrelevant_control",
                "context_missing_control", "context_independent_control", "no_ambiguity_control", "context_ambiguous_control"}
    found = False
    for c, recs in P.items():
        for i, r in recs.items():
            if r["category"] in controls and r["controller_decision"] == "INTERVENE":
                found = True
                L.append(f"- `{c}` {i} ({r['category']}): {r['original_sentence']} → NLLB input: {r['nllb_input']}")
    if not found:
        L.append("- None.")
    concat = P.get("C_concat")
    if concat:
        warn = sum(1 for r in concat.values() if r.get("translation_warnings"))
        L += ["", f"## Concat control", "", f"- Items with a sentence-alignment warning: {warn}/{sum(1 for r in concat.values() if r.get('concat_window'))} (items with context)"]
    out = ROOT / "experiments" / "reports" / f"{exp_id}_summary.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nsaved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1])
