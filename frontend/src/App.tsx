import { useRef } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { StateProvider } from "./state";
import TranslatePage from "./pages/Translate";
import PipelinePage from "./pages/Pipeline";
import ExperimentsPage from "./pages/Experiments";
import AnnotatePage from "./pages/Annotate";
import DashboardPage from "./pages/Dashboard";

// Research tools stay available, but out of the main translation workflow.
const RESEARCH = [
  { to: "/pipeline", label: "Pipeline" },
  { to: "/experiments", label: "Experiments" },
  { to: "/annotate", label: "Annotate" },
  { to: "/dashboard", label: "Dashboard" },
];

function ResearchMenu() {
  const ref = useRef<HTMLDetailsElement>(null);
  const { pathname } = useLocation();
  const active = RESEARCH.some((r) => r.to === pathname);
  return (
    <details ref={ref} className="relative">
      <summary className={`cursor-pointer list-none rounded-md px-3 py-1.5 text-sm hover:text-ink ${active ? "text-ink" : "text-muted"}`}>
        Research ▾
      </summary>
      <div className="absolute right-0 z-10 mt-1 w-44 rounded-lg border border-line bg-card py-1 shadow-lg">
        {RESEARCH.map((r) => (
          <NavLink key={r.to} to={r.to} onClick={() => ref.current?.removeAttribute("open")}
            className={({ isActive }) => `block px-4 py-2 text-sm hover:bg-page ${isActive ? "font-semibold text-ink" : "text-muted"}`}>
            {r.label}
          </NavLink>
        ))}
      </div>
    </details>
  );
}

export default function App() {
  return (
    <StateProvider>
      <header className="px-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between py-5">
          <Link to="/" className="text-lg font-semibold tracking-tight text-ink">Translator</Link>
          <nav className="flex items-center gap-1" aria-label="Main">
            <NavLink to="/" end className={({ isActive }) => `rounded-md px-3 py-1.5 text-sm hover:text-ink ${isActive ? "text-ink" : "text-muted"}`}>
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
