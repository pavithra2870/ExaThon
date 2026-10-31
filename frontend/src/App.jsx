import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useApi } from "./api.js";
import { DatasetsContext, useDataset } from "./dataset.jsx";
import { ErrorState, Skeleton } from "./components/States.jsx";
import Overview from "./pages/Overview.jsx";
import Proof from "./pages/Proof.jsx";
import Customers from "./pages/Customers.jsx";
import PlanTest from "./pages/PlanTest.jsx";
import Method from "./pages/Method.jsx";

const PAGES = [
  { to: "/", label: "Overview", end: true },
  { to: "/proof", label: "Proof" },
  { to: "/customers", label: "Customers" },
  { to: "/plan", label: "Plan a test" },
  { to: "/method", label: "Method" },
];

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("promolens-theme");
    } catch {
      return null;
    }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try {
      if (theme) localStorage.setItem("promolens-theme", theme);
      else localStorage.removeItem("promolens-theme");
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  const systemDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  const effective = theme ?? (systemDark ? "dark" : "light");
  return [effective, () => setTheme(effective === "dark" ? "light" : "dark")];
}

function Header() {
  const { ds, setDataset, list } = useDataset();
  const location = useLocation();
  const [theme, toggleTheme] = useTheme();
  return (
    <header className="masthead">
      <div className="masthead-row">
        <a className="brand" href={`/${location.search}`}>
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
            <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" strokeWidth="3.5" />
            <path d="M5 25 L27 7" stroke="currentColor" strokeWidth="2.5" />
          </svg>
          PromoLens
        </a>
        <label className="ds-switch">
          <span className="sr-only">Dataset</span>
          <select value={ds?.id ?? ""} onChange={(e) => setDataset(e.target.value)} disabled={!list.length}>
            {list.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
                {d.ready ? "" : " (not processed)"}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="theme-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>
      <nav aria-label="Main">
        <ul className="nav">
          {PAGES.map((p) => (
            <li key={p.to}>
              <NavLink to={{ pathname: p.to, search: location.search }} end={p.end}>
                {p.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {ds && (
        <p className="ds-note">
          <span className="ds-channel">{ds.channel} test.</span> {ds.note}
        </p>
      )}
    </header>
  );
}

export default function App() {
  const datasets = useApi("/datasets");
  const ctx = { list: datasets.data ?? [], loading: datasets.loading, error: datasets.error };

  return (
    <DatasetsContext.Provider value={ctx}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <Header />
        <main id="main" tabIndex={-1}>
          {datasets.loading && <Skeleton height={240} label="Loading datasets" />}
          {datasets.error && <ErrorState error={datasets.error} onRetry={datasets.reload} />}
          {datasets.data && (
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/proof" element={<Proof />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/plan" element={<PlanTest />} />
              <Route path="/method" element={<Method />} />
              <Route path="*" element={<ErrorState error={{ message: "There is no page here.", hint: "Use the menu above." }} />} />
            </Routes>
          )}
        </main>
        <footer className="foot">
          <p>
            Every number on these pages comes from a SQL query in Exasol; use “How this was computed” to see it. Groups and
            “would act anyway” are model estimates. Data are public research datasets, not Indian customers. MIT licence.
          </p>
        </footer>
      </div>
    </DatasetsContext.Provider>
  );
}
