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


def test_leveraged_etf_threshold_scales_by_sanity_leverage():
    item = expected(sanity=0.25, sanity_leverage={"SOXL": 3, "TQQQ": 3})
    current = [{"key": "SOXL", "value": 40.87}]
    previous = [{"key": "SOXL", "value": 66.68}]
    assert evaluate(item, D, current, previous) == []
    current = [{"key": "SOXL", "value": 10.0}]
    previous = [{"key": "SOXL", "value": 66.68}]
    assert evaluate(item, D, current, previous)[0].kind == "suspect"


def test_split_ratio_move_is_suspect_even_within_leverage_threshold():
    # A real 3:1 split on a 3x ETF lands inside the scaled threshold but must still flag.
    item = expected(sanity=0.25, sanity_leverage={"SOXL": 3})
    current = [{"key": "SOXL", "value": 133.0}]
    previous = [{"key": "SOXL", "value": 400.0}]
    gap = evaluate(item, D, current, previous)[0]
    assert gap.kind == "suspect"
    assert gap.detail["evidence"][0]["split_like"] is True
    assert evaluate(item, D, current, previous, actions={"SOXL"}) == []


def test_unleveraged_move_matching_no_ratio_still_needs_threshold():
    item = expected(sanity=0.25)
    current = [{"key": "SMH", "value": 300.0}]
    previous = [{"key": "SMH", "value": 400.0}]
    assert evaluate(item, D, current, previous) == []
    current = [{"key": "SMH", "value": 290.0}]
    assert evaluate(item, D, current, previous)[0].kind == "suspect"


def test_partial_coverage_uses_previous_five_median_not_one_bad_day():
    item = expected(min_coverage=0.9)
    gap = evaluate(item, D, [{"key": str(i)} for i in range(40)], [], prior_counts=[100, 101, 99, 1, 100])[0]
    assert gap.kind == "partial"
    assert gap.detail["expected_rows"] == 90


def test_configuration_never_allows_sql_identifier_injection():
    with pytest.raises(ValueError):
        Expectation(dataset="bad", table="flows.observations; DELETE", date_column="date", deadline_et="20:45")


def test_null_value_is_partial_even_when_a_row_exists():
    item = expected(value_column="value")
    assert evaluate(item, D, [{"key": "VIX", "value": None}], [])[0].kind == "partial"


def test_nonfinite_current_value_is_suspect_without_needing_previous_value():
    item = expected(value_column="value")
    assert evaluate(item, D, [{"key": "VIX", "value": float("nan")}], [])[0].kind == "suspect"


def test_review_period_deadline_uses_last_exchange_session_not_calendar_month_end():
    item = expected(cadence="monthly", period_end="month", release_days=1)
    # October 2026 ends Saturday; Friday's review is due on Saturday evening ET.
    days = due_dates(item, datetime(2026, 11, 1, 3, tzinfo=timezone.utc), lookback=5)
    assert date(2026, 10, 30) in days and date(2026, 10, 31) not in days


def test_financial_state_behind_a_known_qualifying_filing_is_partial():
    item = expected(carry_forward=True, key_column="ticker")
    got = evaluate(item, D, [{"key": "AAA", "day": date(2026, 10, 1), "expected_filed": D}], [])
    assert got[0].kind == "partial"
    assert got[0].detail["outdated_filings"][0]["expected_filed"] == "2026-11-05"


def test_multiple_partial_reasons_still_produce_one_gap_per_kind():
    item = expected(value_column="fear", quality_column="missing")
    got = evaluate(item, D, [{"key": "all", "value": None, "quality": ["信用利差"]}], [])
    assert [r.kind for r in got] == ["partial"]
    assert got[0].detail["missing_fields"] == ["信用利差"]


def test_ecb_target_holidays_are_not_due_for_jpy_series():
    from datetime import date

    from inves_cog.dataguard.calendar import ecb_target_holiday

    # Good Friday 2026-04-03, Easter Monday 2026-04-06, May 1, Dec 25/26
    for d in [date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 12, 25), date(2026, 12, 26)]:
        assert ecb_target_holiday(d), d
    assert not ecb_target_holiday(date(2026, 4, 7))
    assert not ecb_target_holiday(date(2026, 11, 5))
    item = expected(holiday_calendar="ecb")
    from datetime import datetime, timezone

    now = datetime(2026, 4, 7, 17, 0, tzinfo=timezone.utc)
    due = due_dates(item, now, lookback=10)
    # Easter Monday is a US trading day but a TARGET holiday — must not be due
    assert date(2026, 4, 6) not in due
    # a normal trading day still becomes due
    assert date(2026, 4, 7) in due or date(2026, 4, 2) in due
