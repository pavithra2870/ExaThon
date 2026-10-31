"""Load a dataset's raw files into typed Exasol tables and verify row counts.

  python -m pipeline.load --dataset hillstrom|lenta|x5

Hillstrom and Lenta are small enough for pandas. X5 CSVs are streamed straight into
Exasol with pyexasol's HTTP transport; purchases.csv (~4.2 GB) goes in byte-bounded
chunks and is never read into pandas.
"""

from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pandas as pd
import pyexasol

from app.config import DATA_DIR, HILLSTROM, LENTA, SCHEMA, X5, Dataset
from app.db import count, run_script
from pipeline.common import banner, dataset_arg, pipeline_connection

CHUNK_BYTES = 256 * 1024 * 1024
LENTA_RAW_COLUMNS = [
    "age", "children", "months_from_register", "response_sms", "response_viber",
    "food_share_15d", "food_share_1m", "promo_share_15d", "mean_discount_depth_15d",
    "stdev_discount_depth_15d", "k_var_discount_depth_15d", "k_var_cheque_15d", "k_var_cheque_3m",
    "k_var_cheque_category_width_15d", "k_var_days_between_visits_15d", "k_var_days_between_visits_1m",
    "k_var_days_between_visits_3m", "k_var_sku_per_cheque_15d", "stdev_days_between_visits_15d",
    "perdelta_days_between_visits_15_30d", "crazy_purchases_cheque_count_1m",
    "crazy_purchases_cheque_count_3m", "crazy_purchases_cheque_count_12m",
    "crazy_purchases_goods_count_12m", "cheque_count_3m_g20", "cheque_count_12m_g20",
    "sale_count_3m_g24", "sale_count_12m_g32",
]


def _check(c: pyexasol.ExaConnection, table: str, expected: int) -> None:
    got = count(c, table)
    status = "OK" if got == expected else "MISMATCH"
    print(f"  {table}: {got:,} rows (expected {expected:,}) {status}")
    if got != expected:
        raise SystemExit(f"Row count mismatch for {table}")


def load_hillstrom(c: pyexasol.ExaConnection, ds: Dataset) -> None:
    path = DATA_DIR / "Hillstrom" / "hillstorm_no_indices.csv.gz"
    df = pd.read_csv(path)
    df.insert(0, "client_id", [f"H{i:06d}" for i in range(len(df))])
    cols = ["client_id", "recency", "history", "mens", "womens", "zip_code", "newbie", "channel", "segment", "visit", "conversion"]
    run_script(c, ds.raw_sql, ds)
    c.import_from_pandas(df[cols], (SCHEMA, f"{ds.prefix}_RAW"))
    _check(c, f"{ds.prefix}_RAW", len(df))


def load_lenta(c: pyexasol.ExaConnection, ds: Dataset) -> None:
    path = DATA_DIR / "Lenta" / "lenta_dataset.csv.gz"
    df = pd.read_csv(path, usecols=["group", "response_att", "gender", "main_format", *LENTA_RAW_COLUMNS])
    df.insert(0, "client_id", [f"L{i:07d}" for i in range(len(df))])
    # Source labels are Cyrillic: female, male, undetermined.
    df["gender"] = df["gender"].map({"Ж": "F", "М": "M"}).fillna("U")
    df = df.rename(columns={"group": "grp"})
    cols = ["client_id", "grp", "response_att", "gender", "main_format", *LENTA_RAW_COLUMNS]
    run_script(c, ds.raw_sql, ds)
    c.import_from_pandas(df[cols], (SCHEMA, f"{ds.prefix}_RAW"))
    _check(c, f"{ds.prefix}_RAW", len(df))


class _ChunkReader(io.RawIOBase):
    """Reads about max_bytes from a binary file, then finishes the current line."""

    def __init__(self, f: io.BufferedReader, max_bytes: int):
        self.f, self.left, self.lines, self.done = f, max_bytes, 0, False

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self.done:
            return b""
        if self.left <= 0:
            self.done = True
            tail = self.f.readline()
            self.lines += tail.count(b"\n")
            return tail
        data = self.f.read(min(size if size and size > 0 else 1 << 20, self.left))
        if not data:
            self.done = True
            return b""
        self.left -= len(data)
        self.lines += data.count(b"\n")
        return data


def _data_lines(path: Path) -> int:
    """Number of data rows (lines minus header), counted in binary blocks."""
    n, last = 0, b"\n"
    with open(path, "rb") as f:
        while block := f.read(1 << 24):
            n += block.count(b"\n")
            last = block[-1:]
    return n + (0 if last == b"\n" else 1) - 1


def _import_csv(c: pyexasol.ExaConnection, path: Path, table: str) -> None:
    t0 = time.perf_counter()
    c.import_from_file(str(path), (SCHEMA, table), import_params={"skip": 1})
    print(f"  imported {path.name} in {time.perf_counter() - t0:.1f}s")
    _check(c, table, _data_lines(path))


def load_x5(c: pyexasol.ExaConnection, ds: Dataset) -> None:
    root = DATA_DIR / "X5-RetailHero"
    run_script(c, ds.raw_sql, ds)
    c.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
    for name, table in [
        ("clients.csv", "CLIENTS"),
        ("products.csv", "PRODUCTS"),
        ("uplift_train.csv", "UPLIFT_TRAIN"),
        ("uplift_test.csv", "UPLIFT_TEST"),
    ]:
        _import_csv(c, root / name, f"{ds.prefix}_{table}")

    path = root / "purchases.csv"
    size = os.path.getsize(path)
    table = f"{ds.prefix}_PURCHASES"
    print(f"  streaming {path.name} ({size / 1e9:.2f} GB) in ~{CHUNK_BYTES >> 20} MB chunks")
    sent, t0 = 0, time.perf_counter()
    with open(path, "rb") as f:
        f.readline()  # header
        chunk = 0
        while f.tell() < size:
            chunk += 1
            reader = _ChunkReader(f, CHUNK_BYTES)
            c.import_from_file(reader, (SCHEMA, table))
            sent += reader.lines
            print(f"  chunk {chunk}: {f.tell() / size:6.1%} of file, {count(c, table):,} rows in table, {time.perf_counter() - t0:.0f}s")
    expected = _data_lines(path)
    print(f"  newline-terminated rows sent: {sent:,}")
    _check(c, table, expected)


LOADERS = {HILLSTROM.id: load_hillstrom, LENTA.id: load_lenta, X5.id: load_x5}


def run(ds: Dataset) -> None:
    banner(f"load {ds.id}")
    c = pipeline_connection()
    LOADERS[ds.id](c, ds)


if __name__ == "__main__":
    run(dataset_arg(__doc__))
