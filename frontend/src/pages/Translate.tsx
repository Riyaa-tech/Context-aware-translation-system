import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, CompareResponse, Languages, post } from "../lib/api";
import { langName, ms } from "../lib/format";
import { useAppState } from "../state";
import { Button, Card, DecisionBadge, ErrorBox, inputCls, Spinner } from "../components/ui";

const EXAMPLES = [
  { label: "Idiom", text: "She finally spilled the beans about the surprise party.", context: "", src: "eng_Latn", tgt: "hin_Deva" },
  { label: "Literal control", text: "He spilled the beans all over the kitchen floor.", context: "", src: "eng_Latn", tgt: "hin_Deva" },
  { label: "Context: river", text: "He went to the bank.", context: "The fisherman sat beside the river.", src: "eng_Latn", tgt: "hin_Deva" },
  { label: "Irrelevant context", text: "He went to the bank.", context: "My cousin called me yesterday.", src: "eng_Latn", tgt: "hin_Deva" },
  { label: "Spanish idiom", text: "No te creo, me estás tomando el pelo.", context: "", src: "spa_Latn", tgt: "eng_Latn" },
  { label: "Sarcasm (no module)", text: "Wonderful, another delay!", context: "Our flight was postponed for the third time.", src: "eng_Latn", tgt: "spa_Latn" },
];

const ACTION_TEXT: Record<string, string> = {
  accept: "applied", reject_literal: "not applied — literal use", abstain_uncertain: "abstained — uncertain",
  abstain_conflict: "abstained — conflict", reject_low_confidence: "not applied — low confidence",
  reject_review_status: "not applied — review status", no_context_required: "no context needed",
  resolved_no_rewrite: "resolved — no rewrite needed", abstain_irrelevant: "abstained — context irrelevant",
  abstain_insufficient: "abstained — no context", abstain_ambiguous: "abstained — context ambiguous",
};

