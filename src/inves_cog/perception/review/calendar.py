"""Trading-day shifts and the Shanghai visibility cutoff. The clock is injected by callers."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import next_trading_day, trading_day

SHANGHAI = ZoneInfo("Asia/Shanghai")
HORIZONS = (("T+1", 1), ("T+5", 5), ("T+20", 20))


def is_session(day):
    return bool(trading_day(day))


def add_sessions(day, count):
    cursor = day
    for _ in range(count):
        cursor = next_trading_day(cursor)
    return cursor


def cutoff(day):
    start = datetime.combine(day, time.min, tzinfo=SHANGHAI)
    return start + timedelta(days=1)
