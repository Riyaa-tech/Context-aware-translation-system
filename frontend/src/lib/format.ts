// Missing values are shown as "unavailable" — never as 0 (spec Section 10, Page 3).
export const UNAVAILABLE = "unavailable";

export function fmt(v: number | null | undefined, digits = 1, suffix = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return UNAVAILABLE;
  return `${v.toFixed(digits)}${suffix}`;
}
export const pct = (v: number | null | undefined, digits = 1) => fmt(v === null || v === undefined ? v : v * 100, digits, "%");
export const ms = (v: number | null | undefined) => (v === null || v === undefined ? UNAVAILABLE : v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${v.toFixed(v < 10 ? 2 : 0)} ms`);
export const langName = (code: string, langs?: { code: string; name: string }[]) => langs?.find((l) => l.code === code)?.name ?? code;
