from datetime import date, timedelta

import pytest

from inves_cog.dataguard.calendar import regular_bounds, trading_day
from inves_cog.ingest.market import exchange

pytestmark = pytest.mark.phase1_blocking


def test_whole_year_matches_existing_exchange_dependency_and_early_closes():
    calendar = exchange(2026)
    for offset in range(365):
        day = date(2026, 1, 1) + timedelta(days=offset)
        assert trading_day(day) == calendar.is_session(str(day))
        if trading_day(day):
            first, last = regular_bounds(day)
            assert first == calendar.session_open(str(day)).to_pydatetime()
            assert last == calendar.session_close(str(day)).to_pydatetime()


def test_out_of_range_is_unknown_not_a_guessed_weekday():
    with pytest.raises(ValueError):
        trading_day(date(2040, 1, 3))
