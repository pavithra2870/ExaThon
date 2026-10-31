"""Shared helpers for pipeline commands."""

from __future__ import annotations

import argparse

import pyexasol

from app.config import DATASETS, SCHEMA, Dataset, get_dataset
from app.db import connect, run_script


def dataset_arg(description: str | None) -> Dataset:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dataset", required=True, choices=list(DATASETS))
    return get_dataset(parser.parse_args().dataset)


def pipeline_connection() -> pyexasol.ExaConnection:
    """Connect, create/verify the schema and shared tables, then open the schema."""
    c = connect(open_schema=False, socket_timeout=3600)
    run_script(c, "00_schema.sql", verbose=False)
    c.execute(f"OPEN SCHEMA {SCHEMA}")
    return c


def banner(text: str) -> None:
    print(f"\n== {text} ==")
