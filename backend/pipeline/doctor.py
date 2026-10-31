"""Check the environment: venv, packages, .env, Exasol, schema and data files.

  python -m pipeline.doctor
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import DATA_DIR, ROOT, SCHEMA

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    return ok


def main() -> None:
    venv = (ROOT / "venv").resolve()
    check("python venv", Path(sys.prefix).resolve() == venv, f"{sys.prefix} (expected {venv})")

    for mod in ("pyexasol", "fastapi", "sklearn", "sklift", "pandas", "numpy"):
        try:
            m = importlib.import_module(mod)
            check(f"package {mod}", True, getattr(m, "__version__", ""))
        except ImportError as exc:
            check(f"package {mod}", False, str(exc))

    env_ok = check(".env present", (ROOT / ".env").exists(), str(ROOT / ".env"))

    if env_ok:
        try:
            from app.db import connect

            c = connect(open_schema=False)
            check("Exasol SELECT 1", c.execute("SELECT 1").fetchval() == 1, f"session {c.session_id()}")
            version = c.execute(
                "SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME = 'databaseProductVersion'"
            ).fetchval()
            check("Exasol version", True, str(version))
            n = c.execute("SELECT COUNT(*) FROM EXA_SCHEMAS WHERE SCHEMA_NAME = {s}", {"s": SCHEMA}).fetchval()
            check(f"schema {SCHEMA}", True, "exists" if n else "not created yet (pipeline creates it)")
        except Exception as exc:
            check("Exasol SELECT 1", False, f"{type(exc).__name__}: {exc}")

    files = {
        "X5 clients.csv": DATA_DIR / "X5-RetailHero" / "clients.csv",
        "X5 products.csv": DATA_DIR / "X5-RetailHero" / "products.csv",
        "X5 purchases.csv": DATA_DIR / "X5-RetailHero" / "purchases.csv",
        "X5 uplift_train.csv": DATA_DIR / "X5-RetailHero" / "uplift_train.csv",
        "X5 uplift_test.csv": DATA_DIR / "X5-RetailHero" / "uplift_test.csv",
        "Hillstrom": DATA_DIR / "Hillstrom" / "hillstorm_no_indices.csv.gz",
        "Lenta": DATA_DIR / "Lenta" / "lenta_dataset.csv.gz",
    }
    for name, path in files.items():
        hint = "" if path.exists() else "  -> python -m pipeline.download" if "X5" not in name else "  -> see README, data steps"
        check(f"data {name}", path.exists(), (f"{path.stat().st_size / 1e6:,.1f} MB" if path.exists() else "missing") + hint)

    node = shutil.which("node")
    if node:
        v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
        check("node 20+", int(v.lstrip("v").split(".")[0]) >= 20, v)
    else:
        check("node 20+", False, "node not on PATH (needed for the frontend only)")

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
