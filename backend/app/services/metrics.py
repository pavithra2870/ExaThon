"""Metric queries for the API. Every number returned here comes from an Exasol query and
travels with its query_id and elapsed_ms."""

from __future__ import annotations

import re
import threading
import time
from decimal import Decimal
from typing import Any

from app.config import DATASETS, Dataset
from app.db import QueryResult, conn, metric_sql, named_queries, query_id, render, run_query, table_exists
from app.services.stats import verdict

TTL_SECONDS = 300
_cache: dict[tuple, tuple[float, QueryResult]] = {}
_lock = threading.Lock()

GROUPS = {
    "tipped": "Offer tips them",
    "anyway": "Would act anyway",
    "never": "Won't act either way",
    "put_off": "Offer puts them off",
}
SORTS = {
    "uplift_desc": "uplift DESC, client_id",
    "uplift_asc": "uplift ASC, client_id",
    "p1_desc": "p1 DESC, client_id",
    "p0_desc": "p0 DESC, client_id",
    "p0_asc": "p0 ASC, client_id",
}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() and v.as_tuple().exponent >= 0 else float(v)
    return v


def _clean(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


def metric(ds: Dataset, name: str, params: dict[str, Any] | None = None, *, cache: bool = True) -> dict[str, Any]:
    key = (ds.id, name, tuple(sorted((params or {}).items())))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
    if cache and hit and hit[0] > now:
        res, cached = hit[1], True
    else:
        res = run_query(metric_sql(name, ds), params, dataset=ds.id, metric=name)
        res.rows = _clean(res.rows)
        cached = False
        with _lock:
            _cache[key] = (now + TTL_SECONDS, res)
    return {
        "dataset": ds.id,
        "metric": name,
        "query_id": res.query_id,
        "elapsed_ms": res.elapsed_ms,
        "cached": cached,
        "rows": res.rows,
    }


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def dataset_info(ds: Dataset) -> dict[str, Any]:
    return {
        "id": ds.id,
        "name": ds.name,
        "channel": ds.channel,
        "treatment_label": ds.treatment_label,
        "target_label": ds.target_label,
        "outcome": ds.outcome,
        "outcome_plural": ds.outcome_plural,
        "source": ds.source,
        "note": ds.note,
        "limitations": list(ds.limitations),
        "u": ds.u,
        "p0_cut": ds.p0_cut,
        "has_audience": ds.has_audience,
        "features": [{"name": f.name, "label": f.label} for f in ds.features],
        "groups": GROUPS,
    }


def datasets() -> list[dict[str, Any]]:
    c = conn()
    out = []
    for ds in DATASETS.values():
        info = dataset_info(ds)
        info["ready"] = table_exists(c, f"{ds.prefix}_SCORES")
        info["bands_ready"] = info["ready"] and bool(
            c.execute(f"SELECT COUNT(*) FROM {ds.prefix}_BOOTSTRAP").fetchval()
        ) if info["ready"] else False
        out.append(info)
    return out


def overview(ds: Dataset, budget: int) -> dict[str, Any]:
    at_k = metric(ds, "overview", {"budget": budget})
    summary = metric(ds, "summary")
    return {"dataset": ds.id, "budget": budget, "at_budget": at_k, "summary": summary}


def proof(ds: Dataset, budget: int) -> dict[str, Any]:
    comp = metric(ds, "proof", {"budget": budget})
    for r in comp["rows"]:
        r["verdict"] = verdict(r.get("lo"), r.get("hi"))
    return {
        "dataset": ds.id,
        "budget": budget,
        "at_budget": metric(ds, "overview", {"budget": budget}),
        "comparison": comp,
        "qini": metric(ds, "qini"),
        "deciles": metric(ds, "deciles"),
        "groups": metric(ds, "groups"),
        "summary": metric(ds, "summary"),
    }


def _reason_text(ds: Dataset, feature: str, fvalue: float | None, z: float, contrib: float) -> str:
    f = ds.feature(feature)
    label = f.label
    if f.flag:
        what = f"{label}: {'yes' if (fvalue or 0) >= 0.5 else 'no'}"
    elif fvalue is None:
        what = f"{label}: not recorded"
    else:
        what = f"{label}: {'higher' if z > 0 else 'lower'} than typical"
    effect = "raises" if contrib > 0 else "lowers"
    return f"{what}, which {effect} the estimated effect of the {ds.channel.lower()}"


def customers(ds: Dataset, grp: str | None, limit: int, offset: int, sort: str) -> dict[str, Any]:
    if grp is not None and grp not in GROUPS:
        raise KeyError(f"Unknown group '{grp}'. Choose one of: {', '.join(GROUPS)}")
    if sort not in SORTS:
        raise KeyError(f"Unknown sort '{sort}'. Choose one of: {', '.join(SORTS)}")
    page = metric(ds, "customers", {"grp": grp, "order_by": SORTS[sort], "limit": limit, "offset": offset}, cache=False)
    ids = [r["client_id"] for r in page["rows"] if _ID_RE.match(str(r["client_id"]))]
    reasons_meta = None
    if ids:
        id_list = ", ".join(f"'{i}'" for i in ids)
        reasons_meta = metric(ds, "reasons", {"ids": id_list}, cache=False)
        by_id: dict[str, list[dict[str, Any]]] = {}
        for r in reasons_meta["rows"]:
            by_id.setdefault(r["client_id"], []).append(
                {
                    "feature": r["feature"],
                    "label": ds.label(r["feature"]),
                    "z": r["z"],
                    "contrib": r["contrib"],
                    "text": _reason_text(ds, r["feature"], r["fvalue"], r["z"] or 0.0, r["contrib"] or 0.0),
                }
            )
        for r in page["rows"]:
            r["reasons"] = by_id.get(r["client_id"], [])
        reasons_meta = {k: v for k, v in reasons_meta.items() if k != "rows"}
    total = page["rows"][0]["total_rows"] if page["rows"] else 0
    return {"dataset": ds.id, "group": grp, "limit": limit, "offset": offset, "sort": sort, "total": total, "page": page, "reasons": reasons_meta}


def trace(ds: Dataset, name: str) -> dict[str, Any]:
    sql = metric_sql(name, ds)
    return {"dataset": ds.id, "metric": name, "sql": sql, "query_id": query_id(sql)}


def trace_names() -> list[str]:
    return sorted(named_queries("30_metrics.sql"))


def health() -> dict[str, Any]:
    c = conn()
    t0 = time.perf_counter()
    one = c.execute("SELECT 1").fetchval()
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    tables = run_query(render(named_queries("30_metrics.sql")["health_tables"]), dataset="", metric="health_tables", log=False)
    names = {r["table_name"] for r in tables.rows}
    ready = {ds.id: f"{ds.prefix}_SCORES" in names for ds in DATASETS.values()}
    return {
        "exasol": one == 1,
        "select_1_ms": elapsed,
        "session_id": str(c.session_id()),
        "tables": [{"table": r["table_name"], "rows": _jsonable(r["row_count"])} for r in tables.rows],
        "datasets_ready": ready,
        "query_id": tables.query_id,
        "elapsed_ms": tables.elapsed_ms,
    }
