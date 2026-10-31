/** Helpers for the single fetched curve (3 strategies x k = 1..100). */

export const STRATEGIES = [
  { id: "uplift", label: "Target by estimated uplift", short: "Uplift model", className: "s-uplift", band: true },
  { id: "likely_buyers", label: "Target likely buyers", short: "Likely buyers", className: "s-buyers", band: true },
  { id: "random", label: "Contact at random", short: "Random", className: "s-random", band: false },
];

export function byStrategy(rows) {
  const out = {};
  for (const r of rows ?? []) {
    (out[r.strategy] ??= []).push(r);
  }
  for (const k of Object.keys(out)) out[k].sort((a, b) => a.k - b.k);
  return out;
}

/** Linear interpolation of a numeric field at x (1..100) from rows sorted by k. */
export function interpolate(rows, x, field) {
  if (!rows?.length) return null;
  if (x <= rows[0].k) return rows[0][field];
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i - 1];
    const b = rows[i];
    if (x <= b.k) {
      if (a[field] == null || b[field] == null) return x - a.k < b.k - x ? a[field] : b[field];
      const t = (x - a.k) / (b.k - a.k);
      // Exasol sends exact decimals as strings; coerce so the sum adds.
      const av = Number(a[field]);
      return av + t * (Number(b[field]) - av);
    }
  }
  return rows[rows.length - 1][field];
}

export function rowAt(rows, x) {
  const fields = ["per_1000", "lo", "hi", "share_anyway", "n_k", "g_tipped_k", "g_anyway_k", "g_never_k", "g_put_off_k"];
  const r = { k: x };
  for (const f of fields) r[f] = interpolate(rows, x, f);
  return r;
}

export function actionVerb(ds) {
  return ds?.outcome === "store visit" ? "visit a store" : "buy";
}
