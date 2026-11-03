// Small inline icons (no icon package). All decorative: aria-hidden.
type P = { className?: string };
const base = (className = "h-4 w-4") => ({ className, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true });
export const SwapIcon = ({ className }: P) => <svg {...base(className)}><path d="M7 7h11l-3-3M17 17H6l3 3" /></svg>;
export const CopyIcon = ({ className }: P) => <svg {...base(className)}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></svg>;
export const CheckIcon = ({ className }: P) => <svg {...base(className)}><path d="m5 12 4.5 4.5L19 7" /></svg>;
export const AlertIcon = ({ className }: P) => <svg {...base(className)}><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5h.01" /></svg>;
export const ChevronIcon = ({ className }: P) => <svg {...base(className)}><path d="m6 9 6 6 6-6" /></svg>;
export const XIcon = ({ className }: P) => <svg {...base(className)}><path d="M6 6l12 12M18 6 6 18" /></svg>;
export const TranslateMark = ({ className }: P) => (
  <svg {...base(className)}><path d="M4 5h9M8.5 3v2M6 9c1.2 2.4 3.3 4.4 6 5.5M11 5c-.6 3.6-2.9 7-6.5 9" /><path d="M13 21l4-9 4 9M14.5 18h5" /></svg>
);
