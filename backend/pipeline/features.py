"""Build the model frame (features) and the train / holdout split in Exasol.

  python -m pipeline.features --dataset hillstrom|lenta|x5
"""

from __future__ import annotations

from app.config import SCHEMA, Dataset
from app.db import run_script
from pipeline.common import banner, dataset_arg, pipeline_connection


def run(ds: Dataset) -> None:
    banner(f"features {ds.id}")
    c = pipeline_connection()
    P = f"{SCHEMA}.{ds.prefix}"

    if ds.id == "x5":
        # Leakage check: the purchase history must end before the campaign outcome window.
        lo, hi, n = c.execute(
            f"SELECT MIN(transaction_datetime), MAX(transaction_datetime), COUNT(*) FROM {P}_PURCHASES"
        ).fetchone().values()
        print(f"  purchase history: {lo} .. {hi} ({n:,} lines). Features use reference date = {hi}.")
        redeem_after = c.execute(
            f"SELECT COUNT(*) FROM {P}_CLIENTS WHERE first_redeem_date > (SELECT MAX(transaction_datetime) FROM {P}_PURCHASES)"
        ).fetchval()
        print(f"  clients with first redeem after the reference date: {redeem_after:,} (treated as not redeemed)")

    run_script(c, ds.frame_sql, ds)
    run_script(c, "15_split.sql", ds)

    rows = c.execute(
        f"SELECT s.part, COUNT(*) AS n, SUM(f.treatment) AS treated, AVG(f.target) AS target_rate "
        f"FROM {P}_FRAME f JOIN {P}_SPLIT s ON s.client_id = f.client_id GROUP BY s.part ORDER BY s.part"
    ).fetchall()
    for r in rows:
        rate = "n/a" if r["target_rate"] is None else f"{float(r['target_rate']):.4f}"
        print(f"  {r['part']:<9} {int(r['n']):>9,} rows  treated {int(r['treated'] or 0):>9,}  target rate {rate}")

    nulls = []
    for f in ds.feature_names:
        n = c.execute(f"SELECT COUNT(*) FROM {P}_FRAME WHERE {f} IS NULL").fetchval()
        if n:
            nulls.append(f"{f}={n:,}")
    print(f"  {len(ds.feature_names)} features; NULLs (filled with train medians at training): {', '.join(nulls) or 'none'}")


if __name__ == "__main__":
    run(dataset_arg(__doc__))
