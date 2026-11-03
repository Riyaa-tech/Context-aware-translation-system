import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, contextLines, Languages, MAX_CONTEXT_SENTENCES, translateEnhanced } from "../lib/api";
import { useAppState } from "../state";

// Languages offered on this page. Which pairs are allowed comes from the backend (/api/languages);
// the backend validates every request again.
const LANGS: { code: string; name: string }[] = [
  { code: "eng_Latn", name: "English" },
  { code: "hin_Deva", name: "Hindi" },
  { code: "deu_Latn", name: "German" },
];
// Used only if /api/languages cannot be reached; the backend still rejects anything unsupported.
const FALLBACK_DIRECTIONS = ["eng_Latn-hin_Deva", "hin_Deva-eng_Latn", "eng_Latn-deu_Latn", "deu_Latn-eng_Latn"];
const SLOW_MS = 8000;
const HEALTH_POLL_MS = 3000;
type ServerState = "checking" | "offline" | "loading" | "ready" | "error";

function friendly(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Could not reach the translation server. Please check that it is running and try again.";
}

export default function TranslatePage() {
  const { last, setLast } = useAppState();
  const [directions, setDirections] = useState<Set<string>>(new Set(FALLBACK_DIRECTIONS));
  const [src, setSrc] = useState(last?.input.source_lang ?? "eng_Latn");
  const [tgt, setTgt] = useState(last?.input.target_lang ?? "hin_Deva");
  const [context, setContext] = useState(last?.input.context.join("\n") ?? "");
  const [text, setText] = useState(last?.input.text ?? "");
  const [result, setResult] = useState<string | null>(last?.enhanced.translation ?? null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const inFlight = useRef(false); // guards against double submits before React re-renders
  const [server, setServer] = useState<ServerState>("checking");
  const [serverError, setServerError] = useState<string | null>(null);
  const [recheck, setRecheck] = useState(0);

  // Server/model status: poll /health until the model is ready, so users see why nothing happens yet.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = async () => {
      try {
        const h = await api<{ model_loaded: boolean; model_state?: string; model_error?: string | null }>("/health");
        const st = h.model_state ?? (h.model_loaded ? "ready" : "not_loaded");
        if (stopped) return;
        if (st === "ready" || st === "not_loaded") { setServer("ready"); return; } // not_loaded: loads on first request
        if (st === "error") { setServer("error"); setServerError(h.model_error ?? null); return; }
        setServer("loading");
      } catch {
        if (stopped) return;
        setServer("offline");
      }
      timer = setTimeout(check, HEALTH_POLL_MS);
    };
    check();
    return () => { stopped = true; clearTimeout(timer); };
  }, [recheck]);

  useEffect(() => {
    api<Languages>("/api/languages")
      .then((l) => setDirections(new Set(l.directions.filter((d) => d.status === "enabled").map((d) => `${d.source}-${d.target}`))))
      .catch(() => { /* keep the fallback list; a failed translation will show the error */ });
  }, []);

  const allowed = (s: string, t: string) => directions.has(`${s}-${t}`);
  const validTargets = useMemo(() => LANGS.filter((l) => allowed(src, l.code)).map((l) => l.code), [src, directions]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (validTargets.length && !validTargets.includes(tgt)) setTgt(validTargets[0]); }, [validTargets]); // eslint-disable-line react-hooks/exhaustive-deps

  const canSwap = allowed(tgt, src);
  function swap() {
    if (!canSwap) return;
    setSrc(tgt); setTgt(src);
    if (result) { setText(result); setResult(null); }
  }

  async function translate() {
    if (inFlight.current || !text.trim()) return;
    const ctx = contextLines(context);
    if (ctx.length > MAX_CONTEXT_SENTENCES) {
      setError(`Please use at most ${MAX_CONTEXT_SENTENCES} context sentences (one per line).`);
      return;
    }
    inFlight.current = true;
    setBusy(true); setSlow(false); setError(null); setCopied(false);
    const slowTimer = setTimeout(() => setSlow(true), SLOW_MS);
    const input = { text: text.trim(), source_lang: src, target_lang: tgt, context: ctx };
    try {
      const r = await translateEnhanced(input);
      setResult(r.translation);
      setLast({ input, enhanced: r });
    } catch (e) {
      setResult(null);
      setError(friendly(e));
      if (!(e instanceof ApiError)) setRecheck((n) => n + 1); // server unreachable: watch for it to come back
    } finally {
      clearTimeout(slowTimer);
      inFlight.current = false;
      setBusy(false); setSlow(false);
    }
  }

  async function copy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Copy failed. Please select the text and copy it manually.");
    }
  }

  const selectCls = "w-full appearance-none rounded-lg border border-line bg-card px-3 py-2.5 text-[15px] font-medium focus:border-accent focus:outline-none";
  const areaCls = "w-full resize-y rounded-lg border border-line bg-card px-4 py-3 text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none";

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="sr-only">Translate</h1>

      {/* Language selection */}
      <div className="mb-6 flex items-end gap-2 sm:gap-3">
        <label className="flex-1">
          <span className="mb-1.5 block text-sm text-muted">From</span>
          <select aria-label="Input language" className={selectCls} value={src} onChange={(e) => setSrc(e.target.value)}>
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
        </label>
        <button type="button" onClick={swap} disabled={!canSwap} aria-label="Swap languages" title="Swap languages"
          className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg text-muted hover:bg-card hover:text-ink disabled:opacity-30">
          ⇄
        </button>
        <label className="flex-1">
          <span className="mb-1.5 block text-sm text-muted">To</span>
          <select aria-label="Output language" className={selectCls} value={tgt} onChange={(e) => setTgt(e.target.value)}>
            {LANGS.map((l) => {
              const ok = allowed(src, l.code);
              return <option key={l.code} value={l.code} disabled={!ok}>{l.name}{!ok && l.code !== src ? " (not available)" : ""}</option>;
            })}
          </select>
        </label>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Input */}
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); translate(); }}>
          <label className="block">
            <span className="mb-1.5 block text-sm text-muted">Preceding context <span className="text-muted/80">(optional, one sentence per line)</span></span>
            <textarea aria-label="Preceding context" className={`${areaCls} min-h-[88px] text-[15px]`} value={context}
              placeholder="Enter preceding context (optional)..." onChange={(e) => setContext(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-muted">Sentence</span>
            <textarea aria-label="Sentence to translate" className={`${areaCls} min-h-[150px] text-lg`} value={text} maxLength={2000}
              placeholder="Enter the sentence you want to translate..." onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); translate(); } }} />
          </label>
          <button type="submit" disabled={busy || !text.trim()}
            className="rounded-lg bg-accent px-6 py-3 text-base font-semibold text-white shadow-sm transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 md:self-start">
            {busy ? "Translating…" : "Translate"}
          </button>
          {server === "loading" && (
            <p className="flex items-center gap-2 text-sm text-muted" role="status" aria-label="Server status">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" aria-hidden />
              Preparing the translation model. The first start can take a few minutes.
            </p>
          )}
          {server === "offline" && (
            <p className="text-sm text-bad" aria-label="Server status">
              Can't reach the translation server. Start it with <code>start.bat</code> (Windows) or <code>./start.sh</code>; this page connects automatically.
            </p>
          )}
          {server === "error" && (
            <p className="text-sm text-bad" aria-label="Server status">The translation model could not be loaded{serverError ? `: ${serverError}` : "."}</p>
          )}
        </form>

        {/* Output */}
        <section aria-label="Translation" aria-live="polite" aria-busy={busy}
          className="flex min-h-[200px] flex-col rounded-xl border border-line bg-page/60 p-5 md:mt-[26px]">
          {busy ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted" role="status">
              <span className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" aria-hidden />
              <span>Translating…</span>
              {slow && <span className="text-center text-sm">Still working. The first translation after the server starts can take longer.</span>}
            </div>
          ) : error ? (
            <p role="alert" className="text-bad">{error}</p>
          ) : result ? (
            <>
              <p className="flex-1 whitespace-pre-wrap text-xl leading-relaxed" lang={tgt.slice(0, 2)} data-testid="translation">{result}</p>
              <div className="mt-4 flex justify-end">
                <button type="button" onClick={copy}
                  className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:border-accent hover:text-ink">
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </>
          ) : (
            <p className="m-auto text-center text-muted">Your translation will appear here.</p>
          )}
        </section>
      </div>
    </div>
  );
}
