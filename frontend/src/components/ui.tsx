import { ReactNode } from "react";
import type { Decision } from "../lib/api";
import { UNAVAILABLE } from "../lib/format";

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-card p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

const DECISION_STYLE: Record<Decision, { label: string; icon: string; dot: string }> = {
  INTERVENE: { label: "Intervened", icon: "✎", dot: "bg-s1" },
  ABSTAIN: { label: "Abstained", icon: "⏸", dot: "bg-s2" },
  PASS_THROUGH: { label: "Passed through", icon: "→", dot: "bg-s3" },
};
export function DecisionBadge({ d }: { d: Decision }) {
  const s = DECISION_STYLE[d];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-sm font-medium">
      <span className={`h-2 w-2 rounded-full ${s.dot}`} aria-hidden /> <span aria-hidden>{s.icon}</span> {s.label}
    </span>
  );
}

export function Value({ v }: { v: string }) {
  return v === UNAVAILABLE ? <span className="text-sm italic text-muted" title="Not measured yet">unavailable</span> : <span className="tabular-nums">{v}</span>;
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="mt-3 rounded-lg border border-bad/40 px-3 py-2 text-sm text-bad">{error}</p>;
}

export function Notice({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-line bg-warnbg px-3 py-2 text-sm">{children}</div>;
}

export function Button({ children, primary, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean }) {
  return (
    <button {...p} className={`rounded-lg border px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
      primary ? "border-accent bg-accent text-white hover:brightness-110" : "border-line bg-card hover:border-accent"} ${p.className ?? ""}`}>
      {children}
    </button>
  );
}

export const inputCls = "w-full rounded-lg border border-line bg-card px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none";

export function Spinner({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-muted"><span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />{label}</span>;
}
