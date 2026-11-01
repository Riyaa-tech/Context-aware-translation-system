import { useState } from "react";
import { DecisionStack } from "../components/charts";
import { RunPicker } from "../components/RunPicker";
import { Card, Notice, Value, ErrorBox } from "../components/ui";
import { fmt, ms } from "../lib/format";
import { useApi, RunSummary } from "../lib/hooks";

interface DatasetFile { file: string; sha256: string; n: number; by_split: Record<string, number>; by_category: Record<string, number>;
  by_direction: Record<string, number>; provenance: string[]; errors: number }

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex justify-between gap-3 border-t border-line py-1 text-sm"><span className="text-muted">{k}</span><span className="text-right">{v}</span></div>;
}

export default function DashboardPage() {
  const [run, setRun] = useState("");
  const [batch, setBatch] = useState("");
  const runs = useApi<{ experiments: RunSummary[] }>("/api/experiments");
  const ds = useApi<{ challenge_files: DatasetFile[]; flores_files: string[]; test_split_present: boolean }>("/api/research/datasets");
  const info = useApi<any>("/api/system/run-info");
  const reps = useApi<{ reports: { name: string; bytes: number }[] }>("/api/research/reports");
  const q = run ? `?experiment_id=${encodeURIComponent(run)}${batch ? `&batch_id=${encodeURIComponent(batch)}` : ""}` : null;
  const met = useApi<any>(q && `/api/research/metrics${q}`);
  const res = useApi<{ conditions: Record<string, { decision_counts: Record<string, number> }> }>(run ? `/api/experiments/${encodeURIComponent(run)}/results` : null);
  const errs = useApi<any>(batch ? `/api/research/errors?batch_id=${encodeURIComponent(batch)}` : null);
  const m = met.data;

  return (
    <div className="space-y-5">
      {ds.data && !ds.data.test_split_present && (
        <Notice><strong>No held-out test data yet.</strong> All runs so far use development data or a FLORES pilot subset, so no result here answers the research question. Next steps: team-written test items, frozen decision rule, human ratings.</Notice>
      )}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Experiment history" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead><tr className="text-left text-xs text-muted"><th className="py-1">Run</th><th>Status</th><th>Split</th><th>Reportable</th><th className="text-right">Items</th><th>Directions</th></tr></thead>
              <tbody>{runs.data?.experiments.map((r) => (
                <tr key={r.experiment_id} className="border-t border-line">
                  <td className="py-1 font-mono text-xs">{r.experiment_id}</td><td>{r.status}</td><td>{r.split}</td>
                  <td>{r.reportable ? "yes" : "no"}</td><td className="text-right tabular-nums">{r.n_examples}</td>
                  <td className="text-xs">{r.directions.join(", ")}</td>
                </tr>))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Model configuration">
          {info.data ? (<>
            <KV k="Model" v={<span className="font-mono text-xs">{info.data.model.model_id}</span>} />
            <KV k="Revision" v={<span className="font-mono text-xs">{info.data.model.requested_revision?.slice(0, 12)}</span>} />
            <KV k="Decoding" v={`beam ${info.data.model.generation_config.num_beams}, sampling ${info.data.model.generation_config.do_sample ? "on" : "off"}, max ${info.data.model.generation_config.max_new_tokens} tokens`} />
            <KV k="Device" v={info.data.model.device ?? "loads on first request"} />
            <KV k="transformers / torch" v={`${info.data.packages.transformers} / ${info.data.packages.torch}`} />
            <KV k="sacrebleu" v={info.data.packages.sacrebleu} />
            <KV k="Hardware" v={`${info.data.hardware.cpu_count} CPU, ${info.data.hardware.ram_gb} GB${info.data.hardware.cuda_available ? ", GPU" : ", no GPU"}`} />
            <p className="mt-2 text-xs text-muted">The backbone is used unchanged: no fine-tuning.</p>
          </>) : <ErrorBox error={info.error} />}
        </Card>
      </div>

      <Card title="Datasets">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead><tr className="text-left text-xs text-muted"><th className="py-1">File</th><th className="text-right">Items</th><th>Splits</th><th>Categories</th><th>Provenance</th></tr></thead>
            <tbody>{ds.data?.challenge_files.map((f) => (
              <tr key={f.file} className="border-t border-line align-top">
                <td className="py-1 font-mono text-xs">{f.file.split("/").pop()}<div className="text-muted">sha {f.sha256}</div></td>
                <td className="text-right tabular-nums">{f.n}</td>
                <td className="text-xs">{Object.entries(f.by_split).map(([k, v]) => `${k} ${v}`).join(", ")}</td>
                <td className="text-xs">{Object.entries(f.by_category).map(([k, v]) => `${k} ${v}`).join(", ")}</td>
                <td className="text-xs text-muted">{f.provenance.join("; ")}</td>
              </tr>))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">FLORES-200 files available locally: {ds.data?.flores_files.length ?? 0} (10 directions × dev/devtest; CC-BY-SA 4.0).</p>
      </Card>

      <Card title="Run analysis"><RunPicker run={run} setRun={setRun} batch={batch} setBatch={setBatch} /></Card>
      <ErrorBox error={met.error} />
      {m && (
        <div className={`grid gap-5 lg:grid-cols-2 ${met.loading ? "opacity-60" : ""}`}>
          {m.notes?.length > 0 && <div className="lg:col-span-2"><Notice>{m.notes.join(" · ")}</Notice></div>}
          <Card title="Results by language direction (reference-based)">
            {Object.entries(m.general_quality).map(([c, g]: [string, any]) => (
              <div key={c} className="mb-2">
                <div className="font-mono text-xs">{c}</div>
                {g.available === false ? <p className="text-sm italic text-muted">unavailable — {g.reason}</p> :
                  Object.entries(g.by_direction).map(([d, s]: [string, any]) => (
                    <div key={d} className="text-sm">{d} (n={s.chrfpp.n}): BLEU(13a) {fmt(s.bleu_13a.score, 2)} · spBLEU {fmt(s.spbleu_flores200.score, 2)} · chrF++ {fmt(s.chrfpp.score, 2)}</div>))}
              </div>))}
          </Card>
          <Card title="Statistical tests and confidence intervals">
            {Object.entries(m.general_quality).flatMap(([c, g]: [string, any]) => Object.entries(g.paired_bootstrap_vs_A ?? {}).flatMap(([d, t]: [string, any]) =>
              Object.entries(t).map(([name, r]: [string, any]) => (
                <div key={c + d + name} className="text-sm"><span className="font-mono text-xs">{c}</span> vs A · {d} · {name}: Δ {fmt(r.delta, 2)} (95% CI {r.ci95[0]} to {r.ci95[1]}; p(B≤A) = {r.p_b_not_better}; {r.n_samples} paired bootstrap samples)</div>)))) }
            {m.semantic.available ? Object.entries(m.semantic.per_condition).map(([c, e]: [string, any]) => (
              <div key={c} className="mt-1 text-sm"><span className="font-mono text-xs">{c}</span>: SPR {fmt(e.overall.spr, 1, "%")} (95% CI {e.overall.spr_ci95?.join("–")}, n={e.n_rated})
                {e.delta_vs_A && <> · ΔSPR {fmt(e.delta_vs_A.overall.delta_pp, 1)} pp (CI {e.delta_vs_A.overall.delta_pp_ci95?.join(" to ")}), McNemar p = {fmt(e.delta_vs_A.overall.mcnemar?.p_value, 4)}</>}</div>))
              : <p className="mt-2 text-sm italic text-muted">SPR confidence intervals and McNemar tests: unavailable — {m.semantic.reason}</p>}
            {m.semantic.available && m.semantic.single_rater_limitation && <p className="mt-2 text-xs">Limitation: single rater — no agreement statistic.</p>}
          </Card>
          {res.data && <Card title="Ablation: controller decisions"><DecisionStack rows={Object.entries(res.data.conditions).map(([name, c]) => ({ name, counts: c.decision_counts ?? {} }))} /></Card>}
          <Card title="Detectors and latency">
            {Object.entries(m.detectors).map(([c, d]: [string, any]) => (
              <div key={c} className="text-sm"><span className="font-mono text-xs">{c}</span>: idiom F1 <Value v={d.idiom.available === false ? "unavailable" : fmt(d.idiom.f1, 3)} /> · context state acc <Value v={d.context.available === false ? "unavailable" : fmt(d.context.state_accuracy, 3)} /> · modules {ms(m.latency[c]?.modules_median)} · NLLB {ms(m.latency[c]?.translation_median)}</div>))}
            <p className="mt-2 text-xs text-muted">Detector scores on dev data are optimistic (rules and examples written by the same author).</p>
          </Card>
          <Card title="Error analysis (human annotations)" className="lg:col-span-2">
            {!batch ? <p className="text-sm italic text-muted">unavailable — choose an annotation batch above.</p>
              : errs.data?.available ? (
                <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>{Object.entries(errs.data.by_condition).map(([c, v]: [string, any]) => (
                  <tr key={c} className="border-t border-line"><td className="py-1 pr-3 font-mono text-xs">{c}</td><td className="text-xs">{Object.entries(v).sort((a: any, b: any) => b[1] - a[1]).map(([k, n]) => `${k} ${n}`).join(" · ")}</td></tr>))}</tbody></table></div>
              ) : <p className="text-sm italic text-muted">unavailable — {errs.data?.reason ?? "loading"}</p>}
          </Card>
        </div>
      )}

      <Card title="Downloadable reports">
        <ul className="space-y-1 text-sm">
          {run && <li><a className="text-accent hover:underline" href={`/api/research/metrics${q}`} download>Full metrics JSON for the selected run</a></li>}
          {reps.data?.reports.map((r) => <li key={r.name}><a className="font-mono text-xs text-accent hover:underline" href={`/api/research/reports/${encodeURIComponent(r.name)}`}>{r.name}</a></li>)}
        </ul>
      </Card>
    </div>
  );
}
