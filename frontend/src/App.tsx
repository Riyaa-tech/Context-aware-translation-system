import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./lib/api";
import { StateProvider } from "./state";
import TranslatePage from "./pages/Translate";
import PipelinePage from "./pages/Pipeline";
import ExperimentsPage from "./pages/Experiments";
import AnnotatePage from "./pages/Annotate";
import DashboardPage from "./pages/Dashboard";

const NAV = [
  { to: "/", label: "Translate" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/experiments", label: "Experiments" },
  { to: "/annotate", label: "Annotate" },
  { to: "/dashboard", label: "Dashboard" },
];

function Health() {
  const [h, setH] = useState<{ ok: boolean; loaded?: boolean } | null>(null);
  useEffect(() => {
    api<{ status: string; model_loaded: boolean }>("/health").then((r) => setH({ ok: r.status === "ok", loaded: r.model_loaded })).catch(() => setH({ ok: false }));
  }, []);
  if (!h) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className={`h-2 w-2 rounded-full ${h.ok ? "bg-good" : "bg-bad"}`} aria-hidden />
      {h.ok ? (h.loaded ? "Backend ready · model loaded" : "Backend ready · model loads on first request") : "Backend offline"}
    </span>
  );
}

export default function App() {
  return (
    <StateProvider>
      <header className="border-b border-line bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="mr-auto">
            <div className="text-sm font-semibold">Context-Aware NMT</div>
            <div className="text-xs text-muted">NLLB-200 (unchanged) + selective semantic modules · research prototype</div>
          </div>
          <nav className="flex flex-wrap gap-1" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? "bg-accent text-white" : "text-ink hover:bg-page"}`}>{n.label}</NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-4 flex justify-end"><Health /></div>
        <Routes>
          <Route path="/" element={<TranslatePage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/annotate" element={<AnnotatePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-muted">
        All values come from the backend: real model outputs, stored experiment runs and human annotations. Nothing is simulated.
        NLLB-200 is licensed CC-BY-NC 4.0 (research use).
      </footer>
    </StateProvider>
  );
}
