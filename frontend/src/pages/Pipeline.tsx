import { Link } from "react-router-dom";
import type { PipelineEvent } from "../lib/api";
import { ms } from "../lib/format";
import { useAppState } from "../state";
import { Card, DecisionBadge } from "../components/ui";

const STAGE_LABEL: Record<string, string> = {
  input: "Input", idiom_detection: "Idiom detection (M1)", context_analysis: "Context relevance analysis (M2)",
  controller: "Semantic controller", translation: "NLLB-200 (unchanged)", output: "Final translation",
};

function Chip({ children, tone = "line" }: { children: React.ReactNode; tone?: "line" | "s1" | "s2" | "s3" }) {
  const dot = { line: "bg-line", s1: "bg-s1", s2: "bg-s2", s3: "bg-s3" }[tone];
  return <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs"><span className={`h-1.5 w-1.5 rounded-full ${dot}`} />{children}</span>;
}

function IdiomDetails({ d }: { d: any }) {
  const c = d.candidates as any[];
  if (!c?.length) return <p className="text-sm text-muted">No lexicon idiom found in this sentence.</p>;
  return (
    <ul className="space-y-2">
      {c.map((x) => (
        <li key={x.idiom_id} className="rounded-lg border border-line p-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{x.idiom_id}</span> “{x.matched_text}”
            <Chip tone={x.usage === "figurative" ? "s1" : x.usage === "literal" ? "s3" : "s2"}>{x.usage}</Chip>
            <span className="text-xs text-muted">rule score {x.usage_score} (not a probability) · entry {x.review_status}</span>
          </div>
          <div className="mt-1 text-muted">Meaning: {x.intended_meaning} → paraphrase “{x.paraphrase}”</div>
          {(x.figurative_cues_found.length > 0 || x.literal_cues_found.length > 0 || x.literal_follower_found) && (
            <div className="mt-1 text-xs text-muted">
              figurative cues: {x.figurative_cues_found.join(", ") || "—"} · literal cues: {x.literal_cues_found.join(", ") || "—"}
              {x.literal_follower_found && <> · literal follower “{x.literal_follower_found}”</>}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function ContextDetails({ ev }: { ev: PipelineEvent }) {
  const d = ev.details as any;
  if (ev.status === "skipped") return <p className="text-sm text-muted">{d.reason}</p>;
  if (ev.status === "concat_all") return <p className="text-sm text-muted">{d.reason}. Window: {d.window?.join(" ") || "—"}</p>;
  return (
    <div className="space-y-2 text-sm">
      <div>Overall state: <Chip tone={d.state === "RELEVANT_CONTEXT_SELECTED" ? "s1" : d.state === "NO_CONTEXT_REQUIRED" ? "s3" : "s2"}>{d.state}</Chip></div>
      {!d.words?.length && <p className="text-muted">No ambiguous word from the sense inventory in this sentence.</p>}
      {d.words?.map((w: any) => (
        <div key={w.word_id + w.start} className="rounded-lg border border-line p-2">
          <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{w.word_id}</span> “{w.matched_text}” <Chip>{w.state}</Chip></div>
          <div className="mt-1 text-muted">{w.reason}</div>
          {w.resolved_sense && <div className="mt-1">Resolved sense: <strong>{w.resolved_sense}</strong> ({w.resolved_gloss ?? "in-sentence"}){w.replacement && <> → “{w.replacement}”</>}</div>}
          {w.sentence_scores?.length > 0 && (
            <table className="mt-2 w-full text-xs">
              <thead><tr className="text-left text-muted"><th className="py-1 pr-2">Context sentence</th><th className="pr-2">Dist.</th><th className="pr-2">Weight</th><th className="pr-2">Cues</th><th>Selected</th></tr></thead>
              <tbody>{w.sentence_scores.map((s: any) => (
                <tr key={s.index} className="border-t border-line align-top">
                  <td className="py-1 pr-2">{s.text}</td><td className="pr-2 tabular-nums">{s.distance}</td><td className="pr-2 tabular-nums">{s.weight}</td>
                  <td className="pr-2">{Object.entries(s.hits).map(([k, v]) => `${k}: ${(v as string[]).join(", ")}`).join("; ") || "—"}</td>
                  <td>{s.selected ? "yes" : "no"}</td>
                </tr>))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}

function ControllerDetails({ d }: { d: any }) {
  return (
    <div className="space-y-2 text-sm">
      <DecisionBadge d={d.decision} />
      {d.span_decisions?.map((s: any, i: number) => (
        <div key={i} className="text-muted"><span className="font-mono text-xs">{s.module}:{s.item_id}</span> → <strong className="text-ink">{s.action}</strong> — {s.reason}</div>
      ))}
      {d.abstention_reason && <div><strong>Abstention reason:</strong> {d.abstention_reason}</div>}
      {d.conflicts?.length > 0 && <div><strong>Conflicts:</strong> {d.conflicts.join("; ")}</div>}
      {d.rewrites?.length > 0 && (
        <div>Rewrites: {d.rewrites.map((r: any, i: number) => <span key={i} className="mr-2">“{r.original_span}” → “{r.replacement}” <span className="text-xs text-muted">({r.module})</span></span>)}</div>
      )}
      <div>Text sent to NLLB: <span className="font-mono">{d.nllb_input}</span></div>
    </div>
  );
}

export default function PipelinePage() {
  const { last } = useAppState();
  if (!last) {
    return <Card title="Pipeline explainability"><p className="text-sm text-muted">No translation yet. <Link className="text-accent hover:underline" to="/">Translate a sentence</Link> first; this page then shows the real backend events for it.</p></Card>;
  }
  const e = last.enhanced;
  const total = e.events.reduce((a, x) => a + x.duration_ms, 0);
  return (
    <div className="space-y-4">
      <Card title="Pipeline explainability">
        <p className="text-sm text-muted">Each step below is a logged backend event for this request (condition <span className="font-mono">{e.condition}</span>, model {e.model_id} @ {e.model_revision?.slice(0, 7)}). Times are measured, not animated. Total {ms(total)}.</p>
      </Card>
      <ol className="space-y-0">
        {e.events.map((ev, i) => (
          <li key={i} className="relative pl-8">
            <span className="absolute left-2 top-5 h-full w-px bg-line" aria-hidden />
            <span className="absolute left-0 top-4 flex h-4 w-4 items-center justify-center rounded-full border-2 border-accent bg-card" aria-hidden />
            <Card className="mb-3" title={<span>{STAGE_LABEL[ev.stage] ?? ev.stage}</span>}
              actions={<span className="text-xs text-muted">{ev.status} · {ms(ev.duration_ms)}</span>}>
              {ev.stage === "input" && <div className="text-sm"><div className="text-lg">{(ev.details as any).text}</div>
                {e.record.context?.length > 0 && <div className="mt-1 text-muted">Context: {e.record.context.join(" ")}</div>}</div>}
              {ev.stage === "idiom_detection" && (ev.status === "skipped" ? <p className="text-sm text-muted">{(ev.details as any).reason}</p> : <IdiomDetails d={ev.details} />)}
              {ev.stage === "context_analysis" && <ContextDetails ev={ev} />}
              {ev.stage === "controller" && <ControllerDetails d={ev.details} />}
              {ev.stage === "translation" && <div className="text-sm">Input: <span className="font-mono">{(ev.details as any).nllb_input}</span></div>}
              {ev.stage === "output" && <div><div className="text-lg">{(ev.details as any).final_translation}</div>
                <div className="mt-1 text-xs text-muted">Baseline for comparison: {last.baseline.translation}</div></div>}
            </Card>
          </li>
        ))}
      </ol>
    </div>
  );
}
