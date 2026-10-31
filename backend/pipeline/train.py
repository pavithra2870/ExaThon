"""Two-model uplift: one logistic regression on treated rows, one on control rows.

  python -m pipeline.train --dataset hillstrom|lenta|x5

Fits on the 70% training split only (C tuned by 3-fold CV log loss inside it), writes
coefficients, means, stds and median fills to <PREFIX>_MODEL_COEF, scores every customer
in Exasol (20_scores.sql), then checks SQL scores against sklearn predict_proba on the holdout.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pyexasol
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from app.config import SCHEMA, Dataset
from app.db import run_script
from pipeline.common import banner, dataset_arg, pipeline_connection

C_GRID = [0.01, 0.1, 1.0]
PARITY_TOL = 1e-6


def fetch_frame(c: pyexasol.ExaConnection, ds: Dataset, part: str) -> pd.DataFrame:
    cols = ", ".join(f"f.{f}" for f in ds.feature_names)
    df = c.export_to_pandas(
        f"SELECT f.client_id, f.treatment, f.target, {cols} "
        f"FROM {SCHEMA}.{ds.prefix}_FRAME f JOIN {SCHEMA}.{ds.prefix}_SPLIT s ON s.client_id = f.client_id "
        f"WHERE s.part = '{part}' ORDER BY f.client_id"
    )
    df.columns = [col.lower() for col in df.columns]
    return df


class Prep:
    """Median fill, then standardise with training mean and population std."""

    def __init__(self, X: pd.DataFrame):
        self.fill = X.median().fillna(0.0)
        Xf = X.fillna(self.fill)
        self.mean = Xf.mean()
        std = Xf.std(ddof=0)
        self.std = std.where(std > 0, 1.0)

    def __call__(self, X: pd.DataFrame) -> np.ndarray:
        return ((X.fillna(self.fill) - self.mean) / self.std).to_numpy(dtype=float)


def fit_arm(Z: np.ndarray, y: np.ndarray) -> LogisticRegression:
    search = GridSearchCV(
        LogisticRegression(max_iter=5000),
        {"C": C_GRID},
        scoring="neg_log_loss",
        cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=0),
        n_jobs=1,
    )
    search.fit(Z, y)
    return search.best_estimator_


def run(ds: Dataset) -> None:
    banner(f"train {ds.id}")
    c = pipeline_connection()
    feats = ds.feature_names

    train = fetch_frame(c, ds, "train")
    t = train["treatment"].astype(int).to_numpy()
    y = train["target"].astype(int).to_numpy()
    print(f"  training rows: {len(train):,} (treated {t.sum():,}, control {(1 - t).sum():,})")

    prep = Prep(train[feats].astype(float))
    Z = prep(train[feats].astype(float))

    t0 = time.perf_counter()
    m1 = fit_arm(Z[t == 1], y[t == 1])
    m0 = fit_arm(Z[t == 0], y[t == 0])
    print(f"  fitted in {time.perf_counter() - t0:.1f}s; C treated = {m1.C}, C control = {m0.C}")

    coef = pd.DataFrame(
        {
            "feature": feats + ["__intercept__"],
            "coef_treated": list(m1.coef_[0]) + [m1.intercept_[0]],
            "coef_control": list(m0.coef_[0]) + [m0.intercept_[0]],
            "mean_value": list(prep.mean) + [0.0],
            "std_value": list(prep.std) + [1.0],
            "fill_value": list(prep.fill) + [0.0],
            "c_treated": m1.C,
            "c_control": m0.C,
            "n_train": len(train),
        }
    )
    table = f"{ds.prefix}_MODEL_COEF"
    c.execute(
        f"CREATE OR REPLACE TABLE {SCHEMA}.{table} (feature VARCHAR(64), coef_treated DOUBLE, coef_control DOUBLE, "
        "mean_value DOUBLE, std_value DOUBLE, fill_value DOUBLE, c_treated DOUBLE, c_control DOUBLE, n_train DECIMAL(12,0))"
    )
    c.import_from_iterable(
        [tuple(r) for r in coef.itertuples(index=False)], (SCHEMA, table)
    )
    print(f"  wrote {len(coef)} rows to {table}")
    top = coef[coef.feature != "__intercept__"].assign(gap=lambda d: (d.coef_treated - d.coef_control).abs())
    for r in top.nlargest(5, "gap").itertuples():
        print(f"    {r.feature:<34} treated {r.coef_treated:+.3f}  control {r.coef_control:+.3f}")

    run_script(c, "20_scores.sql", ds)

    # Parity: SQL scores vs sklearn predict_proba on the holdout.
    hold = fetch_frame(c, ds, "holdout")
    Zh = prep(hold[feats].astype(float))
    sk = pd.DataFrame({"client_id": hold["client_id"], "p1_sk": m1.predict_proba(Zh)[:, 1], "p0_sk": m0.predict_proba(Zh)[:, 1]})
    sql = c.export_to_pandas(f"SELECT client_id, p0, p1 FROM {SCHEMA}.{ds.prefix}_SCORES WHERE part = 'holdout'")
    sql.columns = [col.lower() for col in sql.columns]
    m = sk.merge(sql, on="client_id", how="inner")
    diff = max((m.p1 - m.p1_sk).abs().max(), (m.p0 - m.p0_sk).abs().max())
    status = "PASS" if len(m) == len(hold) and diff < PARITY_TOL else "FAIL"
    print(f"  parity on {len(m):,} holdout rows: max |SQL - sklearn| = {diff:.2e} (tolerance {PARITY_TOL:g}) {status}")
    if status != "PASS":
        raise SystemExit("SQL scoring does not match sklearn")


if __name__ == "__main__":
    run(dataset_arg(__doc__))
