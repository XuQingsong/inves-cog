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


def test_periodic_job_query_requires_a_completed_attempt_not_a_running_pid():
    item = Expectation(
        dataset="x",
        table="ingest.job_runs",
        date_column="trade_date",
        deadline_et="04:00",
        cadence="intraday:1",
        key_column="task_name",
        value_column="status",
        latest_column="ended_at",
    )
    sql, _ = query(item, date(2026, 11, 5), date(2026, 11, 6))
    assert "status<>'running'" in sql and "ended_at IS NOT NULL" in sql


def test_confirmed_soxx_action_is_exempt_but_unknown_shock_still_warns():
    _, items = load("config/data_expectations.yaml")
    item = next(i for i in items if i.dataset == "指数与半导体基金日线")
    day = date(2026, 11, 5)
    current = [dict(key=k, value=131.9 if k == "SOXX" else 100, n=1) for k in item.expected_keys]
    old = [dict(key=k, value=450.41 if k == "SOXX" else 100, n=1) for k in item.expected_keys]
    assert findings(item, day, {day: current, date(2026, 11, 4): old}) == []
    assert findings(item, date(2026, 11, 6), {date(2026, 11, 6): current, day: old})[0].kind == "suspect"


def test_barometer_row_with_partial_inputs_is_not_healthy_just_because_fear_is_a_number():
    item = Expectation(
        dataset="晴雨表",
        table="flows.barometer_daily",
        date_column="date",
        deadline_et="20:45",
        value_column="fear",
        quality_column="missing",
    )
    day = date(2026, 11, 5)
    got = findings(item, day, {day: [dict(key="all", value=70, n=1, quality=["信用利差"])]})
    assert got[0].kind == "partial" and got[0].detail["missing_fields"] == ["信用利差"]


def test_fresh_upstream_vix_does_not_hide_an_old_cached_barometer_input():
    from inves_cog.dataguard.reader import barometer_drift

    day = date(2026, 11, 5)
    got = barometer_drift("晴雨表日报", day, 16.61, 28.18)
    assert got.kind == "stale" and got.detail["cached_value"] == 16.61
    assert barometer_drift("晴雨表日报", day, 28.18, 28.18) is None
