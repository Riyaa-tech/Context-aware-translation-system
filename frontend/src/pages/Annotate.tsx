import { useEffect, useState } from "react";
import { api, post } from "../lib/api";
import { useApi, Batch, RunSummary } from "../lib/hooks";
import { Button, Card, ErrorBox, inputCls, Notice } from "../components/ui";

interface Rubric { ratings: Record<string, string>; sub_scale: string[]; sub_dimensions: Record<string, string>; error_categories: Record<string, string>; guidelines: string[] }
interface Item { item_id: string; source_text: string; context: string[]; intended_meaning: string | null; reference_translation: string | null;
  source_lang: string; target_lang: string; translation: string; my_annotation: Record<string, any> | null }

const RATING_LABEL: Record<string, string> = { preserved: "Meaning preserved", partial: "Partially preserved", not_preserved: "Meaning not preserved" };
const empty = { rating: "", core_proposition: "", figurative_meaning: "", pragmatic_intent: "", unsupported_addition: false, omission: false, primary_error: "", comment: "" };

export default function AnnotatePage() {
  const rubric = useApi<Rubric>("/api/annotations/rubric");
  const [reload, setReload] = useState(0);
  const batches = useApi<{ batches: Batch[] }>(`/api/annotations/batches?r=${reload}`);
  const runs = useApi<{ experiments: RunSummary[] }>("/api/experiments");
  const [batch, setBatch] = useState("");
  const [rater, setRater] = useState(() => { try { return localStorage.getItem("rater") ?? ""; } catch { return ""; } });
  const [pending, setPending] = useState(true);
  const [items, setItems] = useState<Item[]>([]);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [i, setI] = useState(0);
  const [form, setForm] = useState<typeof empty>(empty);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [newRun, setNewRun] = useState("");

  useEffect(() => { if (!batch && batches.data?.batches.length) setBatch(batches.data.batches[0].batch_id); }, [batches.data]); // eslint-disable-line
  const it = items[i];
  useEffect(() => { setForm(it?.my_annotation ? { ...empty, ...Object.fromEntries(Object.entries(it.my_annotation).map(([k, v]) => [k, v ?? (typeof (empty as any)[k] === "boolean" ? false : "")])) } as any : empty); setMsg(""); }, [it]);

  async function start() {
    setError(null);
    try {
      try { localStorage.setItem("rater", rater); } catch { /* storage unavailable */ }
      const d = await api<{ items: Item[]; done: number; total: number }>(`/api/annotations?batch_id=${encodeURIComponent(batch)}&rater_id=${encodeURIComponent(rater)}&only_pending=${pending}`);
      setItems(d.items); setProgress({ done: d.done, total: d.total }); setI(0);
    } catch (e) { setError((e as Error).message); }
  }
  async function createBatch() {
    setError(null);
    try {
      const b = await post<{ batch_id: string; n_items: number; n_condition_outputs: number }>("/api/annotations/batches", { experiment_id: newRun });
      setMsg(`Created ${b.batch_id}: ${b.n_items} items (from ${b.n_condition_outputs} condition outputs; identical outputs merged).`);
      setReload((x) => x + 1); setBatch(b.batch_id);
    } catch (e) { setError((e as Error).message); }
  }
  async function save() {
    if (!form.rating) { setMsg("Choose an overall rating first."); return; }
    const body: Record<string, unknown> = { item_id: it.item_id, rater_id: rater, rating: form.rating,
      unsupported_addition: form.unsupported_addition, omission: form.omission, primary_error: form.primary_error || null, comment: form.comment || null };
    for (const k of Object.keys(rubric.data!.sub_dimensions)) body[k] = (form as any)[k] || null;
    try {
      await post("/api/annotations", body);
      if (!it.my_annotation) setProgress((p) => ({ ...p, done: p.done + 1 }));
      setItems((xs) => xs.map((x, j) => (j === i ? { ...x, my_annotation: body } : x)));
      setI((x) => x + 1);
    } catch (e) { setMsg(`Not saved: ${(e as Error).message}`); }
  }

  const sel = batches.data?.batches.find((b) => b.batch_id === batch);
  const run = runs.data?.experiments.find((r) => r.experiment_id === sel?.experiment_id);
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-5">
        <Card title="Rater setup">
          <label className="block text-sm">Batch
            <select className={inputCls} value={batch} onChange={(e) => setBatch(e.target.value)}>
              {!batches.data?.batches.length && <option value="">No batches yet</option>}
              {batches.data?.batches.map((b) => <option key={b.batch_id} value={b.batch_id}>{b.batch_id} ({b.n_items})</option>)}
            </select>
          </label>
          <label className="mt-3 block text-sm">Your rater ID
            <input className={inputCls} value={rater} onChange={(e) => setRater(e.target.value)} placeholder="e.g. rater_riya" maxLength={40} />
          </label>
          <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={pending} onChange={(e) => setPending(e.target.checked)} /> Only items I have not rated</label>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button primary onClick={start} disabled={!batch || !rater.trim()}>Start rating</Button>
            {batch && <a className="rounded-lg border border-line px-3.5 py-2 text-sm hover:border-accent" href={`/api/annotations/export?batch_id=${encodeURIComponent(batch)}&format=csv`}>Export CSV</a>}
            {batch && <a className="rounded-lg border border-line px-3.5 py-2 text-sm hover:border-accent" href={`/api/annotations/export?batch_id=${encodeURIComponent(batch)}&format=jsonl`}>Export JSONL</a>}
          </div>
          {sel && <p className="mt-3 text-xs text-muted">Ratings so far: {Object.entries(sel.raters).map(([r, n]) => `${r} ${n}`).join(", ") || "none"}</p>}
          {run && !run.reportable && <div className="mt-3"><Notice>This batch comes from a <strong>dev</strong> run: use it to practise the protocol, not for reported results.</Notice></div>}
          <ErrorBox error={error} />
        </Card>
        <Card title="Create a batch from a run">
          <select className={inputCls} value={newRun} onChange={(e) => setNewRun(e.target.value)}>
            <option value="">Choose a completed run…</option>
            {runs.data?.experiments.filter((r) => r.status === "complete").map((r) => <option key={r.experiment_id} value={r.experiment_id}>{r.experiment_id}</option>)}
          </select>
          <Button className="mt-3" onClick={createBatch} disabled={!newRun}>Create blinded batch</Button>
          <p className="mt-2 text-xs text-muted">Condition and category are hidden from raters; each rater sees their own random order.</p>
        </Card>
        {rubric.data && <Card title="Guidelines"><ul className="list-disc space-y-1 pl-5 text-sm">{rubric.data.guidelines.map((g) => <li key={g}>{g}</li>)}</ul></Card>}
      </div>

      <div className="space-y-5 lg:col-span-2">
        {!items.length ? (
          <Card><p className="text-sm text-muted">{msg || "Choose a batch and your rater ID, then press Start rating."}</p></Card>
        ) : !it ? (
          <Card><p className="text-sm">No more items in this view. Rated {progress.done} of {progress.total}.</p></Card>
        ) : (
          <>
            <div>
              <div className="h-2 overflow-hidden rounded bg-line"><div className="h-full bg-accent" style={{ width: `${progress.total ? (100 * progress.done) / progress.total : 0}%` }} /></div>
              <p className="mt-1 text-xs text-muted">{progress.done} of {progress.total} rated · item {i + 1} of {items.length} in this view · {it.source_lang} → {it.target_lang}</p>
            </div>
            <Card>
              {it.context.length > 0 && <div className="mb-3"><div className="text-xs font-semibold uppercase text-muted">Preceding context</div><p className="text-sm">{it.context.join(" ")}</p></div>}
              <div className="text-xs font-semibold uppercase text-muted">Source sentence</div><p className="text-lg">{it.source_text}</p>
              <div className="mt-3 text-xs font-semibold uppercase text-muted">Intended meaning</div><p className="text-sm">{it.intended_meaning ?? "—"}</p>
              {it.reference_translation && <><div className="mt-3 text-xs font-semibold uppercase text-muted">Reference (guide only)</div><p className="text-sm text-muted">{it.reference_translation}</p></>}
              <div className="mt-3 text-xs font-semibold uppercase text-muted">Translation to rate</div>
              <p className="rounded-lg border-l-4 border-accent bg-page p-3 text-xl">{it.translation}</p>
            </Card>
            <Card>
              <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Overall meaning">
                {Object.keys(rubric.data?.ratings ?? {}).map((k) => (
                  <button key={k} role="radio" aria-checked={form.rating === k} title={rubric.data!.ratings[k]} onClick={() => setForm({ ...form, rating: k })}
                    className={`rounded-lg border px-3 py-3 text-sm font-medium ${form.rating === k ? "border-accent ring-2 ring-accent" : "border-line"}`}>{RATING_LABEL[k]}</button>
                ))}
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {Object.entries(rubric.data?.sub_dimensions ?? {}).map(([k, q]) => (
                  <label key={k} className="text-sm">{q}
                    <select className={inputCls} value={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}>
                      <option value="">—</option>{rubric.data!.sub_scale.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.unsupported_addition} onChange={(e) => setForm({ ...form, unsupported_addition: e.target.checked })} /> Unsupported addition</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.omission} onChange={(e) => setForm({ ...form, omission: e.target.checked })} /> Omission</label>
              </div>
              <label className="mt-3 block text-sm">Primary error category
                <select className={inputCls} value={form.primary_error} onChange={(e) => setForm({ ...form, primary_error: e.target.value })}>
                  <option value="">—</option>{Object.entries(rubric.data?.error_categories ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label className="mt-3 block text-sm">Comment<textarea className={`${inputCls} min-h-[60px]`} maxLength={2000} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} /></label>
              <div className="mt-4 flex gap-2"><Button onClick={() => setI((x) => Math.max(0, x - 1))} disabled={i === 0}>Previous</Button><Button primary onClick={save}>Save and next</Button></div>
              {msg && <p className="mt-2 text-sm text-muted" role="status">{msg}</p>}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
