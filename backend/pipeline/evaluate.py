"""Evaluate on the holdout with the same SQL the API uses, and print the results.

  python -m pipeline.evaluate --dataset hillstrom|lenta|x5

Also cross-checks the Qini score with scikit-uplift on the fetched holdout scores.
"""

from __future__ import annotations

from app.config import SCHEMA, Dataset
from app.db import connect
from app.services import metrics
from app.services.stats import verdict
from pipeline.common import banner, dataset_arg


def _f(v: float | None, spec: str) -> str:
    return "n/a" if v is None else format(v, spec)


def run(ds: Dataset) -> None:
    banner(f"evaluate {ds.id}")

    s = metrics.metric(ds, "summary", cache=False)
    print("  split summary:")
    for r in s["rows"]:
        print(f"    {r['part']:<9} n={r['n']:>8,}  treated rate {_f(r['treated_rate'], '.4f')}  control rate {_f(r['control_rate'], '.4f')}  mean est. p0 {_f(r['mean_p0'], '.4f')}")

    d = metrics.metric(ds, "deciles", cache=False)
    print(f"\n  decile table (holdout, ranked by estimated uplift)  query_id={d['query_id'][:12]} {d['elapsed_ms']} ms")
    print("    dec      n   treated   control  observed  predicted   95% band")
    for r in d["rows"]:
        print(
            f"    {r['decile']:>3} {r['n']:>6,}  {_f(r['treated_rate'], '8.4f')}  {_f(r['control_rate'], '8.4f')}  "
            f"{_f(r['observed_uplift'], '+8.4f')}  {_f(r['predicted_uplift'], '+9.4f')}   [{_f(r['lo'], '+.4f')}, {_f(r['hi'], '+.4f')}]"
        )

    print(f"\n  extra {ds.outcome_plural} per 1,000 contacted (holdout)")
    print("      k  uplift model              likely buyers             random                    est. share acting anyway (uplift / buyers)")
    for k in (5, 10, 20, 30, 50, 100):
        rows = {r["strategy"]: r for r in metrics.metric(ds, "overview", {"budget": k}, cache=False)["rows"]}

        def cell(name: str, rows: dict = rows) -> str:
            r = rows[name]
            return f"{_f(r['per_1000'], '+7.1f')} [{_f(r['lo'], '+.1f')}, {_f(r['hi'], '+.1f')}]".ljust(26)

        print(f"    {k:>3}  {cell('uplift')}{cell('likely_buyers')}{cell('random')}{_f(rows['uplift']['share_anyway'], '.1%')} / {_f(rows['likely_buyers']['share_anyway'], '.1%')}")

    p = metrics.metric(ds, "proof", {"budget": 20}, cache=False)
    print("\n  at 20% contacted, uplift model minus:")
    for r in p["rows"]:
        print(f"    {r['versus']:<14} {_f(r['diff_per_1000'], '+.1f')} per 1,000  [{_f(r['lo'], '+.1f')}, {_f(r['hi'], '+.1f')}]  {verdict(r['lo'], r['hi'])}")

    q = metrics.metric(ds, "qini", cache=False)
    print("\n  Qini coefficient (percent grid, SQL):")
    for r in q["rows"]:
        print(f"    {r['strategy']:<14} {_f(r['qini_coefficient'], '+.5f')}")

    g = metrics.metric(ds, "groups", cache=False)
    print(f"\n  estimated groups (u = {ds.u}, p0 cut = {ds.p0_cut}); observed rates are holdout only")
    for r in g["rows"]:
        print(
            f"    {metrics.GROUPS[r['grp']]:<22} {r['n']:>8,} ({r['share']:.1%})  est. uplift {r['mean_uplift']:+.4f}  "
            f"holdout treated {_f(r['holdout_treated_rate'], '.4f')} vs control {_f(r['holdout_control_rate'], '.4f')}"
        )

    try:
        from sklift.metrics import qini_auc_score

        c = connect()
        h = c.export_to_pandas(f"SELECT treatment, target, uplift FROM {SCHEMA}.{ds.prefix}_SCORES WHERE part = 'holdout'")
        h.columns = [col.lower() for col in h.columns]
        sk = qini_auc_score(h["target"].astype(int), h["uplift"], h["treatment"].astype(int))
        print(f"\n  cross-check: scikit-uplift qini_auc_score (normalised) = {sk:+.4f}")
    except Exception as exc:  # cross-check is informative only
        print(f"\n  cross-check skipped: {exc}")


if __name__ == "__main__":
    run(dataset_arg(__doc__))