export default function TranslatePage() {
  const { last, setLast } = useAppState();
  const [langs, setLangs] = useState<Languages | null>(null);
  const [src, setSrc] = useState("eng_Latn");
  const [tgt, setTgt] = useState("hin_Deva");
  const [text, setText] = useState(EXAMPLES[0].text);
  const [context, setContext] = useState("");
  const [idiom, setIdiom] = useState(true);
  const [ctx, setCtx] = useState(true);
  const [idiomMode, setIdiomMode] = useState<"paraphrase" | "hint">("paraphrase");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  useEffect(() => { api<Languages>("/api/languages").then(setLangs).catch((e) => setError(e.message)); }, []);
  const enabled = useMemo(() => langs?.directions.filter((d) => d.status === "enabled") ?? [], [langs]);
  const sources = [...new Set(enabled.map((d) => d.source))];
  const targets = enabled.filter((d) => d.source === src).map((d) => d.target);
  useEffect(() => { if (targets.length && !targets.includes(tgt)) setTgt(targets[0]); }, [src, langs]); // eslint-disable-line

  async function run() {
    setBusy(true); setError(null);
    const t0 = performance.now();
    try {
      const modules = [...(idiom ? ["idiom"] : []), ...(ctx ? ["context"] : [])];
      const r = await post<CompareResponse>("/api/translate/compare", {
        text, source_lang: src, target_lang: tgt, idiom_mode: idiomMode, modules,
        context: context.split("\n").map((s) => s.trim()).filter(Boolean),
      });
      setLast(r); setElapsed(performance.now() - t0);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const rec = last?.enhanced.record;
  return (
    <div className="grid gap-5 lg:grid-cols-5">
      <Card title="Input" className="lg:col-span-2">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {EXAMPLES.map((e) => (
            <button key={e.label} onClick={() => { setSrc(e.src); setTgt(e.tgt); setText(e.text); setContext(e.context); }}
              className="rounded-full border border-line px-2.5 py-1 text-xs hover:border-accent">{e.label}</button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-sm">From
            <select className={inputCls} value={src} onChange={(e) => setSrc(e.target.value)}>
              {sources.map((c) => <option key={c} value={c}>{langName(c, langs?.languages)}</option>)}
            </select>
          </label>
          <label className="text-sm">To
            <select className={inputCls} value={tgt} onChange={(e) => setTgt(e.target.value)}>
              {targets.map((c) => <option key={c} value={c}>{langName(c, langs?.languages)}</option>)}
            </select>
          </label>
        </div>
        <label className="mt-3 block text-sm">Preceding context <span className="text-muted">(optional, one sentence per line, oldest first)</span>
          <textarea className={`${inputCls} min-h-[64px]`} value={context} onChange={(e) => setContext(e.target.value)} />
        </label>
        <label className="mt-3 block text-sm">Sentence to translate
          <textarea className={`${inputCls} min-h-[80px] text-base`} value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
        </label>
        <fieldset className="mt-3 rounded-lg border border-line p-3 text-sm">
          <legend className="px-1 text-muted">Proposed system modules</legend>
          <label className="mr-4 inline-flex items-center gap-2"><input type="checkbox" checked={idiom} onChange={(e) => setIdiom(e.target.checked)} /> Idiom (M1)</label>
          <label className="mr-4 inline-flex items-center gap-2"><input type="checkbox" checked={ctx} onChange={(e) => setCtx(e.target.checked)} /> Selected context (M2)</label>
          <label className="mt-2 flex items-center gap-2">Idiom mode
            <select className={`${inputCls} w-auto`} value={idiomMode} onChange={(e) => setIdiomMode(e.target.value as "paraphrase" | "hint")}>
              <option value="paraphrase">controlled paraphrase</option><option value="hint">inline hint</option>
            </select>
          </label>
          <p className="mt-2 text-xs text-muted">Sarcasm module (M3): not implemented — sarcasm is an evaluation category only.</p>
        </fieldset>
        <div className="mt-4 flex items-center gap-3">
          <Button primary onClick={run} disabled={busy || !text.trim()}>Translate</Button>
          {busy && <Spinner label="Running NLLB-200 (CPU: a few seconds)…" />}
        </div>
        <ErrorBox error={error} />
      </Card>

      <div className="space-y-5 lg:col-span-3">
        {!last ? (
          <Card><p className="text-sm text-muted">Pick an example or type a sentence, then press Translate. Both outputs come from the real model.</p></Card>
        ) : (
          <>
            <Card title={<span className="text-sm uppercase tracking-wide text-muted">Baseline NLLB-200 (condition A)</span>}>
              <p className="text-lg" lang={last.enhanced.target_lang.slice(0, 2)}>{last.baseline.translation}</p>
              <p className="mt-2 text-xs text-muted">Input sent to NLLB: <span className="font-mono">{last.enhanced.source_text}</span> · {ms(last.baseline.latency_ms)}</p>
            </Card>
            <Card title={<span className="text-sm uppercase tracking-wide text-muted">Proposed system ({last.enhanced.condition})</span>}
              actions={<DecisionBadge d={last.enhanced.controller_decision} />}>
              <p className="text-lg" lang={last.enhanced.target_lang.slice(0, 2)}>{last.enhanced.translation}</p>
              <p className="mt-2 text-xs text-muted">Input sent to NLLB: <span className="font-mono">{last.enhanced.nllb_input}</span></p>
              <p className="mt-1 text-xs text-muted">
                {last.outputs_differ ? "Output differs from the baseline." : "Output is identical to the baseline."}
                {elapsed !== null && <> · Round trip for both: {ms(elapsed)} · modules {ms(rec?.latency_ms?.modules)}</>}
              </p>
            </Card>
            <Card title="Why the controller decided this" actions={<Link to="/pipeline" className="text-sm text-accent hover:underline">Open full pipeline →</Link>}>
              {rec?.span_decisions?.length ? (
                <ul className="space-y-2 text-sm">
                  {rec.span_decisions.map((s: any, i: number) => (
                    <li key={i} className="rounded-lg border border-line p-2">
                      <div><span className="font-medium">{s.module === "idiom" ? "Idiom" : "Context"}</span> <span className="font-mono text-xs">{s.item_id}</span> — <strong>{ACTION_TEXT[s.action] ?? s.action}</strong></div>
                      <div className="text-muted">{s.reason}</div>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted">No idiom or ambiguous word was detected, so the sentence was passed to NLLB unchanged.</p>}
              {rec?.abstention_reason && <p className="mt-2 text-sm"><strong>Abstention reason:</strong> {rec.abstention_reason}</p>}
              {(rec?.conflicts?.length ?? 0) > 0 && <p className="mt-2 text-sm"><strong>Conflicts:</strong> {rec?.conflicts.join("; ")}</p>}
              {rec?.module_predictions?.idiom?.some((p: any) => p.review_status === "draft") && (
                <p className="mt-2 text-xs text-muted">Lexicon entries used are marked “draft” (not yet human-reviewed).</p>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
