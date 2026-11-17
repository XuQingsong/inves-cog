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
    lv = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lv) // 451
    month = (h + lv - 7 * m + 114) // 31
    day = ((h + lv - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def ecb_target_holiday(day):
    """TARGET closing days: New Year, Good Friday, Easter Monday, 1 May, 25/26 Dec."""
    if (day.month, day.day) in {(1, 1), (5, 1), (12, 25), (12, 26)}:
        return True
    easter = _easter(day.year)
    return day == easter - timedelta(days=2) or day == easter + timedelta(days=1)


def _nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def us_federal_holiday(day):
    """US federal holidays, including observed dates, for sources closed by the federal calendar."""
    fixed = {(1, 1), (6, 19), (7, 4), (11, 11), (12, 25)}
    if (day.month, day.day) in fixed:
        return True
    for year in {day.year - 1, day.year, day.year + 1}:
        for month, month_day in fixed:
            actual = date(year, month, month_day)
            observed = (
                actual - timedelta(days=1)
                if actual.weekday() == 5
                else actual + timedelta(days=1)
                if actual.weekday() == 6
                else actual
            )
            if day == observed:
                return True
    if day == _nth_weekday(day.year, 1, 0, 3):
        return True
    if day == _nth_weekday(day.year, 2, 0, 3):
        return True
    if day == _nth_weekday(day.year, 9, 0, 1):
        return True
    if day == _nth_weekday(day.year, 10, 0, 2):
        return True
    if day == _nth_weekday(day.year, 11, 3, 4):
        return True
    last = date(day.year, 5, 31)
    return day == last - timedelta(days=(last.weekday() - 0) % 7)


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
