from datetime import date, datetime, timezone

import pytest


@pytest.mark.phase1_blocking
def test_observed_publish_date_only_when_on_time():
    from inves_cog.ingest.sources import observed_publish_date

    # Settlement 2026-10-15 (Thu); inferred publish ~+9 sessions -> 10-28ish.
    # On-time observation within tolerance is written.
    assert observed_publish_date("2026-10-15", date(2026, 10, 27)) == "2026-10-27"
    # A backfill observed months later stays NULL (reader falls back to inference).
    assert observed_publish_date("2025-01-15", date(2026, 11, 9)) is None


@pytest.mark.phase1_blocking
def test_semimonthly_cadence_settlement_days():
    from pathlib import Path

    from inves_cog.dataguard.core import due_dates
    from inves_cog.dataguard.reader import load

    _, all_items = load(Path("config/data_expectations.yaml"))
    items = [i for i in all_items if i.table == "ingest.short_interest"]
    assert items, "semimonthly expectation must parse"
    item = items[0]
    # 2026-11-15 is Sunday -> mid-month settlement rolls back to Friday 11-13.
    # Long lookback now so a Nov settlement is already due.
    due = due_dates(item, datetime(2026, 12, 20, 12, tzinfo=timezone.utc), lookback=60)
    assert date(2026, 11, 13) in due  # Friday, rolled back from Sunday 15th
    assert date(2026, 11, 15) not in due
    assert date(2026, 11, 30) in due  # month-end (Monday, trading day)
