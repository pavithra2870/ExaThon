"""Metric formulas on tiny hand-checked inputs."""

import numpy as np
import pytest

from app.services.stats import bootstrap_bands, gain, ntile, per_1000, sample_size_per_arm, verdict


def test_per_1000_hand_checked():
    # treated: 2 of 4 bought (0.50); control: 1 of 4 bought (0.25) -> 0.25 * 1000
    assert per_1000(yt=2, nt=4, yc=1, nc=4) == pytest.approx(250.0)


def test_gain_scales_by_contacted():
    # 0.25 extra purchases per person contacted, 8 contacted -> 2 extra purchases
    assert gain(yt=2, nt=4, yc=1, nc=4, n=8) == pytest.approx(2.0)


def test_per_1000_empty_arm():
    assert per_1000(yt=1, nt=3, yc=0, nc=0) is None


def test_sample_size_textbook_case():
    # 10% vs 12%, power 0.8, alpha 0.05 two-sided: 3,841 per arm (Fleiss formula, no continuity correction)
    assert sample_size_per_arm(0.10, 0.02, 0.8, 0.05) == 3841


def test_sample_size_rejects_impossible_rates():
    with pytest.raises(ValueError):
        sample_size_per_arm(0.99, 0.05)
    with pytest.raises(ValueError):
        sample_size_per_arm(0.1, 0.0)


def test_ntile_matches_sql():
    # 13 rows in 10 buckets: first 3 buckets get 2 rows, the rest 1
    assert list(ntile(13, 10)) == [1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10]


def test_verdict():
    assert verdict(1.0, 5.0) == "better"
    assert verdict(-5.0, -1.0) == "worse"
    assert verdict(-1.0, 5.0) == "inconclusive"
    assert verdict(None, 1.0) == "inconclusive"


def _toy(n=2000, seed=1):
    rng = np.random.default_rng(seed)
    t = rng.integers(0, 2, n)
    score = rng.random(n)
    # people with a high score respond to treatment; others do not
    y = (rng.random(n) < 0.1 + 0.2 * t * (score > 0.5)).astype(int)
    rank_u = np.argsort(np.argsort(-score)) + 1
    rank_b = np.argsort(np.argsort(rng.random(n))) + 1
    dec = np.empty(n, dtype=int)
    dec[np.argsort(rank_u)] = ntile(n)
    return t, y, rank_u, rank_b, dec


def test_bootstrap_shape_order_and_determinism():
    t, y, ru, rb, dec = _toy()
    a = bootstrap_bands(t, y, ru, rb, dec, n_resamples=50, seed=7)
    b = bootstrap_bands(t, y, ru, rb, dec, n_resamples=50, seed=7)
    assert a == b
    assert len(a) == 3 * 100 + 2 * 100 + 10
    for _, _, _, lo, hi in a:
        if lo is not None and hi is not None:
            assert lo <= hi


def test_bootstrap_band_covers_point_estimate():
    t, y, ru, rb, dec = _toy(n=5000)
    bands = {(s, m, k): (lo, hi) for s, m, k, lo, hi in bootstrap_bands(t, y, ru, rb, dec, n_resamples=200, seed=3)}
    order = np.argsort(ru)
    top = order[: 2000]  # top 40%
    point = per_1000(y[top][t[top] == 1].sum(), (t[top] == 1).sum(), y[top][t[top] == 0].sum(), (t[top] == 0).sum())
    lo, hi = bands[("uplift", "per_1000", 40)]
    assert lo < point < hi
    # the planted effect sits in the top half, so uplift ranking beats random at 40%
    assert bands[("uplift", "diff_random", 40)][0] > 0
