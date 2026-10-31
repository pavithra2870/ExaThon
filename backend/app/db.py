"""Exasol connection, SQL templating and the query log."""

from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import pyexasol

from app.config import HOLDOUT_SHARE, SCHEMA, SQL_DIR, Dataset, exa_settings

_local = threading.local()


def connect(open_schema: bool = True, socket_timeout: int = 120) -> pyexasol.ExaConnection:
    """Open a new connection. TLS stays on; the DSN pins the server certificate fingerprint.
    Pipeline jobs pass a long socket_timeout: big CREATE TABLE AS statements can run for minutes."""
    s = exa_settings()
    conn = pyexasol.connect(
        dsn=s["dsn"],
        user=s["user"],
        password=s["password"],
        socket_timeout=socket_timeout,
        compression=True,
        fetch_dict=True,
        lower_ident=True,
    )
    if open_schema:
        conn.execute(f"OPEN SCHEMA {SCHEMA}")
    return conn


def conn() -> pyexasol.ExaConnection:
    """One connection per thread (pyexasol connections are not thread-safe)."""
    c: pyexasol.ExaConnection | None = getattr(_local, "conn", None)
    if c is None or c.is_closed:
        c = connect()
        _local.conn = c
    return c


# ---------------------------------------------------------------------------
# SQL files are templates. {{P}} is the dataset prefix, {{SCHEMA}} the schema,
# {{FEATURE_UNPIVOT}} expands to one UNION ALL branch per configured feature,
# {{U}} and {{P0_CUT}} are the group thresholds from the dataset config.
# ---------------------------------------------------------------------------

def _unpivot(ds: Dataset) -> str:
    branches = [
        f"SELECT client_id, CAST('{f}' AS VARCHAR(64)) AS feature, CAST({f} AS DOUBLE) AS fvalue FROM {SCHEMA}.{ds.prefix}_FRAME"
        for f in ds.feature_names
    ]
    return "\nUNION ALL ".join(branches)


def render(sql: str, ds: Dataset | None = None) -> str:
    sql = sql.replace("{{SCHEMA}}", SCHEMA).replace("{{HOLDOUT}}", repr(HOLDOUT_SHARE))
    if ds is not None:
        sql = (
            sql.replace("{{FEATURE_UNPIVOT}}", _unpivot(ds))
            .replace("{{P}}", f"{SCHEMA}.{ds.prefix}")
            .replace("{{U}}", repr(float(ds.u)))
            .replace("{{P0_CUT}}", repr(float(ds.p0_cut)))
        )
    left = [m for m in re.findall(r"{{\w+}}", sql) if m != "{{BUCKET}}"]
    if left:
        raise ValueError(f"Unrendered placeholder in SQL: {left}")
    return sql


def statements(sql: str) -> list[str]:
    """Split a script on semicolons that end a line. Comment-only chunks are dropped."""
    parts = re.split(r";[ \t]*(?:\r?\n|$)", sql)
    out = []
    for p in parts:
        body = "\n".join(line for line in p.splitlines() if not line.strip().startswith("--")).strip()
        if body:
            out.append(p.strip())
    return out


def read_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


def named_queries(filename: str) -> dict[str, str]:
    """Parse '-- name: foo' blocks from a SQL file. Blocks named _x are fragments that
    other blocks include as {{X}} (e.g. _curve_ctes -> {{CURVE_CTES}})."""
    text = read_sql(filename)
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.M)
    raw = {blocks[i]: blocks[i + 1].strip().rstrip(";") for i in range(1, len(blocks), 2)}
    fragments = {k: v for k, v in raw.items() if k.startswith("_")}
    out = {}
    for name, body in raw.items():
        if name.startswith("_"):
            continue
        for frag, frag_body in fragments.items():
            body = body.replace("{{" + frag[1:].upper() + "}}", frag_body)
        out[name] = body
    return out


def metric_sql(name: str, ds: Dataset) -> str:
    queries = named_queries("30_metrics.sql")
    if name not in queries:
        raise KeyError(f"Unknown metric '{name}'. Known: {', '.join(sorted(queries))}")
    return render(queries[name], ds)


def query_id(sql: str) -> str:
    return hashlib.sha1(sql.encode("utf-8")).hexdigest()


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    sql: str
    query_id: str
    elapsed_ms: float


def run_query(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    dataset: str = "",
    metric: str = "",
    log: bool = True,
    c: pyexasol.ExaConnection | None = None,
) -> QueryResult:
    """Run a query, time it, and record it in QUERY_LOG.

    query_id is the sha1 of the SQL text before parameters are bound, so the same
    metric keeps the same id across budgets. pyexasol exposes the session id but no
    per-statement id, so the log stores the session id.
    """
    c = c or conn()
    t0 = time.perf_counter()
    rows = c.execute(sql, params or None).fetchall()
    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    qid = query_id(sql)
    if log:
        try:
            c.execute(
                f"INSERT INTO {SCHEMA}.QUERY_LOG (query_id, dataset, metric, sql_text, elapsed_ms, row_count, session_id, logged_at) "
                "VALUES ({qid}, {ds}, {metric}, {sql}, {ms}, {n}, {sid}, CURRENT_TIMESTAMP)",
                {"qid": qid, "ds": dataset, "metric": metric, "sql": sql[:2_000_000], "ms": elapsed, "n": len(rows), "sid": str(c.session_id())},
            )
        except pyexasol.ExaError:
            pass  # logging must never break a read
    return QueryResult(rows=rows, sql=sql, query_id=qid, elapsed_ms=elapsed)


BUCKETS = 16


def run_script(c: pyexasol.ExaConnection, filename: str, ds: Dataset | None = None, verbose: bool = True) -> None:
    """Run each statement of a rendered script. A statement containing {{BUCKET}} runs once per
    bucket 0..BUCKETS-1, so heavy aggregations over huge tables stay within the database's RAM."""
    sql = render(read_sql(filename), ds)
    for stmt in statements(sql):
        t0 = time.perf_counter()
        first = next(line for line in stmt.splitlines() if line.strip() and not line.strip().startswith("--"))
        if "{{BUCKET}}" in stmt:
            rows = 0
            for b in range(BUCKETS):
                rows += c.execute(stmt.replace("{{BUCKET}}", str(b))).rowcount()
            if verbose:
                print(f"  {filename}: {first.strip()[:80]}  [{BUCKETS} buckets, {rows} rows, {time.perf_counter() - t0:.1f}s]", flush=True)
            continue
        st = c.execute(stmt)
        if verbose:
            print(f"  {filename}: {first.strip()[:90]}  [{st.rowcount()} rows, {time.perf_counter() - t0:.1f}s]", flush=True)


def table_exists(c: pyexasol.ExaConnection, table: str) -> bool:
    return bool(
        c.execute(
            "SELECT COUNT(*) AS n FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA = {s} AND TABLE_NAME = {t}",
            {"s": SCHEMA, "t": table.upper()},
        ).fetchval()
    )


def count(c: pyexasol.ExaConnection, table: str) -> int:
    return int(c.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}").fetchval())
