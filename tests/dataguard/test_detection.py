"""Failure-first regressions for the actual A-032 incident shapes; offline clocks."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from inves_cog.dataguard.core import Expectation, due_dates, evaluate

pytestmark = pytest.mark.phase1_blocking
D = date(2026, 11, 5)
NOW = datetime(2026, 11, 6, 15, tzinfo=timezone.utc)


def expected(**kw):
    return Expectation(
        dataset="波动率", table="flows.observations", date_column="obs_date", deadline_et="20:45", grace_min=15, **kw
    )


def test_before_deadline_and_weekend_and_holiday_are_not_missing():
    item = expected()
    assert D not in due_dates(item, datetime(2026, 11, 6, 1, 55, tzinfo=timezone.utc), lookback=1)
    days = due_dates(item, datetime(2026, 11, 28, 15, tzinfo=timezone.utc), lookback=5)
    assert date(2026, 11, 26) not in days  # Thanksgiving
    assert date(2026, 11, 28) not in days


def test_fall_dst_deadline_and_next_session_release():
    item = expected(release_sessions=1)
    assert D not in due_dates(item, NOW, lookback=3)
    assert D in due_dates(item, datetime(2026, 11, 7, 3, tzinfo=timezone.utc), lookback=3)


def test_empty_short_volume_is_missing_not_healthy_zero():
    gaps = evaluate(expected(), D, [], [])
    assert [g.kind for g in gaps] == ["missing"]


def test_identical_vix_is_stale_but_absent_previous_is_not():
    item = expected(staleness=True)
    rows = [{"key": "VIX", "value": Decimal("19.5")}]
    assert evaluate(item, D, rows, rows)[0].kind == "stale"
    assert evaluate(item, D, rows, []) == []


def test_credit_partial_requires_every_configured_series():
    item = expected(expected_keys=("HYG", "IEF"))
    gap = evaluate(item, D, [{"key": "HYG", "value": 80}], [])[0]
    assert gap.kind == "partial"
    assert gap.detail["missing_keys"] == ["IEF"]


def test_soxx_raw_drop_is_suspect_without_corporate_action():
    item = expected(sanity=0.25)
    current = [{"key": "SOXX", "value": 80}]
    previous = [{"key": "SOXX", "value": 273}]
    gap = evaluate(item, D, current, previous)[0]
    assert gap.kind == "suspect"
    assert gap.detail["evidence"][0]["previous"] == 273
    assert evaluate(item, D, current, previous, actions={"SOXX"}) == []


def test_partial_coverage_uses_previous_five_median_not_one_bad_day():
    item = expected(min_coverage=0.9)
    gap = evaluate(item, D, [{"key": str(i)} for i in range(40)], [], prior_counts=[100, 101, 99, 1, 100])[0]
    assert gap.kind == "partial"
    assert gap.detail["expected_rows"] == 90


def test_configuration_never_allows_sql_identifier_injection():
    with pytest.raises(ValueError):
        Expectation(dataset="bad", table="flows.observations; DELETE", date_column="date", deadline_et="20:45")
