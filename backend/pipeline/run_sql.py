"""Render and run numbered SQL files against Exasol.

  python -m pipeline.run_sql 00_schema.sql
  python -m pipeline.run_sql --dataset hillstrom 15_split.sql 20_scores.sql
  python -m pipeline.run_sql --dataset lenta --print 20_scores.sql   (render only)
"""

from __future__ import annotations

import argparse

from app.config import DATASETS, get_dataset
from app.db import read_sql, render, run_script
from pipeline.common import pipeline_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--dataset", choices=list(DATASETS))
    parser.add_argument("--print", action="store_true", help="print the rendered SQL instead of running it")
    args = parser.parse_args()
    ds = get_dataset(args.dataset) if args.dataset else None

    if args.print:
        for f in args.files:
            print(render(read_sql(f), ds))
        return

    c = pipeline_connection()
    for f in args.files:
        run_script(c, f, ds)


if __name__ == "__main__":
    main()
