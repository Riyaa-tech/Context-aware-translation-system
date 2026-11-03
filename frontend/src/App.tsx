import { useRef } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { TranslateMark } from "./components/icons";
import { StateProvider } from "./state";
import TranslatePage from "./pages/Translate";
import PipelinePage from "./pages/Pipeline";
import ExperimentsPage from "./pages/Experiments";
import AnnotatePage from "./pages/Annotate";
import DashboardPage from "./pages/Dashboard";

// Research tools stay available, but out of the main translation workflow.
const RESEARCH = [
  { to: "/pipeline", label: "Pipeline", hint: "How the last translation was made" },
  { to: "/experiments", label: "Experiments", hint: "Compare system conditions" },
  { to: "/annotate", label: "Annotate", hint: "Rate translations" },
  { to: "/dashboard", label: "Dashboard", hint: "Runs, datasets and results" },
];

function ResearchMenu() {
  const ref = useRef<HTMLDetailsElement>(null);
  const { pathname } = useLocation();
  const active = RESEARCH.some((r) => r.to === pathname);
  return (
    <details ref={ref} className="group relative">
      <summary className={`flex cursor-pointer list-none items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors hover:bg-card hover:text-ink [&::-webkit-details-marker]:hidden ${active ? "bg-card text-ink shadow-soft" : "text-muted"}`}>
        Research ▾
      </summary>
      <div className="fade-up absolute right-0 z-20 mt-2 w-64 rounded-xl border border-line bg-card p-1.5 shadow-pop">
        {RESEARCH.map((r) => (
          <NavLink key={r.to} to={r.to} onClick={() => ref.current?.removeAttribute("open")}
            aria-label={r.label} aria-describedby={`hint-${r.label}`}
            className={({ isActive }) => `block rounded-lg px-3 py-2 transition-colors hover:bg-surface2 ${isActive ? "bg-surface2" : ""}`}>
            <span className="block text-sm font-medium text-ink">{r.label}</span>
            <span id={`hint-${r.label}`} className="block text-xs text-muted">{r.hint}</span>
          </NavLink>
        ))}
      </div>
    </details>
  );
}

export default function App() {
  // Header width follows the page: the translator is narrower than the research pages.
  const wide = useLocation().pathname !== "/";
  return (
    <StateProvider>
      <header className={wide ? "" : "px-4"}>
        <div className={`mx-auto flex items-center justify-between py-4 sm:py-5 ${wide ? "max-w-6xl px-4" : "max-w-5xl"}`}>
          <Link to="/" className="flex items-center gap-2.5 text-ink" aria-label="Translator">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white"><TranslateMark className="h-[18px] w-[18px]" /></span>
            <span className="text-[17px] font-semibold tracking-tight">Translator</span>
          </Link>
          <nav className="flex items-center gap-1" aria-label="Main">
            <NavLink to="/" end className={({ isActive }) => `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors hover:bg-card hover:text-ink ${isActive ? "bg-card text-ink shadow-soft" : "text-muted"}`}>
              Translate
            </NavLink>
            <ResearchMenu />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-12 pt-2 sm:pt-6">
        <Routes>
          <Route path="/" element={<TranslatePage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/annotate" element={<AnnotatePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
    </StateProvider>
  );
}
