"""SQL templates render cleanly for every dataset (no database needed)."""

import pytest

from app.config import DATASETS
from app.db import metric_sql, named_queries, query_id, read_sql, render, statements

SCRIPTS = ["00_schema.sql", "15_split.sql", "20_scores.sql"]


@pytest.mark.parametrize("ds", DATASETS.values(), ids=list(DATASETS))
def test_scripts_render(ds):
    for f in [*SCRIPTS, ds.raw_sql, ds.frame_sql]:
        sql = render(read_sql(f), ds)
        assert "{{" not in sql.replace("{{BUCKET}}", "")  # the bucket marker is filled in by run_script
        assert statements(sql)


@pytest.mark.parametrize("ds", DATASETS.values(), ids=list(DATASETS))
def test_metric_queries_render(ds):
    for name in named_queries("30_metrics.sql"):
        sql = metric_sql(name, ds)
        assert "{{" not in sql
        assert f"PROMOLENS.{ds.prefix}_" in sql or name == "health_tables"


def test_unpivot_has_one_branch_per_feature():
    ds = DATASETS["lenta"]
    sql = render(read_sql("20_scores.sql"), ds)
    assert sql.count("UNION ALL SELECT client_id") == len(ds.features) - 1


def test_query_id_is_sha1_of_text():
    import hashlib

    assert query_id("SELECT 1") == hashlib.sha1(b"SELECT 1").hexdigest()
    assert len(query_id("SELECT 1")) == 40


def test_statement_split_ignores_comment_only_chunks():
    assert statements("-- hi;\nSELECT 1;\n-- trailing\n") == ["SELECT 1"]


def test_lenta_feature_count_within_limit():
    # at most 40 numeric features plus gender and store format
    ds = DATASETS["lenta"]
    numeric = [f for f in ds.feature_names if f not in {"gender_f", "gender_m", "main_format"}]
    assert len(numeric) <= 40
