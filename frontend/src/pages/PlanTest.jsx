import { useEffect, useState } from "react";
import { useApi } from "../api.js";
import { useDataset } from "../dataset.jsx";
import { fmt } from "../format.js";
import Explain from "../components/Explain.jsx";
import { ErrorState } from "../components/States.jsx";

function useDebounced(value, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function PlanTest() {
  const { ds, id } = useDataset();
  const [baseline, setBaseline] = useState("10");
  const [effect, setEffect] = useState("1");
  const [power, setPower] = useState("0.8");
  const [alpha, setAlpha] = useState("0.05");
  const summary = useApi(ds?.ready ? `/${id}/overview` : null, { budget: 20 });

  const inputs = useDebounced({ baseline, effect, power, alpha });
  const b = Number(inputs.baseline) / 100;
  const e = Number(inputs.effect) / 100;
  const valid = b > 0 && b < 1 && e !== 0 && b + e > 0 && b + e < 1;
  const plan = useApi(valid ? "/plan-test" : null, { baseline: b, effect: e, power: inputs.power, alpha: inputs.alpha });

  const holdout = summary.data?.summary.rows.find((r) => r.part === "holdout");

  return (
    <article className="page narrow">
      <header className="page-head">
        <h1>Plan a test</h1>
        <p className="lede">
          How many customers you need in each group (messaged and not messaged) to reliably detect a given change in the
          rate of people who act. Uses a two-sided test of two proportions.
        </p>
      </header>

      <form className="plan" onSubmit={(ev) => ev.preventDefault()}>
        <div className="field">
          <label htmlFor="baseline">Rate without the message</label>
          <div className="input-suffix">
            <input id="baseline" type="number" inputMode="decimal" min="0.01" max="99.99" step="0.1" value={baseline} onChange={(ev) => setBaseline(ev.target.value)} />
            <span>%</span>
          </div>
          {holdout?.control_rate != null && (
            <button type="button" className="link-btn" onClick={() => setBaseline((holdout.control_rate * 100).toFixed(2))}>
              Use {ds.name} control rate ({fmt.pct2(holdout.control_rate)})
            </button>
          )}
          {summary.data && <Explain dataset={id} result={summary.data.summary} />}
        </div>
        <div className="field">
          <label htmlFor="effect">Smallest change worth detecting</label>
          <div className="input-suffix">
            <input id="effect" type="number" inputMode="decimal" step="0.1" value={effect} onChange={(ev) => setEffect(ev.target.value)} />
            <span>points</span>
          </div>
          <p className="field-hint">Absolute change, e.g. 1 point takes 10% to 11%.</p>
        </div>
        <div className="field">
          <label htmlFor="power">Chance of detecting a real change (power)</label>
          <select id="power" value={power} onChange={(ev) => setPower(ev.target.value)}>
            <option value="0.8">80%</option>
            <option value="0.9">90%</option>
            <option value="0.95">95%</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="alpha">False alarm rate (alpha)</label>
          <select id="alpha" value={alpha} onChange={(ev) => setAlpha(ev.target.value)}>
            <option value="0.1">10%</option>
            <option value="0.05">5%</option>
            <option value="0.01">1%</option>
          </select>
        </div>
      </form>

      <section className="plan-result" aria-live="polite">
        {!valid && <p className="state-hint">Enter a rate between 0 and 100% and a non-zero change that keeps it within 0 to 100%.</p>}
        {valid && plan.error && <ErrorState error={plan.error} />}
        {valid && plan.data && (
          <>
            <p className="plan-n">
              <span className="mono">{fmt.int(plan.data.n_per_arm)}</span> customers per group
            </p>
            <p>
              {fmt.int(plan.data.n_total)} in total, split evenly between messaged and not messaged, to detect a change from{" "}
              {fmt.pct2(plan.data.baseline)} to {fmt.pct2(plan.data.baseline + plan.data.effect)}.
            </p>
            <p className="fine mono">{plan.data.formula}</p>
          </>
        )}
      </section>
    </article>
  );
}
