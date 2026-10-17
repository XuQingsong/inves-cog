"""Divergence labels exist only on the deadline or once the case is verified."""

import math
from datetime import date, datetime, timedelta

_LAGS = (7, 30, 60, 90)
_EPS_FIELDS = ("当季", "下季", "当年", "次年")


def consensus_lookback(reading):
    """Four calendar lags. A missing day stays missing, and this does not name a revision band."""
    if reading is None:
        return None
    as_of = _on(reading.get("as_of"))
    snapshots = reading.get("snapshots")
    if as_of is None or snapshots is None:
        return None
    by_day = _snapshot_days(snapshots)
    current = by_day.get(as_of)
    if current is None:
        return None
    lags = {}
    for days in _LAGS:
        prior = by_day.get(as_of - timedelta(days=days))
        lags[f"day_{days}"] = {field: _lag_cell(current.get(field), prior, field) for field in _EPS_FIELDS}
    return {
        "lags": lags,
        "band": None,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


def _snapshot_days(snapshots):
    found = {}
    for row in snapshots:
        day = _on(row.get("on"))
        if day is None:
            continue
        levels = {field: row.get(field) if _number(row.get(field)) else None for field in _EPS_FIELDS}
        if day not in found:
            found[day] = levels
        elif found[day] != levels:
            found[day] = None
    return {day: levels for day, levels in found.items() if levels is not None}


def _lag_cell(current, prior, field):
    earlier = None if prior is None else prior.get(field)
    return {"prior": earlier, "change": _change(current, earlier)}


def _change(current, prior):
    if not _number(current) or not _number(prior) or prior == 0:
        return None
    return (current - prior) / prior


def _on(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def consensus_band(change, downgrades, upgrades, coverage):
    """Missing EPS consensus or coverage stays unknown. It is not 未下修."""
    breadth = coverage is not None and coverage > 0 and downgrades is not None
    if breadth and downgrades >= 0.3 * coverage:
        return "显著下修"
    if change is not None and change <= -0.03:
        return "显著下修"
    if change is None or not breadth or upgrades is None:
        return None
    if change > -0.02 and downgrades <= upgrades:
        return "未下修"
    return "其他"


def divergence_label(moment, price, consensus, fundamental, linkage, *, guidance_cut=False):
    if moment not in {"截止日", "已验证"}:
        return None
    if price is None or fundamental is None or linkage is None:
        return None
    if guidance_cut:
        revision = "显著下修"
    elif consensus is None:
        return None
    else:
        revision = consensus
    table = {
        ("大跌", "未下修", "未变", "已衰减"): "情绪性折价",
        ("大跌", "未下修", "未变", "已证伪"): "情绪性折价",
        ("大跌", "未下修", "未变", "估值倍数类"): "情绪性折价",
        ("大跌", "显著下修", "支持不利", "已验证·有影响"): "合理重定价",
        ("小跌或未跌", "显著下修", "支持不利", "已验证·有影响"): "滞后风险",
        ("大涨", "未上修", "未变", "估值倍数类"): "情绪性溢价",
        ("大涨", "显著上修", "支持有利", "已验证正向"): "基本面驱动上涨",
    }
    return table.get((price, revision, fundamental, linkage))
