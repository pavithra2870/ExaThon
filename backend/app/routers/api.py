"""HTTP routes. Thin: validation here, queries in services."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.config import get_dataset
from app.schemas import Customers, MetricResult, Overview, PlanTest, Proof, Trace
from app.services import metrics
from app.services.stats import sample_size_per_arm

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, Any]:
    return metrics.health()


@router.get("/datasets")
def datasets() -> list[dict[str, Any]]:
    return metrics.datasets()


@router.get("/plan-test", response_model=PlanTest)
def plan_test(
    baseline: float = Query(..., gt=0, lt=1, description="Control rate, 0-1"),
    effect: float = Query(..., description="Absolute change to detect, e.g. 0.01 = 1 point"),
    power: float = Query(0.8, gt=0, lt=1),
    alpha: float = Query(0.05, gt=0, lt=1),
) -> PlanTest:
    n = sample_size_per_arm(baseline, effect, power, alpha)
    return PlanTest(
        baseline=baseline,
        effect=effect,
        power=power,
        alpha=alpha,
        n_per_arm=n,
        n_total=2 * n,
        formula="n = (z(1-alpha/2) * sqrt(2 pbar (1-pbar)) + z(power) * sqrt(p1 q1 + p2 q2))^2 / effect^2, two-sided",
    )


@router.get("/{ds}/overview", response_model=Overview)
def overview(ds: str, budget: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    return metrics.overview(get_dataset(ds), budget)


@router.get("/{ds}/curve", response_model=MetricResult)
def curve(ds: str) -> dict[str, Any]:
    return metrics.metric(get_dataset(ds), "curve")


@router.get("/{ds}/deciles", response_model=MetricResult)
def deciles(ds: str) -> dict[str, Any]:
    return metrics.metric(get_dataset(ds), "deciles")


@router.get("/{ds}/groups", response_model=MetricResult)
def groups(ds: str) -> dict[str, Any]:
    return metrics.metric(get_dataset(ds), "groups")


@router.get("/{ds}/proof", response_model=Proof)
def proof(ds: str, budget: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    return metrics.proof(get_dataset(ds), budget)


@router.get("/{ds}/customers", response_model=Customers)
def customers(
    ds: str,
    group: str | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("uplift_desc"),
) -> dict[str, Any]:
    return metrics.customers(get_dataset(ds), group or None, limit, offset, sort)


@router.get("/{ds}/trace", response_model=Trace)
def trace(ds: str, metric: str = Query(...)) -> dict[str, Any]:
    return metrics.trace(get_dataset(ds), metric)
