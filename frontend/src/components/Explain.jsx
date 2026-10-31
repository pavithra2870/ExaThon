import { useEffect, useId, useRef, useState } from "react";
import { get } from "../api.js";
import { fmt } from "../format.js";

/** "How this was computed": query id, timing, and the SQL text fetched from /trace. */
export default function Explain({ dataset, result, metric, note }) {
  const [open, setOpen] = useState(false);
  const [sql, setSql] = useState(null);
  const [err, setErr] = useState(null);
  const panelId = useId();
  const wrap = useRef(null);
  const name = metric ?? result?.metric;

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    const onClick = (e) => wrap.current && !wrap.current.contains(e.target) && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  useEffect(() => {
    setSql(null);
    setErr(null);
  }, [dataset, name]);

  useEffect(() => {
    if (!open || sql || !dataset || !name) return;
    get(`/${dataset}/trace`, { metric: name })
      .then((t) => setSql(t.sql))
      .catch((e) => setErr(e));
  }, [open, sql, dataset, name]);

  if (!result) return null;
  return (
    <span className="explain" ref={wrap}>
      <button
        type="button"
        className="explain-btn"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        How this was computed
      </button>
      {open && (
        <div className="explain-panel" id={panelId} role="dialog" aria-label="How this was computed">
          <dl className="explain-meta">
            <div>
              <dt>Query</dt>
              <dd className="mono">{name}</dd>
            </div>
            <div>
              <dt>query_id</dt>
              <dd className="mono" title={result.query_id}>
                {result.query_id?.slice(0, 16)}…
              </dd>
            </div>
            <div>
              <dt>Ran in Exasol</dt>
              <dd className="mono">
                {fmt.ms(result.elapsed_ms)}
                {result.cached ? " (cached)" : ""}
              </dd>
            </div>
          </dl>
          {note && <p className="explain-note">{note}</p>}
          {err && <p className="explain-note">Could not load the SQL: {err.message}</p>}
          {!err && !sql && <p className="explain-note">Loading SQL…</p>}
          {sql && <pre className="sql" tabIndex={0}>{sql}</pre>}
        </div>
      )}
    </span>
  );
}
