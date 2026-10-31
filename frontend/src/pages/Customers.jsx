import { useEffect, useRef, useState } from "react";
import { useApi } from "../api.js";
import { GROUP_COPY, GROUP_ORDER, useDataset } from "../dataset.jsx";
import { fmt } from "../format.js";
import Explain from "../components/Explain.jsx";
import { EmptyState, ErrorState, NotReady, SkeletonBlock } from "../components/States.jsx";

const PAGE = 25;
const COLUMNS = [
  { id: "p0", label: "Chance without message", desc: "p0_desc", asc: "p0_asc" },
  { id: "p1", label: "Chance with message", desc: "p1_desc", asc: null },
  { id: "uplift", label: "Estimated effect", desc: "uplift_desc", asc: "uplift_asc" },
];
const PART_LABEL = { train: "Training", holdout: "Holdout", audience: "Unlabelled audience" };

function Drawer({ row, ds, reasonsMeta, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="drawer-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-h" tabIndex={-1} ref={ref}>
        <div className="drawer-head">
          <h2 id="drawer-h">
            Customer <span className="mono">{row.client_id}</span>
          </h2>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        <p>
          <span className={`swatch ${row.grp}`} aria-hidden="true" /> {GROUP_COPY[row.grp].label}{" "}
          <span className="muted">(estimated: {GROUP_COPY[row.grp].hint})</span>
        </p>
        <dl className="stats">
          <div>
            <dt>Chance without message</dt>
            <dd className="mono">{fmt.pct1(row.p0)}</dd>
          </div>
          <div>
            <dt>Chance with message</dt>
            <dd className="mono">{fmt.pct1(row.p1)}</dd>
          </div>
          <div>
            <dt>Estimated effect</dt>
            <dd className="mono">{fmt.pts(row.uplift)}</dd>
          </div>
        </dl>
        <h3>Main reasons for this estimate</h3>
        {row.reasons?.length ? (
          <ol className="reasons">
            {row.reasons.map((r) => (
              <li key={r.feature}>
                {r.text}
                <span className="muted mono"> ({fmt.pts(r.contrib)})</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">No reasons available.</p>
        )}
        <p className="fine">
          Each reason is one input’s pull on the estimated effect: how far this customer is from typical, times how
          differently that input predicts {ds.outcome_plural} with and without the {ds.channel === "Email" ? "email" : "SMS"}.
          “Typical” means the training average. Part of data: {PART_LABEL[row.part] ?? row.part}.
        </p>
        {reasonsMeta && <Explain dataset={ds.id} result={reasonsMeta} />}
      </aside>
    </div>
  );
}

export default function Customers() {
  const { ds, id } = useDataset();
  const [group, setGroup] = useState("");
  const [sort, setSort] = useState("uplift_desc");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const res = useApi(ds?.ready ? `/${id}/customers` : null, { group, sort, limit: PAGE, offset }, { cache: false });

  useEffect(() => setOffset(0), [group, sort, id]);

  if (!ds) return null;
  if (!ds.ready) return <NotReady ds={ds} />;

  const data = res.data;
  const rows = data?.page.rows ?? [];
  const total = data?.total ?? 0;

  const sortBy = (col) => {
    if (sort === col.desc && col.asc) setSort(col.asc);
    else setSort(col.desc);
  };
  const ariaSort = (col) => (sort === col.desc ? "descending" : sort === col.asc ? "ascending" : "none");

  return (
    <article className="page">
      <header className="page-head">
        <h1>Customers</h1>
        <p className="lede">
          Every scored customer with the model’s estimates. Groups are estimates, not observed behaviour.
          {ds.has_audience && " Unlabelled contest customers are included here only; they are never used to evaluate the model."}
        </p>
      </header>

      <div className="filters">
        <div className="segmented" role="radiogroup" aria-label="Filter by estimated group">
          <button type="button" role="radio" aria-checked={group === ""} className={group === "" ? "on" : ""} onClick={() => setGroup("")}>
            All
          </button>
          {GROUP_ORDER.map((g) => (
            <button key={g} type="button" role="radio" aria-checked={group === g} className={group === g ? "on" : ""} onClick={() => setGroup(g)}>
              <span className={`swatch ${g}`} aria-hidden="true" />
              {GROUP_COPY[g].label}
            </button>
          ))}
        </div>
      </div>

      {res.error && <ErrorState error={res.error} onRetry={res.reload} />}
      {res.loading && !data && <SkeletonBlock lines={8} />}
      {data && !rows.length && <EmptyState title="No customers in this group.">Try another group, or All.</EmptyState>}
      {data && rows.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="data clickable">
              <caption className="sr-only">Customers, sorted by {sort.replace("_", " ")}. Select a row for reasons.</caption>
              <thead>
                <tr>
                  <th scope="col">Customer</th>
                  <th scope="col">Estimated group</th>
                  {COLUMNS.map((c) => (
                    <th key={c.id} scope="col" className="num" aria-sort={ariaSort(c)}>
                      <button type="button" className="sort-btn" onClick={() => sortBy(c)}>
                        {c.label}
                        <span aria-hidden="true">{sort === c.desc ? " ↓" : sort === c.asc ? " ↑" : ""}</span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.client_id}>
                    <th scope="row">
                      <button type="button" className="row-btn mono" onClick={() => setOpen(r)}>
                        {r.client_id}
                      </button>
                    </th>
                    <td>
                      <span className={`swatch ${r.grp}`} aria-hidden="true" />
                      {GROUP_COPY[r.grp]?.label}
                    </td>
                    <td className="num mono">{fmt.pct1(r.p0)}</td>
                    <td className="num mono">{fmt.pct1(r.p1)}</td>
                    <td className="num mono">{fmt.pts(r.uplift)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button type="button" className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Previous
            </button>
            <span className="muted">
              {fmt.int(offset + 1)}–{fmt.int(offset + rows.length)} of {fmt.int(total)}
            </span>
            <button type="button" className="btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
              Next
            </button>
          </div>
          <Explain dataset={id} result={data.page} />
        </>
      )}
      {open && <Drawer row={open} ds={ds} reasonsMeta={data?.reasons} onClose={() => setOpen(null)} />}
    </article>
  );
}
