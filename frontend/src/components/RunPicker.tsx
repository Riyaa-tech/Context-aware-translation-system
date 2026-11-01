import { useEffect } from "react";
import { useApi, RunSummary, Batch } from "../lib/hooks";
import { inputCls } from "./ui";

/** Run + annotation-batch selectors in one row above the content they scope. */
export function RunPicker({ run, setRun, batch, setBatch }: { run: string; setRun: (v: string) => void; batch: string; setBatch: (v: string) => void }) {
  const runs = useApi<{ experiments: RunSummary[] }>("/api/experiments");
  const batches = useApi<{ batches: Batch[] }>("/api/annotations/batches");
  const done = runs.data?.experiments.filter((r) => r.status === "complete") ?? [];
  useEffect(() => { if (!run && done.length) setRun(done[0].experiment_id); }, [runs.data]); // eslint-disable-line
  const forRun = batches.data?.batches.filter((b) => b.experiment_id === run) ?? [];
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="min-w-[260px] flex-1 text-sm">Experiment run
        <select className={inputCls} value={run} onChange={(e) => { setRun(e.target.value); setBatch(""); }}>
          {done.length === 0 && <option value="">No completed runs</option>}
          {done.map((r) => <option key={r.experiment_id} value={r.experiment_id}>{r.experiment_id} · {r.split}{r.reportable ? "" : " (not reportable)"}</option>)}
        </select>
      </label>
      <label className="min-w-[220px] text-sm">Human annotation batch
        <select className={inputCls} value={batch} onChange={(e) => setBatch(e.target.value)}>
          <option value="">None (SPR unavailable)</option>
          {forRun.map((b) => <option key={b.batch_id} value={b.batch_id}>{b.batch_id.split("__")[1]} · {Object.values(b.raters).reduce((a, x) => a + x, 0)} ratings</option>)}
        </select>
      </label>
    </div>
  );
}
