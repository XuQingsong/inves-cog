"""Small validated XNYS schedule: the resident guard never imports pandas/numpy.
Generated offline by scripts/build_data_guard_calendar.py using the existing dependency.
Out-of-range dates fail explicitly, rather than inventing trading sessions.
"""

import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


@lru_cache(maxsize=1)
def _calendar():
    return json.loads(Path(__file__).with_name("sessions.json").read_text())


def trading_day(day):
    value = _calendar()
    if not date.fromisoformat(value["start"]) <= day <= date.fromisoformat(value["end"]):
        raise ValueError("数据守护交易日历超出覆盖范围，需要更新日历")
    return str(day) in value["sessions"]


def next_trading_day(day):
    day += timedelta(days=1)
    while not trading_day(day):
        day += timedelta(days=1)
    return day


@lru_cache(maxsize=4096)
def regular_bounds(day):
    if not trading_day(day):
        return None
    return tuple(datetime.fromisoformat(s) for s in _calendar()["sessions"][str(day)])
