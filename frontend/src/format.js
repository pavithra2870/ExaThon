const locale = undefined; // viewer's locale

const int = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
const one = new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const signedOne = new Intl.NumberFormat(locale, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});
const pct0 = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 });
const pct1 = new Intl.NumberFormat(locale, { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const pct2 = new Intl.NumberFormat(locale, { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signedPts = new Intl.NumberFormat(locale, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});
const sci = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });

const ok = (v) => v !== null && v !== undefined && Number.isFinite(Number(v));
const dash = "–";

export const fmt = {
  int: (v) => (ok(v) ? int.format(v) : dash),
  one: (v) => (ok(v) ? one.format(v) : dash),
  signed: (v) => (ok(v) ? signedOne.format(v) : dash),
  pct: (v) => (ok(v) ? pct0.format(v) : dash),
  pct1: (v) => (ok(v) ? pct1.format(v) : dash),
  pct2: (v) => (ok(v) ? pct2.format(v) : dash),
  /** a rate difference (0.0123) as signed percentage points: +1.23 pts */
  pts: (v) => (ok(v) ? `${signedPts.format(v * 100)} pts` : dash),
  compact: (v) => (ok(v) ? sci.format(v) : dash),
  ms: (v) => (ok(v) ? `${one.format(v)} ms` : dash),
};

export function bandText(lo, hi, f = fmt.signed) {
  if (!ok(lo) || !ok(hi)) return "band not computed yet";
  return `${f(lo)} to ${f(hi)}`;
}

export function verdictOf(lo, hi) {
  if (!ok(lo) || !ok(hi)) return "inconclusive";
  if (lo > 0) return "better";
  if (hi < 0) return "worse";
  return "inconclusive";
}
