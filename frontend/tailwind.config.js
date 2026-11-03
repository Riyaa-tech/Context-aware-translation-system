/** Colours come from CSS variables in src/index.css (light + dark). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)", card: "var(--card)", surface2: "var(--surface-2)", line: "var(--line)", linestrong: "var(--line-strong)",
        ink: "var(--ink)", muted: "var(--muted)", accent: "var(--accent)", accenthover: "var(--accent-hover)", accentsoft: "var(--accent-soft)",
        s1: "var(--series-1)", s2: "var(--series-2)", s3: "var(--series-3)",
        good: "var(--good)", bad: "var(--bad)", badsoft: "var(--bad-soft)", warnbg: "var(--warn-bg)",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Devanagari", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: { soft: "0 1px 2px rgba(16,16,20,0.04), 0 1px 1px rgba(16,16,20,0.03)", pop: "0 8px 24px rgba(16,16,20,0.10)" },
    },
  },
  plugins: [],
};
