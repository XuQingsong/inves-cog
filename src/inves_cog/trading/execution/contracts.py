"""Order reasons, membership and the read-only, tightening-only overlay contract."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from inves_cog.trading.execution.state import PARAMS

NY = ZoneInfo("America/New_York")


def validate_order(order):
    rules = order.get("rule_ids", [])
    text = order.get("reason_zh", "")
    if not rules or not all(re.fullmatch(r"M-\d{2}", r) for r in rules):
        raise ValueError("I05: order requires M rule identifiers")
    if not re.search(r"[\u4e00-\u9fff]", text) or not text.startswith(rules[0]):
        raise ValueError("I05: reason requires rule identifier and Chinese explanation")
    if any(token in text for token in ("悲观", "中性", "乐观", "目标价", "p=", "估值区间")):
        raise ValueError("I05: valuation scenarios cannot enter execution reasons")


def members_asof(universe, day):
    result = []
    for row in universe:
        first = row.get("listed_on", row.get("first_trade_date"))
        first = date.fromisoformat(first) if isinstance(first, str) else first
        if first is None or first <= day:
            result.append(row["ticker"])
    return result


def overlay_state(overlay, day, *, asof=None):
    if not overlay or not overlay.get("generated_at"):
        return {"version": None, "status": "missing", "errors": []}, {}
    stamp = overlay["generated_at"]
    stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else stamp
    floor = datetime.combine(day, datetime.min.time(), NY).replace(hour=6)
    if stamp.tzinfo is not None and asof is not None and stamp > asof:
        return {"version": overlay.get("version"), "status": "missing", "errors": ["future_overlay"]}, {}
    if stamp.tzinfo is None or stamp < floor:
        return {"version": overlay.get("version"), "status": "stale", "errors": []}, {}
    errors = []
    for ticker, row in overlay.get("tickers", {}).items():
        if row.get("first_lot_multiplier", 1) > 1 or row.get("increase_qty") or row.get("sell"):
            errors.append(ticker + ": increase/sell overlay request ignored")
    return {"version": overlay.get("version"), "status": "ok", "errors": errors}, overlay.get("tickers", {})


def coverage(tradable, with_bars):
    pct = with_bars / tradable * 100 if tradable else 100.0
    return {"tradable": tradable, "with_bars": with_bars, "pct": pct}, pct >= PARAMS["coverage_floor_pct"]
