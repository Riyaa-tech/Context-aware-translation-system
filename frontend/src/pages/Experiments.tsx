import { useState } from "react";
import { MetricBars, DecisionStack } from "../components/charts";
import { RunPicker } from "../components/RunPicker";
import { Card, Notice, Value, Spinner, ErrorBox } from "../components/ui";
import { fmt, ms, pct } from "../lib/format";
import { useApi } from "../lib/hooks";

interface AblationRow {
  condition: string; label: string; bleu_13a: Record<string, number> | null; spbleu_flores200: Record<string, number> | null;
  chrfpp: Record<string, number> | null; spr_overall: number | null; spr_idiom: number | null; spr_sarcasm: number | null;
  spr_context: number | null; delta_spr_pp: number | null; intervention_coverage: number | null;
  harmful_intervention_rate: number | null; latency_ms: { translation_median?: number; modules_median?: number } | null;
}
interface Ablation { experiment_id: string; reportable: boolean; notes: string[]; semantic_available: boolean; semantic_reason: string | null; rows: AblationRow[] }

const CONDITION_HELP: Record<string, string> = {
  A: "Plain NLLB-200", B_hint: "+ idiom (hint)", B_paraphrase: "+ idiom (paraphrase)", C_selected: "+ selected context",
  C_concat: "control: unfiltered context", D_paraphrase: "idiom (paraphrase) + context", D_hint: "idiom (hint) + context", E: "not implemented",
};

const dirScores = (v: Record<string, number> | null) => (v ? Object.entries(v).map(([d, s]) => `${d.replace("_Latn", "").replace("_Deva", "")}: ${s.toFixed(1)}`).join(" · ") : "unavailable");

export default function ExperimentsPage() {
  const [run, setRun] = useState("");
  const [batch, setBatch] = useState("");
  const q = run ? `?experiment_id=${encodeURIComponent(run)}${batch ? `&batch_id=${encodeURIComponent(batch)}` : ""}` : null;
  const abl = useApi<Ablation>(q && `/api/research/ablation${q}`);
  const res = useApi<{ conditions: Record<string, { decision_counts: Record<string, number> }> }>(run ? `/api/experiments/${encodeURIComponent(run)}/results` : null);
  const met = useApi<{ controller: Record<string, { output_changed_vs_baseline: number; n: number }> }>(q && `/api/research/metrics${q}`);
  const rows = abl.data?.rows ?? [];

  return (
    <div className="space-y-5">
      <Card title="Experimental comparison"><RunPicker run={run} setRun={setRun} batch={batch} setBatch={setBatch} /></Card>
      {(abl.loading && !abl.data) && <Spinner label="Computing metrics from stored predictions…" />}
      <ErrorBox error={abl.error} />
      {abl.data && (
        <div className={`space-y-5 ${abl.loading ? "opacity-60" : ""}`}>
          {!abl.data.reportable && <Notice><strong>Not reportable.</strong> {abl.data.notes.join(" · ")}</Notice>}
          {!abl.data.semantic_available && <Notice><strong>Strict SPR unavailable:</strong> {abl.data.semantic_reason}. SPR needs human ratings (Annotate page); it is never estimated automatically.</Notice>}
          <Card title="All conditions">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="py-2 pr-3">Condition</th><th className="pr-3">BLEU (13a)</th><th className="pr-3">spBLEU</th><th className="pr-3">chrF++</th>
                    <th className="pr-3 text-right">SPR</th><th className="pr-3 text-right">Idiom SPR</th><th className="pr-3 text-right">Sarcasm SPR</th>
                    <th className="pr-3 text-right">Context SPR</th><th className="pr-3 text-right">ΔSPR (pp)</th><th className="pr-3 text-right">Coverage</th>
                    <th className="pr-3 text-right">Harmful</th><th className="text-right">Latency (median)</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.condition} className="border-b border-line align-top">
                      <td className="py-2 pr-3"><div className="font-mono text-xs">{r.condition}</div><div className="text-xs text-muted">{CONDITION_HELP[r.condition]}</div></td>
                      <td className="pr-3 text-xs"><Value v={dirScores(r.bleu_13a)} /></td>
                      <td className="pr-3 text-xs"><Value v={dirScores(r.spbleu_flores200)} /></td>
                      <td className="pr-3 text-xs"><Value v={dirScores(r.chrfpp)} /></td>
                      <td className="pr-3 text-right"><Value v={fmt(r.spr_overall, 1, "%")} /></td>
                      <td className="pr-3 text-right"><Value v={fmt(r.spr_idiom, 1, "%")} /></td>
                      <td className="pr-3 text-right"><Value v={fmt(r.spr_sarcasm, 1, "%")} /></td>
                      <td className="pr-3 text-right"><Value v={fmt(r.spr_context, 1, "%")} /></td>
                      <td className="pr-3 text-right"><Value v={r.condition === "A" ? "—" : fmt(r.delta_spr_pp, 1)} /></td>
                      <td className="pr-3 text-right"><Value v={pct(r.intervention_coverage)} /></td>
                      <td className="pr-3 text-right"><Value v={r.condition === "A" ? "—" : fmt(r.harmful_intervention_rate, 1, "%")} /></td>
                      <td className="text-right text-xs"><div><Value v={ms(r.latency_ms?.translation_median)} /> NLLB</div><div className="text-muted">{ms(r.latency_ms?.modules_median)} modules</div></td>
                    </tr>
                  ))}
                  <tr className="text-muted"><td className="py-2 font-mono text-xs">E</td><td colSpan={11} className="text-xs italic">Not implemented: no validated sarcasm/intent module.</td></tr>
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted">BLEU/chrF++ exist only for items with human reference translations (e.g. FLORES). Scores are per direction; no average is shown. Coverage = share of items where the controller intervened; C_concat never uses the controller (it prepends the context window to every item that has context), so its coverage is 0 by construction.</p>
          </Card>
          <div className="grid gap-5 md:grid-cols-2">
            <Card><MetricBars title="Strict SPR (human-rated)" unit="%" rows={rows.map((r) => ({ name: r.condition, value: r.spr_overall }))} format={(v) => `${v.toFixed(1)}%`} /></Card>
            <Card><MetricBars title="Intervention coverage" unit="% of items" rows={rows.map((r) => ({ name: r.condition, value: r.intervention_coverage === null ? null : r.intervention_coverage * 100 }))} format={(v) => `${v.toFixed(1)}%`} /></Card>
            <Card><MetricBars title="Outputs that differ from baseline A" unit="items" rows={rows.filter((r) => r.condition !== "A").map((r) => ({ name: r.condition, value: met.data?.controller[r.condition]?.output_changed_vs_baseline ?? null }))} format={(v) => String(v)} /></Card>
            <Card><MetricBars title="Median NLLB time per item" unit="ms" rows={rows.map((r) => ({ name: r.condition, value: r.latency_ms?.translation_median ?? null }))} format={(v) => `${Math.round(v)}`} /></Card>
          </div>
          {res.data && <Card><DecisionStack rows={Object.entries(res.data.conditions).map(([name, c]) => ({ name, counts: c.decision_counts ?? {} }))} /></Card>}
        </div>
      )}
    </div>
  );
}
