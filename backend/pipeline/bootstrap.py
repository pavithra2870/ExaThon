"""Bootstrap 95% bands on the scored holdout and store them in <PREFIX>_BOOTSTRAP.

  python -m pipeline.bootstrap --dataset hillstrom|lenta|x5

Rankings come from Exasol (same ORDER BY and tie-break as the metric queries). Resampling
runs in Python on the fetched holdout rows: 200 resamples, fixed seed.
"""

from __future__ import annotations

import time

from app.config import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, SCHEMA, Dataset
from app.db import render, run_query
from app.services.stats import bootstrap_bands
from pipeline.common import banner, dataset_arg, pipeline_connection

RANKS_SQL = """
SELECT treatment, target,
       ROW_NUMBER() OVER (ORDER BY uplift DESC, tb) AS rank_uplift,
       ROW_NUMBER() OVER (ORDER BY p1 DESC, tb)     AS rank_buyers,
       NTILE(10)    OVER (ORDER BY uplift DESC, tb) AS decile
FROM (
    SELECT treatment, target, p1, uplift, HASH_SHA1('promolens-tiebreak:' || client_id) AS tb
    FROM {{P}}_SCORES
    WHERE part = 'holdout'
) h
"""


def run(ds: Dataset) -> None:
    banner(f"bootstrap {ds.id}")
    c = pipeline_connection()
    res = run_query(render(RANKS_SQL, ds), dataset=ds.id, metric="bootstrap_ranks", c=c)
    rows = res.rows
    print(f"  fetched {len(rows):,} holdout rows in {res.elapsed_ms:.0f} ms")

    t0 = time.perf_counter()
    bands = bootstrap_bands(
        treatment=[int(r["treatment"]) for r in rows],
        target=[int(r["target"]) for r in rows],
        rank_uplift=[int(r["rank_uplift"]) for r in rows],
        rank_buyers=[int(r["rank_buyers"]) for r in rows],
        decile=[int(r["decile"]) for r in rows],
        n_resamples=BOOTSTRAP_RESAMPLES,
        seed=BOOTSTRAP_SEED,
    )
    print(f"  {BOOTSTRAP_RESAMPLES} resamples in {time.perf_counter() - t0:.1f}s, seed {BOOTSTRAP_SEED}")

    table = f"{ds.prefix}_BOOTSTRAP"
    c.execute(f"TRUNCATE TABLE {SCHEMA}.{table}")
    c.import_from_iterable(
        [(*r, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED) for r in bands], (SCHEMA, table)
    )
    print(f"  wrote {len(bands)} band rows to {table}")
    for strategy, metric, k, lo, hi in bands:
        if metric in ("per_1000", "diff_buyers") and k in (10, 20, 50):
            fmt = lambda v: "n/a" if v is None else f"{v:+.1f}"  # noqa: E731
            print(f"    {strategy:<13} {metric:<11} k={k:<3} [{fmt(lo)}, {fmt(hi)}] per 1,000")


if __name__ == "__main__":
    run(dataset_arg(__doc__))
