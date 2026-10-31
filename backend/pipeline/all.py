"""Run the whole pipeline for one dataset: load, features, train, bootstrap, evaluate.

  python -m pipeline.all --dataset hillstrom
"""

from __future__ import annotations

from pipeline import bootstrap, evaluate, features, load, train
from pipeline.common import dataset_arg


def main() -> None:
    ds = dataset_arg(__doc__)
    for step in (load, features, train, bootstrap, evaluate):
        step.run(ds)


if __name__ == "__main__":
    main()
