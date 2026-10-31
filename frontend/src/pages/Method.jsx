import { useApi } from "../api.js";
import { useDataset } from "../dataset.jsx";
import { fmt } from "../format.js";

export default function Method() {
  const { list } = useDataset();
  const health = useApi("/health", undefined, { cache: false });

  return (
    <article className="page narrow prose">
      <header className="page-head">
        <h1>Method and assumptions</h1>
        <p className="lede">Short, plain, and honest about what the numbers mean.</p>
      </header>

      <h2>The question</h2>
      <p>
        A message only earns its keep with people it changes. Some customers act anyway; some won’t act whatever you send.
        PromoLens estimates, per customer, the chance of acting with and without the message, and ranks people by the
        difference (the estimated effect, or uplift).
      </p>

      <h2>The data</h2>
      <p>
        Each dataset is a past randomised experiment: customers were split at random into a group that got an SMS or email
        and a group that did not. Randomisation is what makes the comparison fair. None of these are price offers, and none
        are Indian customers.
      </p>
      <ul>
        {list.map((d) => (
          <li key={d.id}>
            <strong>{d.name}.</strong> {d.note} <span className="muted">Source: {d.source}.</span>
          </li>
        ))}
      </ul>

      <h2>The model</h2>
      <ol>
        <li>Customers are split 70/30 by a hash of their id. The 30% holdout is not touched until evaluation.</li>
        <li>
          Two logistic regressions are trained on the 70%: one on messaged customers, one on the rest. Inputs are
          standardised; missing values are filled with training medians and flagged.
        </li>
        <li>
          The coefficients are written to Exasol, and every customer is scored there in SQL. A test checks that the SQL scores
          match the Python model to within one in a million.
        </li>
        <li>Estimated effect = chance with message − chance without.</li>
      </ol>

      <h2>The comparison</h2>
      <p>
        On the holdout, three ways of choosing who to contact are compared at every budget from 1% to 100%: rank by estimated
        effect, rank by chance of acting with the message (“likely buyers”), and random. For the top k%, extra outcomes per
        1,000 contacted = (rate among messaged − rate among not messaged) × 1,000.
      </p>
      <p>
        The 95% bands come from 200 bootstrap resamples of the holdout with a fixed seed. Resampling runs in Python on scores
        fetched from Exasol; the bands are stored back in Exasol. When a band includes zero, the result is called
        inconclusive.
      </p>

      <h2>The four groups (estimates)</h2>
      <ul>
        <li>
          <strong>Offer tips them</strong>: estimated effect of at least {fmt.one((list[0]?.u ?? 0.01) * 100)} percentage
          point.
        </li>
        <li>
          <strong>Offer puts them off</strong>: estimated effect of at most −{fmt.one((list[0]?.u ?? 0.01) * 100)} point.
        </li>
        <li>
          <strong>Would act anyway</strong>: otherwise, with an estimated chance of acting without the message of{" "}
          {fmt.pct(list[0]?.p0_cut ?? 0.5)} or more.
        </li>
        <li>
          <strong>Won’t act either way</strong>: everyone else.
        </li>
      </ul>
      <p>These thresholds are set per dataset in the backend config. Individual effects cannot be observed, only estimated.</p>

      <h2>Limitations</h2>
      <ul>
        <li>Past campaigns predict future ones only if customers, message and timing are similar.</li>
        <li>Logistic regression is simple on purpose, so it can be scored in SQL and explained. Stronger models may rank better.</li>
        <li>Results are counts and rates. There are no revenue or margin figures.</li>
        {list.flatMap((d) => d.limitations.map((l) => <li key={`${d.id}-${l}`}>{d.name}: {l}</li>))}
      </ul>

      <h2>Where it runs</h2>
      <p>
        Data, features, scores, curves and metrics live in a local Exasol database (the exasol/docker-db container). Python
        trains the small models, runs the bootstrap and serves the API.
        {health.data && (
          <>
            {" "}
            Right now Exasol is {health.data.exasol ? "reachable" : "not reachable"}; schema PROMOLENS holds{" "}
            {fmt.int(health.data.tables.length)} tables.
          </>
        )}
      </p>
    </article>
  );
}
