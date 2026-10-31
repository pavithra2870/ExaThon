import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../api.js";
import { useDataset } from "../dataset.jsx";
import { STRATEGIES, actionVerb, byStrategy, rowAt } from "../curve.js";
import { bandText, fmt, verdictOf } from "../format.js";
import Explain from "../components/Explain.jsx";
import LineChart from "../components/charts/LineChart.jsx";
import StackedBar from "../components/charts/StackedBar.jsx";
import { ErrorState, NotReady, Skeleton, SkeletonBlock } from "../components/States.jsx";

function useBudget() {
  const [params, setParams] = useSearchParams();
  const n = Math.min(100, Math.max(1, Number.parseInt(params.get("n") ?? "20", 10) || 20));
  const set = (v) => {
    const next = new URLSearchParams(params);
    next.set("n", String(v));
    setParams(next, { replace: true });
  };
  return [n, set];
}

function Readout({ strategy, row, ds, highlight }) {
  const verdict = verdictOf(row?.lo, row?.hi);
  const isRandom = strategy.id === "random";
  return (
    <div className={`readout ${highlight ? "readout-lead" : ""}`}>
      <h3 className="readout-label">
        <span className={`key ${strategy.className}`} aria-hidden="true" />
        {strategy.label}
      </h3>
      <p className="readout-value mono">{fmt.signed(row?.per_1000)}</p>
      <p className="readout-unit">extra {ds.outcome_plural} per 1,000 contacted</p>
      <p className="readout-band">
        95% band: <span className="mono">{bandText(row?.lo, row?.hi)}</span>
      </p>
      {verdict === "inconclusive" && Number.isFinite(row?.lo) && (
        <p className="readout-flag">Inconclusive: the band includes zero.</p>
      )}
      {isRandom && <p className="readout-note">Same at every budget: the average effect across the holdout.</p>}
    </div>
  );
}

export default function Overview() {
  const { ds, id } = useDataset();
  const [budget, setBudget] = useBudget();
  const [mix, setMix] = useState("uplift");
  const curve = useApi(ds?.ready ? `/${id}/curve` : null);
  const summary = useApi(ds?.ready ? `/${id}/overview` : null, { budget: 20 });

  const series = useMemo(() => {
    const by = byStrategy(curve.data?.rows);
    return STRATEGIES.map((s) => ({
      ...s,
      rows: by[s.id] ?? [],
      points: (by[s.id] ?? []).map((r) => ({ x: Number(r.k), y: r.per_1000, lo: r.lo, hi: r.hi })),
    }));
  }, [curve.data]);

  if (!ds) return null;
  if (!ds.ready) return <NotReady ds={ds} />;
  if (curve.error) return <ErrorState error={curve.error} onRetry={curve.reload} />;

  const at = Object.fromEntries(series.map((s) => [s.id, rowAt(s.rows, budget)]));
  const holdout = summary.data?.summary.rows.find((r) => r.part === "holdout");
  const verb = actionVerb(ds);
  const mixRow = at[mix];
  const counts = mixRow
    ? { tipped: mixRow.g_tipped_k, anyway: mixRow.g_anyway_k, never: mixRow.g_never_k, put_off: mixRow.g_put_off_k }
    : null;

  return (
    <article className="page">
      <section className="hero" aria-labelledby="hero-q">
        <h1 id="hero-q" className="hero-q">
          Send the {ds.channel === "Email" ? "email" : "SMS"} to the top
          <output className="hero-n mono" htmlFor="budget">
            {budget}%
          </output>
          of customers
        </h1>
        <div className="slider-wrap">
          <input
            id="budget"
            type="range"
            min={1}
            max={100}
            step={1}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            aria-label="Share of customers to contact"
            aria-valuetext={`${budget}% of customers`}
            style={{ "--fill": `${budget}%` }}
            className="slider"
          />
          <div className="slider-ticks" aria-hidden="true">
            {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((t) => (
              <span key={t} style={{ left: `${t}%` }}>
                {t}
              </span>
            ))}
          </div>
        </div>
        <p className="hero-sub">
          Measured on {holdout ? fmt.int(holdout.n) : "…"} customers held out from training. In that group, {budget}% is{" "}
          {fmt.int(at.uplift?.n_k)} people.
        </p>
      </section>

      {curve.loading || !curve.data ? (
        <SkeletonBlock lines={4} />
      ) : (
        <>
          <section className="readouts" aria-label={`Results at ${budget}% contacted`}>
            {STRATEGIES.map((s) => (
              <Readout key={s.id} strategy={s} row={at[s.id]} ds={ds} highlight={s.id === "uplift"} />
            ))}
          </section>
          <div className="explain-row">
            <Explain dataset={id} result={curve.data} note="One query returns all three strategies at every budget; the slider reads from it." />
          </div>

          <section className="headline" aria-label="Messages to people who would act anyway">
            <p>
              Targeting likely buyers, an estimated{" "}
              <strong className="mono">{fmt.pct(at.likely_buyers?.share_anyway)}</strong> of messages at {budget}% go to
              people who would {verb} anyway. Targeting by uplift, it is{" "}
              <strong className="mono">{fmt.pct(at.uplift?.share_anyway)}</strong>.
            </p>
            <p className="fine">
              “Would {verb} anyway” is the model’s estimated chance of acting without the message, averaged over the people
              contacted. It is an estimate, not an observed count.
            </p>
          </section>

          <section className="panel" aria-labelledby="curve-h">
            <h2 id="curve-h">Extra {ds.outcome_plural} per 1,000 contacted, by budget</h2>
            <p className="lede">
              Shaded areas are 95% bootstrap bands. Click the chart, or focus it and use the arrow keys, to read or set a
              budget.
            </p>
            <LineChart
              series={series.filter((s) => s.points.length)}
              marker={budget}
              onPick={setBudget}
              ariaLabel={`Extra ${ds.outcome_plural} per 1,000 contacted for three targeting strategies`}
              yLabel={`extra ${ds.outcome_plural} per 1,000`}
              formatY={(v) => fmt.one(v)}
              formatTip={(s, p) => `${s.short}: ${fmt.signed(p.y)} (${bandText(p.lo, p.hi)})`}
            />
            <ul className="chart-legend">
              {STRATEGIES.map((s) => (
                <li key={s.id}>
                  <span className={`key ${s.className}`} aria-hidden="true" />
                  {s.label}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel" aria-labelledby="mix-h">
            <div className="panel-head">
              <h2 id="mix-h">Who you would contact at {budget}%</h2>
              <div className="segmented" role="radiogroup" aria-label="Targeting strategy">
                {STRATEGIES.filter((s) => s.id !== "random").map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    role="radio"
                    aria-checked={mix === s.id}
                    className={mix === s.id ? "on" : ""}
                    onClick={() => setMix(s.id)}
                  >
                    {s.short}
                  </button>
                ))}
              </div>
            </div>
            <p className="lede">
              Estimated groups among the holdout customers each strategy would contact. A customer is “tipped” or “put
              off” when the estimated effect is at least {fmt.one(ds.u * 100)} percentage point either way; “would act anyway” when the
              estimated chance without a message is {fmt.pct(ds.p0_cut)} or more.
            </p>
            {counts ? <StackedBar counts={counts} /> : <Skeleton height={36} />}
          </section>
        </>
      )}
    </article>
  );
}
