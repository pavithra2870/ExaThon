"""SQL scores equal sklearn predict_proba within 1e-6, using the coefficients stored in Exasol."""

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.config import DATASETS, SCHEMA

pytestmark = pytest.mark.db


@pytest.mark.parametrize("ds_id", list(DATASETS))
def test_sql_scores_match_sklearn(ds_id):
    from app.db import conn, table_exists

    ds = DATASETS[ds_id]
    c = conn()
    if not table_exists(c, f"{ds.prefix}_SCORES"):
        pytest.skip(f"{ds_id} not processed yet")

    coef = {r["feature"]: r for r in c.execute(f"SELECT * FROM {SCHEMA}.{ds.prefix}_MODEL_COEF").fetchall()}
    feats = ds.feature_names
    cols = ", ".join(f"f.{f}" for f in feats)
    rows = c.execute(
        f"SELECT s.p0, s.p1, {cols} FROM {SCHEMA}.{ds.prefix}_SCORES s "
        f"JOIN {SCHEMA}.{ds.prefix}_FRAME f ON f.client_id = s.client_id WHERE s.part = 'holdout' LIMIT 5000"
    ).fetchall()

    X = np.array([[np.nan if r[f] is None else float(r[f]) for f in feats] for r in rows])
    fill = np.array([coef[f]["fill_value"] for f in feats])
    mean = np.array([coef[f]["mean_value"] for f in feats])
    std = np.array([coef[f]["std_value"] for f in feats])
    Z = (np.where(np.isnan(X), fill, X) - mean) / std

    for arm, col in (("treated", "p1"), ("control", "p0")):
        m = LogisticRegression()
        m.classes_ = np.array([0, 1])
        m.coef_ = np.array([[coef[f][f"coef_{arm}"] for f in feats]])
        m.intercept_ = np.array([coef["__intercept__"][f"coef_{arm}"]])
        sk = m.predict_proba(Z)[:, 1]
        sql = np.array([float(r[col]) for r in rows])
        assert np.max(np.abs(sql - sk)) < 1e-6
