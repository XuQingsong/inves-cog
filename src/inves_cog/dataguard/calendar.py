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


def _easter(year):
    """Gregorian Easter Sunday (Anonymous computus) — deterministic, no external data."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def ecb_target_holiday(day):
    """TARGET closing days: New Year, Good Friday, Easter Monday, 1 May, 25/26 Dec."""
    if (day.month, day.day) in {(1, 1), (5, 1), (12, 25), (12, 26)}:
        return True
    easter = _easter(day.year)
    return day == easter - timedelta(days=2) or day == easter + timedelta(days=1)


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
