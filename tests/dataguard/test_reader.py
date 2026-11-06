from datetime import date, datetime, timezone

import pytest

from inves_cog.dataguard.core import Expectation, Finding
from inves_cog.dataguard.reader import findings, load, query

pytestmark = pytest.mark.phase1_blocking


def test_all_datasets_have_basis_impact_and_detect_only_default():
    config, items = load("config/data_expectations.yaml")
    assert config["detect_only"] is True
    assert len(items) >= 30
    assert all(i.basis and i.impact for i in items)
    assert any(i.table == "flows.short_volume" for i in items)


def test_timestamp_bounds_are_on_original_indexed_column_and_filters_are_bound():
    item = Expectation(
        dataset="x",
        table="flows.option_chain",
        date_column="snapshot_at",
        deadline_et="16:30",
        timestamp=True,
        key_column="underlying",
        filter={"underlying": ["x'; DROP SCHEMA flows"]},
    )
    lower = datetime(2026, 11, 5, tzinfo=timezone.utc)
    upper = datetime(2026, 11, 6, tzinfo=timezone.utc)
    sql, args = query(item, lower, upper)
    assert "snapshot_at>=%s AND snapshot_at<%s" in sql
    assert "DROP SCHEMA" not in sql and args[-1] == ["x'; DROP SCHEMA flows"]


def test_latest_failed_job_is_a_failure_not_success_from_count_nonzero():
    item = Expectation(dataset="任务", table="ingest.job_runs", date_column="trade_date", deadline_et="20:45")
    day = date(2026, 11, 5)
    got = findings(item, day, {day: [dict(key="bars_full", value="failed", n=1)]})
    assert len(got) == 1 and isinstance(got[0], Finding) and got[0].kind == "job_failed"
