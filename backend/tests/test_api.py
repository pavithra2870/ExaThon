"""API via TestClient. Tests marked db need Exasol with Hillstrom processed."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_plan_test_endpoint():
    r = client.get("/api/plan-test", params={"baseline": 0.1, "effect": 0.02})
    assert r.status_code == 200
    body = r.json()
    assert body["n_per_arm"] == 3841
    assert body["n_total"] == 7682


def test_plan_test_bad_input_is_structured():
    r = client.get("/api/plan-test", params={"baseline": 0.99, "effect": 0.05})
    assert r.status_code == 422
    assert set(r.json()) == {"error", "hint"}


def test_unknown_dataset_is_structured_404():
    r = client.get("/api/nope/curve")
    assert r.status_code == 404
    assert "Unknown dataset" in r.json()["error"]


@pytest.mark.db
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["exasol"] is True


@pytest.mark.db
def test_curve_has_three_strategies_and_query_id():
    r = client.get("/api/hillstrom/curve")
    assert r.status_code == 200
    body = r.json()
    assert len(body["query_id"]) == 40 and body["elapsed_ms"] >= 0
    strategies = {row["strategy"] for row in body["rows"]}
    assert strategies == {"uplift", "likely_buyers", "random"}
    assert len(body["rows"]) == 300


@pytest.mark.db
def test_curve_matches_python_formula():
    """Recompute per_1000 at k=20 from raw holdout rows and compare with the SQL curve."""
    from app.config import SCHEMA
    from app.db import conn
    from app.services.stats import per_1000

    rows = conn().execute(
        f"SELECT treatment, target, ROW_NUMBER() OVER (ORDER BY uplift DESC, HASH_SHA1('promolens-tiebreak:' || client_id)) AS rn "
        f"FROM {SCHEMA}.HILL_SCORES WHERE part = 'holdout'"
    ).fetchall()
    n = len(rows)
    top = [r for r in rows if r["rn"] <= 20 * n / 100]
    expected = per_1000(
        sum(r["target"] for r in top if r["treatment"] == 1), sum(1 for r in top if r["treatment"] == 1),
        sum(r["target"] for r in top if r["treatment"] == 0), sum(1 for r in top if r["treatment"] == 0),
    )
    body = client.get("/api/hillstrom/overview", params={"budget": 20}).json()
    got = next(r for r in body["at_budget"]["rows"] if r["strategy"] == "uplift")["per_1000"]
    assert got == pytest.approx(expected, abs=1e-9)


@pytest.mark.db
def test_customers_have_three_reasons():
    body = client.get("/api/hillstrom/customers", params={"limit": 5}).json()
    assert len(body["page"]["rows"]) == 5
    assert all(len(r["reasons"]) == 3 for r in body["page"]["rows"])


@pytest.mark.db
def test_trace_returns_sql_and_matching_id():
    curve = client.get("/api/hillstrom/curve").json()
    trace = client.get("/api/hillstrom/trace", params={"metric": "curve"}).json()
    assert trace["query_id"] == curve["query_id"]
    assert "HILL_SCORES" in trace["sql"]
