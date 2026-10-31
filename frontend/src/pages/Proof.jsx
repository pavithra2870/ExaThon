import { useState } from "react";
import { useApi } from "../api.js";
import { GROUP_COPY, GROUP_ORDER, useDataset } from "../dataset.jsx";
import { STRATEGIES } from "../curve.js";
import { bandText, fmt } from "../format.js";
import Explain from "../components/Explain.jsx";
import DecileBars from "../components/charts/DecileBars.jsx";
import { ErrorState, NotReady, SkeletonBlock } from "../components/States.jsx";

const BUDGETS = [5, 10, 20, 30, 50];
const VERDICT_TEXT = {
  better: "Uplift targeting did better; the band is above zero.",
  worse: "Uplift targeting did worse; the band is below zero.",
  inconclusive: "Inconclusive: the band includes zero.",
};

export default function Proof() {
  const { ds, id } = useDataset();
  const [budget, setBudget] = useState(20);
  const proof = useApi(ds?.ready ? `/${id}/proof` : null, { budget });

  if (!ds) return null;
  if (!ds.ready) return <NotReady ds={ds} />;

  const p = proof.data;
  const at = p ? Object.fromEntries(p.at_budget.rows.map((r) => [r.strategy, r])) : {};
  const holdout = p?.summary.rows.find((r) => r.part === "holdout");
  const qini = p ? Object.fromEntries(p.qini.rows.map((r) => [r.strategy, r])) : {};
  const groups = p ? Object.fromEntries(p.groups.rows.map((r) => [r.grp, r])) : {};

  return (
    <article className="page">
      <header className="page-head">
        <h1>Proof on held-out customers</h1>
        <p className="lede">
          The models never saw these customers. Each one was randomly messaged or not in the original experiment, so
          comparing messaged and not-messaged customers inside any group gives an honest estimate of the message’s effect
          there.
        </p>
      </header>

      <div className="segmented budget-pick" role="radiogroup" aria-label="Share contacted">
        {BUDGETS.map((b) => (
          <button key={b} type="button" role="radio" aria-checked={budget === b} className={budget === b ? "on" : ""} onClick={() => setBudget(b)}>
            Top {b}%
          </button>
        ))}
      </div>

      {proof.error && <ErrorState error={proof.error} onRetry={proof.reload} />}
      {proof.loading && !p && <SkeletonBlock lines={6} />}
      {p && (
        <>
          <section className="panel" aria-labelledby="cmp-h">
            <h2 id="cmp-h">Head to head at {budget}% contacted</h2>
            <p className="lede">
              Holdout: {fmt.int(holdout?.n)} customers. Messaged {fmt.pct2(holdout?.treated_rate)} {ds.outcome}{" "}
              rate vs {fmt.pct2(holdout?.control_rate)} for those not messaged.
            </p>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Strategy</th>
                    <th scope="col" className="num">
                      Extra {ds.outcome_plural} per 1,000
                    </th>
                    <th scope="col" className="num">
                      95% band
                    </th>
                    <th scope="col" className="num">
                      Est. share who’d act anyway
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {STRATEGIES.map((s) => (
                    <tr key={s.id}>
                      <th scope="row">
                        <span className={`key ${s.className}`} aria-hidden="true" />
                        {s.label}
                      </th>
                      <td className="num mono">{fmt.signed(at[s.id]?.per_1000)}</td>
                      <td className="num mono">{bandText(at[s.id]?.lo, at[s.id]?.hi)}</td>
                      <td className="num mono">{fmt.pct(at[s.id]?.share_anyway)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Explain dataset={id} result={p.at_budget} />

            <ul className="verdicts">
              {p.comparison.rows.map((r) => (
                <li key={r.versus} className={`verdict v-${r.verdict}`}>
                  <p className="verdict-head">
                    Uplift model vs {r.versus === "random" ? "random" : "likely buyers"}:{" "}
                    <span className="mono">{fmt.signed(r.diff_per_1000)}</span> per 1,000
                    <span className="verdict-band mono"> (95% band {bandText(r.lo, r.hi)})</span>
                  </p>
                  <p className="verdict-text">{VERDICT_TEXT[r.verdict]}</p>
                </li>
              ))}
            </ul>
            <Explain dataset={id} result={p.comparison} note="The band comes from 200 bootstrap resamples of the holdout (fixed seed); the resampling runs in Python and the bands are stored in Exasol." />
          </section>

          <section className="panel" aria-labelledby="dec-h">
            <h2 id="dec-h">Does the ranking hold up? Observed effect by decile</h2>
            <p className="lede">
              Holdout customers split into ten equal groups by estimated uplift. Bars are the observed difference between
              messaged and not-messaged customers; whiskers are 95% bands; the dark tick is what the model predicted. A
              good model shows taller bars on the left.
            </p>
            <DecileBars rows={p.deciles.rows} />
            <Explain dataset={id} result={p.deciles} />
            <details className="table-details">
              <summary>Show the decile table</summary>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th scope="col">Decile</th>
                      <th scope="col" className="num">Customers</th>
                      <th scope="col" className="num">Messaged rate</th>
                      <th scope="col" className="num">Not messaged rate</th>
                      <th scope="col" className="num">Observed uplift</th>
                      <th scope="col" className="num">Predicted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.deciles.rows.map((r) => (
                      <tr key={r.decile}>
                        <th scope="row">{r.decile}</th>
                        <td className="num mono">{fmt.int(r.n)}</td>
                        <td className="num mono">{fmt.pct2(r.treated_rate)}</td>
                        <td className="num mono">{fmt.pct2(r.control_rate)}</td>
                        <td className="num mono">{fmt.pts(r.observed_uplift)}</td>
                        <td className="num mono">{fmt.pts(r.predicted_uplift)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </section>

          <section className="panel" aria-labelledby="grp-h">
            <h2 id="grp-h">Do the estimated groups behave as labelled?</h2>
            <p className="lede">Groups come from model estimates. The right-hand columns are what actually happened to holdout customers in each group.</p>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Estimated group</th>
                    <th scope="col" className="num">All customers</th>
                    <th scope="col" className="num">Est. uplift</th>
                    <th scope="col" className="num">Holdout: messaged</th>
                    <th scope="col" className="num">Holdout: not messaged</th>
                    <th scope="col" className="num">Observed difference</th>
                  </tr>
                </thead>
                <tbody>
                  {GROUP_ORDER.filter((g) => groups[g]).map((g) => {
                    const r = groups[g];
                    const diff = r.holdout_treated_rate != null && r.holdout_control_rate != null ? r.holdout_treated_rate - r.holdout_control_rate : null;
                    return (
                      <tr key={g}>
                        <th scope="row">
                          <span className={`swatch ${g}`} aria-hidden="true" />
                          {GROUP_COPY[g].label}
                        </th>
                        <td className="num mono">
                          {fmt.int(r.n)} <span className="muted">({fmt.pct(r.share)})</span>
                        </td>
                        <td className="num mono">{fmt.pts(r.mean_uplift)}</td>
                        <td className="num mono">{fmt.pct2(r.holdout_treated_rate)}</td>
                        <td className="num mono">{fmt.pct2(r.holdout_control_rate)}</td>
                        <td className="num mono">{fmt.pts(diff)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Explain dataset={id} result={p.groups} />
          </section>

          <section className="panel" aria-labelledby="qini-h">
            <h2 id="qini-h">Qini score</h2>
            <p className="lede">
              Average gap between a strategy’s cumulative extra {ds.outcome_plural} and random contact, across all budgets,
              as a share of the holdout. Higher is better; zero means no better than random.
            </p>
            <dl className="stats">
              {["uplift", "likely_buyers"].map((s) => (
                <div key={s}>
                  <dt>{STRATEGIES.find((x) => x.id === s).short}</dt>
                  <dd className="mono">{fmt.signed(qini[s]?.qini_coefficient * 1000)} per 1,000 customers</dd>
                </div>
              ))}
            </dl>
            <Explain dataset={id} result={p.qini} />
          </section>

          <aside className="cannot" aria-labelledby="cannot-h">
            <h2 id="cannot-h">What this can’t tell you</h2>
            <ul>
              <li>
                These are past {ds.channel === "Email" ? "email" : "SMS"} campaigns, not price offers. A different message,
                channel, season or country can behave differently.
              </li>
              <li>Groups and “would act anyway” are model estimates for individuals; only group averages are observed.</li>
              <li>Bands show sampling uncertainty in the holdout. They do not cover a model that is wrong in a systematic way.</li>
              <li>Results count {ds.outcome_plural}, not revenue or profit. A strategy can win on counts and lose on margin.</li>
              <li>The data are public research datasets from the US and Russia. They are not Indian customers.</li>
              {ds.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </aside>
        </>
      )}
    </article>
  );
}
