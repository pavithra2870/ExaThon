"""Pure statistics: metric formulas, bootstrap bands and test sizing. No database access."""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

KS = np.arange(1, 101)


def per_1000(yt: float, nt: float, yc: float, nc: float) -> float | None:
    """Extra outcomes per 1,000 contacted: (Yt/Nt - Yc/Nc) * 1000. None if an arm is empty."""
    if nt <= 0 or nc <= 0:
        return None
    return (yt / nt - yc / nc) * 1000


def gain(yt: float, nt: float, yc: float, nc: float, n: float) -> float | None:
    """Extra outcomes among n contacted: (Yt/Nt - Yc/Nc) * n."""
    p = per_1000(yt, nt, yc, nc)
    return None if p is None else p / 1000 * n


def sample_size_per_arm(baseline: float, effect: float, power: float = 0.8, alpha: float = 0.05) -> int:
    """Customers per arm for a two-sided two-proportion z-test.

    baseline: control rate (0-1). effect: absolute change to detect (e.g. 0.01 = 1 point).
    n = (z_{1-a/2} * sqrt(2 * pbar * (1 - pbar)) + z_{power} * sqrt(p1 q1 + p2 q2))^2 / effect^2
    """
    p1, p2 = baseline, baseline + effect
    if not 0 < p1 < 1:
        raise ValueError("baseline must be between 0 and 1")
    if effect == 0 or not 0 < p2 < 1:
        raise ValueError("baseline + effect must be between 0 and 1, and effect must not be 0")
    if not 0 < power < 1 or not 0 < alpha < 1:
        raise ValueError("power and alpha must be between 0 and 1")
    z_a = NormalDist().inv_cdf(1 - alpha / 2)
    z_b = NormalDist().inv_cdf(power)
    pbar = (p1 + p2) / 2
    num = z_a * math.sqrt(2 * pbar * (1 - pbar)) + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(num**2 / effect**2)


def ntile(n: int, buckets: int = 10) -> np.ndarray:
    """Bucket (1..buckets) of each position 0..n-1, matching SQL NTILE: the first n % buckets
    buckets get one extra row."""
    base, extra = divmod(n, buckets)
    sizes = [base + (1 if i < extra else 0) for i in range(buckets)]
    return np.repeat(np.arange(1, buckets + 1), sizes)


def _top_k_per_1000(w: np.ndarray, t: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """per_1000 at k = 1..100 for rows already sorted by a strategy, with bootstrap weights w.
    Top k% = rows whose cumulative weight is <= k% of n, matching CEIL(rn * 100 / n) <= k."""
    cw = np.cumsum(w)
    cnt = np.cumsum(w * t)
    cyt = np.cumsum(w * t * y)
    cnc = np.cumsum(w * (1 - t))
    cyc = np.cumsum(w * (1 - t) * y)
    idx = np.searchsorted(cw, KS * n / 100.0 + 1e-9, side="right") - 1
    idx = np.clip(idx, 0, len(w) - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (cyt[idx] / cnt[idx] - cyc[idx] / cnc[idx]) * 1000
    return np.where((cnt[idx] > 0) & (cnc[idx] > 0), out, np.nan)


def bootstrap_bands(
    treatment: np.ndarray,
    target: np.ndarray,
    rank_uplift: np.ndarray,
    rank_buyers: np.ndarray,
    decile: np.ndarray,
    n_resamples: int,
    seed: int,
    level: float = 0.95,
) -> list[tuple[str, str, int, float | None, float | None]]:
    """Percentile bootstrap on the scored holdout. Rankings are fixed (the model is not refit);
    rows are resampled with replacement, which is the uncertainty from who happened to land in
    the holdout and in each arm.

    Returns rows (strategy, metric, k, lo, hi) for:
      per_1000 for uplift, likely_buyers, random at k = 1..100
      diff_buyers, diff_random (uplift minus the other strategy) at k = 1..100
      decile_uplift (observed treated minus control rate) for deciles 1..10
    """
    t = np.asarray(treatment, dtype=float)
    y = np.asarray(target, dtype=float)
    n = len(t)
    order_u = np.argsort(np.asarray(rank_uplift))
    order_b = np.argsort(np.asarray(rank_buyers))
    dec = np.asarray(decile)
    rng = np.random.default_rng(seed)

    res: dict[str, list[np.ndarray]] = {k: [] for k in ("uplift", "likely_buyers", "random", "diff_buyers", "diff_random", "decile")}
    for _ in range(n_resamples):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        u = _top_k_per_1000(w[order_u], t[order_u], y[order_u], n)
        b = _top_k_per_1000(w[order_b], t[order_b], y[order_b], n)
        whole = (np.sum(w * t * y) / np.sum(w * t) - np.sum(w * (1 - t) * y) / np.sum(w * (1 - t))) * 1000
        r = np.full(len(KS), whole)
        d = []
        for q in range(1, 11):
            m = dec == q
            wt, wc = np.sum(w[m] * t[m]), np.sum(w[m] * (1 - t[m]))
            d.append(np.sum(w[m] * t[m] * y[m]) / wt - np.sum(w[m] * (1 - t[m]) * y[m]) / wc if wt > 0 and wc > 0 else np.nan)
        res["uplift"].append(u)
        res["likely_buyers"].append(b)
        res["random"].append(r)
        res["diff_buyers"].append(u - b)
        res["diff_random"].append(u - r)
        res["decile"].append(np.array(d))

    lo_q, hi_q = (1 - level) / 2 * 100, (1 + level) / 2 * 100

    def band(arr: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        a = np.vstack(arr)
        with np.errstate(all="ignore"):
            return np.nanpercentile(a, lo_q, axis=0), np.nanpercentile(a, hi_q, axis=0)

    def clean(v: float) -> float | None:
        return None if not np.isfinite(v) else float(v)

    rows: list[tuple[str, str, int, float | None, float | None]] = []
    for strategy in ("uplift", "likely_buyers", "random"):
        lo, hi = band(res[strategy])
        rows += [(strategy, "per_1000", int(k), clean(lo[i]), clean(hi[i])) for i, k in enumerate(KS)]
    for key in ("diff_buyers", "diff_random"):
        lo, hi = band(res[key])
        rows += [("uplift", key, int(k), clean(lo[i]), clean(hi[i])) for i, k in enumerate(KS)]
    lo, hi = band(res["decile"])
    rows += [("uplift", "decile_uplift", q, clean(lo[q - 1]), clean(hi[q - 1])) for q in range(1, 11)]
    return rows


def verdict(lo: float | None, hi: float | None) -> str:
    """'better', 'worse' or 'inconclusive' for a difference band."""
    if lo is None or hi is None:
        return "inconclusive"
    if lo > 0:
        return "better"
    if hi < 0:
        return "worse"
    return "inconclusive"
