"""Response models. Metric payloads are row lists whose columns come straight from SQL."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    hint: str


class MetricResult(BaseModel):
    dataset: str
    metric: str
    query_id: str
    elapsed_ms: float
    cached: bool = False
    rows: list[dict[str, Any]]


class Overview(BaseModel):
    dataset: str
    budget: int
    at_budget: MetricResult
    summary: MetricResult


class Proof(BaseModel):
    dataset: str
    budget: int
    at_budget: MetricResult
    comparison: MetricResult
    qini: MetricResult
    deciles: MetricResult
    groups: MetricResult
    summary: MetricResult


class Customers(BaseModel):
    dataset: str
    group: str | None
    limit: int
    offset: int
    sort: str
    total: int
    page: MetricResult
    reasons: dict[str, Any] | None


class PlanTest(BaseModel):
    baseline: float
    effect: float
    power: float
    alpha: float
    n_per_arm: int
    n_total: int
    formula: str


class Trace(BaseModel):
    dataset: str
    metric: str
    sql: str
    query_id: str
