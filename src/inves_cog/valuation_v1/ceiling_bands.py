"""Versioned ceiling bands, calibrated from 52 visible weekly cross sections."""

import math
from datetime import date, timedelta
from statistics import median


def finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def calibrate(rows, *, as_of, source):
    end = as_of - timedelta(days=(as_of.weekday() - 4) % 7)
    start = end - timedelta(weeks=51)
    expected = {start + timedelta(weeks=w) for w in range(52)}
    weeks, seen = {}, set()
    for row in rows:
        day = date.fromisoformat(str(row["date"])[:10])
        if day not in expected:
            continue
        key = (day, row["ticker"])
        if key in seen:
            raise ValueError("duplicate ticker/week in calibration panel")
        seen.add(key)
        value = finite(row.get("m8"))
        if value is not None and value > 0:
            weeks.setdefault(day, []).append(value)
    if set(weeks) != expected:
        raise ValueError("calibration requires 52 complete weekly cross sections")
    return {
        "version": "ceiling-bands-v1-" + str(as_of),
        "calibration_date": str(as_of),
        "source": source,
        "discount_rate": 0.08,
        "window_start": str(start),
        "window_end": str(end),
        "week_count": len(weeks),
        "sample_count": sum(map(len, weeks.values())),
        "quantile_method": "linear; median of 52 weekly cross-sectional quantiles",
        "thresholds": {
            "p60": median(quantile(v, 0.6) for v in weeks.values()),
            "p80": median(quantile(v, 0.8) for v in weeks.values()),
        },
        "weekly_samples": {str(day): len(weeks[day]) for day in sorted(weeks)},
    }


def classify_band(m, config):
    value = finite(m)
    if value is None or value <= 0:
        return "不适用"
    thresholds = config["thresholds"]
    if value >= thresholds["p80"]:
        return "严重透支"
    return "偏高" if value >= thresholds["p60"] else "可信"
