"""Fetch the public Hillstrom and Lenta datasets with scikit-uplift.

X5 RetailHero is not fetched here: place its CSVs in data/X5-RetailHero/ by hand
(see README). Lenta is roughly 200 MB compressed; Hillstrom is a few MB.
"""

from __future__ import annotations

import argparse

from sklift.datasets import fetch_hillstrom, fetch_lenta

from app.config import DATA_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["hillstrom", "lenta", "all"], default="all")
    args = parser.parse_args()

    if args.dataset in ("hillstrom", "all"):
        home = DATA_DIR / "Hillstrom"
        home.mkdir(parents=True, exist_ok=True)
        bunch = fetch_hillstrom(data_home=str(home), return_X_y_t=False)
        print(f"hillstrom: {len(bunch.data):,} rows -> {home}")

    if args.dataset in ("lenta", "all"):
        home = DATA_DIR / "Lenta"
        home.mkdir(parents=True, exist_ok=True)
        bunch = fetch_lenta(data_home=str(home), return_X_y_t=False)
        print(f"lenta: {len(bunch.data):,} rows -> {home}")

    for path in sorted(DATA_DIR.rglob("*")):
        if path.is_file() and "X5" not in str(path):
            print(f"  {path.relative_to(DATA_DIR)}  {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
