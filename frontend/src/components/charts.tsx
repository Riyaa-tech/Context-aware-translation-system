// Charts follow the dataviz method: one axis, thin bars with 4px rounded ends, 2px surface gaps,
// selective direct labels, hover tooltips, and a table view for every chart (relief rule).
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { UNAVAILABLE } from "../lib/format";

type Row = { name: string; value: number | null; note?: string };

function TableToggle({ show, onToggle }: { show: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle} className="text-xs font-medium text-accent underline-offset-2 hover:underline" aria-pressed={show}>
      {show ? "Show chart" : "Show table"}
    </button>
  );
}

function TipBox({ label, rows }: { label: string; rows: { name: string; value: string; color: string }[] }) {
  return (
    <div className="rounded-lg border border-line bg-card px-3 py-2 text-sm shadow">
      <div className="mb-1 text-muted">{label}</div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3" style={{ background: r.color }} aria-hidden />
          <strong className="tabular-nums">{r.value}</strong>
          <span className="text-muted">{r.name}</span>
        </div>
      ))}
    </div>
  );
}

/** Horizontal bars for ONE measure across conditions. Null = unavailable (no bar, labelled). */
export function MetricBars({ title, rows, format, unit = "" }: { title: string; rows: Row[]; format: (v: number) => string; unit?: string }) {
  const [table, setTable] = useState(false);
  const data = rows.map((r) => ({ ...r, plot: r.value ?? 0, label: r.value === null ? UNAVAILABLE : format(r.value) }));
  const allNull = rows.every((r) => r.value === null);
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{title}{unit && <span className="text-muted"> ({unit})</span>}</span>
        <TableToggle show={table} onToggle={() => setTable(!table)} />
      </figcaption>
      {table || allNull ? (
        <table className="w-full text-sm">
          <tbody>
            {data.map((r) => (
              <tr key={r.name} className="border-t border-line">
                <td className="py-1 pr-2 font-mono text-xs">{r.name}</td>
                <td className={`py-1 text-right ${r.value === null ? "italic text-muted" : "tabular-nums"}`}>{r.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 34 + 30)}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 64, top: 4, bottom: 4 }} barCategoryGap={6}>
            <CartesianGrid horizontal={false} strokeWidth={1} />
            <XAxis type="number" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "var(--line)", opacity: 0.4 }}
              content={({ active, payload }) => active && payload?.length ? (
                <TipBox label={String(payload[0].payload.name)} rows={[{ name: title, value: payload[0].payload.label, color: "var(--series-1)" }]} />
              ) : null} />
            <Bar dataKey="plot" fill="var(--series-1)" radius={[0, 4, 4, 0]} stroke="var(--card)" strokeWidth={2} isAnimationActive={false}>
              <LabelList dataKey="label" position="right" style={{ fontSize: 11, fill: "var(--ink)" }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </figure>
  );
}

const DEC = [
  { key: "INTERVENE", name: "Intervene", color: "var(--series-1)" },
  { key: "ABSTAIN", name: "Abstain", color: "var(--series-2)" },
  { key: "PASS_THROUGH", name: "Pass through", color: "var(--series-3)" },
] as const;

/** Stacked controller decisions per condition (counts). */
export function DecisionStack({ rows }: { rows: { name: string; counts: Record<string, number> }[] }) {
  const [table, setTable] = useState(false);
  const data = rows.map((r) => ({ name: r.name, ...Object.fromEntries(DEC.map((d) => [d.key, r.counts[d.key] ?? 0])) }));
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Controller decisions per condition <span className="text-muted">(items)</span></span>
        <TableToggle show={table} onToggle={() => setTable(!table)} />
      </figcaption>
      {table ? (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted"><th className="py-1">Condition</th>{DEC.map((d) => <th key={d.key} className="py-1 text-right">{d.name}</th>)}</tr></thead>
          <tbody>{data.map((r: any) => (
            <tr key={r.name} className="border-t border-line"><td className="py-1 font-mono text-xs">{r.name}</td>
              {DEC.map((d) => <td key={d.key} className="py-1 text-right tabular-nums">{r[d.key]}</td>)}</tr>))}
          </tbody>
        </table>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(140, rows.length * 34 + 60)}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }} barCategoryGap={6}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "var(--line)", opacity: 0.4 }}
              content={({ active, payload, label }) => active && payload?.length ? (
                <TipBox label={String(label)} rows={DEC.map((d) => ({ name: d.name, value: String((payload[0].payload as any)[d.key]), color: d.color }))} />
              ) : null} />
            <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} formatter={(v) => <span style={{ color: "var(--ink)" }}>{v}</span>} />
            {DEC.map((d, i) => (
              <Bar key={d.key} dataKey={d.key} name={d.name} stackId="a" fill={d.color} stroke="var(--card)" strokeWidth={2}
                radius={i === DEC.length - 1 ? [0, 4, 4, 0] : 0} isAnimationActive={false}>
                <LabelList dataKey={d.key} position="center" style={{ fontSize: 11, fill: "#fff", fontWeight: 600 }}
                  formatter={(v: number) => (v >= 8 ? v : "")} />
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </figure>
  );
}
