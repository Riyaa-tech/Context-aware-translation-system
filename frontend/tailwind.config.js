/** Colours come from CSS variables in src/index.css (light + dark). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)", card: "var(--card)", line: "var(--line)", ink: "var(--ink)", muted: "var(--muted)",
        accent: "var(--accent)", s1: "var(--series-1)", s2: "var(--series-2)", s3: "var(--series-3)",
        good: "var(--good)", bad: "var(--bad)", warnbg: "var(--warn-bg)",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
