import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, contextLines, Languages, MAX_CONTEXT_SENTENCES, translateEnhanced } from "../lib/api";
import { AlertIcon, CheckIcon, ChevronIcon, CopyIcon, SwapIcon, XIcon } from "../components/icons";
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
const MAX_CHARS = 2000; // backend limit (TranslateRequest.text max_length)
const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
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
  const [copyFailed, setCopyFailed] = useState(false);
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
      setCopyFailed(true); // keep the translation visible; just explain
      setTimeout(() => setCopyFailed(false), 3000);
    }
  }

  const nameOf = (code: string) => LANGS.find((l) => l.code === code)?.name ?? code;
  const ctxCount = contextLines(context).length;
  const tooMuchContext = ctxCount > MAX_CONTEXT_SENTENCES;
  const selectCls = "w-full cursor-pointer appearance-none rounded-xl bg-transparent py-2.5 pl-3 pr-9 text-base font-semibold text-ink transition-colors hover:bg-surface2 focus:bg-surface2 focus:outline-none";

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">Translate</h1>
        <p className="mt-1 text-[15px] text-muted">English, Hindi and German. Add earlier sentences if a word could mean different things.</p>
      </div>

      {/* Language bar */}
      <div className="flex items-center gap-1 rounded-2xl border border-line bg-card p-1.5 shadow-soft sm:gap-2">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">From</span>
          <select aria-label="Input language" className={selectCls} value={src} onChange={(e) => setSrc(e.target.value)}>
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
          <ChevronIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        </label>
        <button type="button" onClick={swap} disabled={!canSwap} aria-label="Swap languages" title="Swap languages"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line text-muted transition-colors hover:border-linestrong hover:bg-surface2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40">
          <SwapIcon className="h-[18px] w-[18px]" />
        </button>
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">To</span>
          <select aria-label="Output language" className={selectCls} value={tgt} onChange={(e) => setTgt(e.target.value)}>
            {LANGS.map((l) => {
              const ok = allowed(src, l.code);
              return <option key={l.code} value={l.code} disabled={!ok}>{l.name}{!ok && l.code !== src ? " (not available)" : ""}</option>;
            })}
          </select>
          <ChevronIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        </label>
      </div>

      {/* Server status: shown only when not ready */}
      <div className="min-h-[28px] px-1 pt-2 text-sm">
        {server === "loading" && (
          <p className="flex items-center gap-2 text-muted" role="status" aria-label="Server status">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" aria-hidden />
            Preparing the translation model. The first start can take a few minutes.
          </p>
        )}
        {server === "offline" && (
          <p className="flex items-start gap-2 text-bad" aria-label="Server status">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-bad" aria-hidden />
            <span>Can't reach the translation server. Start it with <code className="rounded bg-badsoft px-1">start.bat</code> (Windows) or <code className="rounded bg-badsoft px-1">./start.sh</code>; this page connects automatically.</span>
          </p>
        )}
        {server === "error" && (
          <p className="flex items-start gap-2 text-bad" aria-label="Server status">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-bad" aria-hidden />
            The translation model could not be loaded{serverError ? `: ${serverError}` : "."}
          </p>
        )}
      </div>

      {/* Workspace */}
      <div className="mt-1 grid overflow-hidden rounded-2xl border border-line bg-card shadow-soft md:grid-cols-2">
        {/* Input */}
        <form className="flex min-w-0 flex-col" onSubmit={(e) => { e.preventDefault(); translate(); }}>
          <div className="border-b border-line px-5 pb-4 pt-4 sm:px-6">
            <div className="mb-1.5 flex items-baseline justify-between gap-2">
              <label htmlFor="ctx" className="text-sm font-medium text-ink">
                Context <span className="ml-1 rounded-md bg-surface2 px-1.5 py-0.5 text-xs font-normal text-muted">Optional</span>
              </label>
              {ctxCount > 0 && (
                <span className={`text-xs tabular-nums ${tooMuchContext ? "text-bad" : "text-muted"}`}>{ctxCount} / {MAX_CONTEXT_SENTENCES} sentences</span>
              )}
            </div>
            <textarea id="ctx" aria-label="Preceding context" rows={2} value={context}
              placeholder="Enter preceding context (optional)..." onChange={(e) => setContext(e.target.value)}
              className="w-full resize-y rounded-xl border border-line bg-surface2 px-3.5 py-2.5 text-[15px] leading-relaxed text-ink transition-colors placeholder:text-muted/70 hover:border-linestrong focus:border-accent focus:bg-card focus:outline-none focus:ring-2 focus:ring-accent/15" />
            <p className="mt-1.5 text-xs text-muted">Earlier sentences, one per line. They help with words that have more than one meaning.</p>
          </div>

          <div className="relative flex flex-1 flex-col px-5 pt-4 sm:px-6">
            <label htmlFor="src-text" className="sr-only">Sentence</label>
            <textarea id="src-text" aria-label="Sentence to translate" value={text} maxLength={MAX_CHARS}
              placeholder="Enter the sentence you want to translate..." onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); translate(); } }}
              className="min-h-[180px] w-full flex-1 resize-none bg-transparent pr-8 text-xl leading-relaxed text-ink placeholder:text-muted/60 focus:outline-none sm:text-[22px]" />
            {text && (
              <button type="button" onClick={() => setText("")} aria-label="Clear text" title="Clear text"
                className="absolute right-4 top-4 rounded-md p-1 text-muted transition-colors hover:bg-surface2 hover:text-ink">
                <XIcon className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 px-5 pb-5 pt-3 sm:px-6">
            <span className={`text-xs tabular-nums ${text.length >= MAX_CHARS ? "text-bad" : "text-muted"}`}>{text.length} / {MAX_CHARS}</span>
            <div className="flex items-center gap-3">
              <span className="hidden text-xs text-muted sm:inline" aria-hidden>
                <kbd className="rounded border border-line bg-surface2 px-1.5 py-0.5 font-sans">{IS_MAC ? "⌘" : "Ctrl"}</kbd>{" "}
                <kbd className="rounded border border-line bg-surface2 px-1.5 py-0.5 font-sans">Enter</kbd>
              </span>
              <button type="submit" disabled={busy || !text.trim()}
                className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-accent px-6 text-[15px] font-semibold text-white transition-colors hover:bg-accenthover disabled:cursor-not-allowed disabled:opacity-40">
                {busy && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/80 border-t-transparent" aria-hidden />}
                {busy ? "Translating…" : "Translate"}
              </button>
            </div>
          </div>
        </form>

        {/* Output */}
        <section aria-label="Translation" aria-live="polite" aria-busy={busy}
          className="flex min-h-[300px] min-w-0 flex-col border-t border-line bg-surface2 md:border-l md:border-t-0">
          <div className="flex items-center justify-between px-5 pt-4 sm:px-6">
            <span className="text-sm font-medium text-muted">{nameOf(tgt)}</span>
            {result && !busy && !error && (
              <span className="fade-up inline-flex items-center gap-1 text-xs font-medium text-good"><CheckIcon className="h-3.5 w-3.5" /> Translation ready</span>
            )}
          </div>

          <div className="flex flex-1 flex-col px-5 pb-5 pt-3 sm:px-6">
            {busy ? (
              <div className="flex flex-1 flex-col gap-3 pt-1" role="status">
                <span className="sr-only">Translating…</span>
                <div className="skeleton h-5 w-11/12 rounded-md" aria-hidden />
                <div className="skeleton h-5 w-9/12 rounded-md" aria-hidden />
                <div className="skeleton h-5 w-6/12 rounded-md" aria-hidden />
                <p className="mt-auto text-sm text-muted" aria-hidden>Translating…</p>
                {slow && <p className="text-sm text-muted">Still working. The first translation after the server starts can take longer.</p>}
              </div>
            ) : error ? (
              <div role="alert" className="fade-up flex flex-1 flex-col items-start gap-3 rounded-xl bg-badsoft p-4 text-bad">
                <div className="flex items-start gap-2"><AlertIcon className="mt-0.5 h-5 w-5 shrink-0" /><p className="leading-relaxed">{error}</p></div>
                {text.trim() && !tooMuchContext && (
                  <button type="button" onClick={translate}
                    className="rounded-lg border border-bad/30 bg-card px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:border-bad/60">
                    Try again
                  </button>
                )}
              </div>
            ) : result ? (
              <>
                <p className="fade-up flex-1 whitespace-pre-wrap text-xl leading-relaxed text-ink sm:text-[22px]" lang={tgt.slice(0, 2)} data-testid="translation">{result}</p>
                <div className="mt-4 flex items-center justify-end gap-3">
                  {copyFailed && <span className="text-xs text-bad">Copy failed. Select the text and copy it manually.</span>}
                  <button type="button" onClick={copy}
                    className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg border border-line bg-card px-3 text-sm font-medium text-ink transition-colors hover:border-linestrong">
                    {copied ? <CheckIcon className="h-4 w-4 text-good" /> : <CopyIcon className="h-4 w-4" />}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </>
            ) : (
              <div className="m-auto flex max-w-[260px] flex-col items-center gap-2 text-center text-muted">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-card text-muted shadow-soft" aria-hidden>
                  <SwapIcon className="h-5 w-5" />
                </span>
                <p>Your translation will appear here.</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
