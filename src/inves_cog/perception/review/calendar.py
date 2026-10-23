"""Trading-day shifts and the shared visibility cutoff. Callers inject the clock."""

from datetime import datetime, time, timedelta

from inves_cog.ingest.market import NY, next_trading_day, trading_day

HORIZONS = (("T+1", 1), ("T+5", 5), ("T+20", 20))


def is_session(day):
    return bool(trading_day(day))


def add_sessions(day, count):
    cursor = day
    for _ in range(count):
        cursor = next_trading_day(cursor)
    return cursor


def cutoff(day):
    """ET calendar D+1 01:00. Daylight time is Beijing D+1 13:00; standard time is 14:00."""
    return datetime.combine(day + timedelta(days=1), time(1, 0), tzinfo=NY)
