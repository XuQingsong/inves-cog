"""Per-ticker shadow-vs-Rule-A comparison for the account page.

Read-only, PIT-scoped: rows are only used when their generation timestamp is
visible at the caller's cutoff. Shadow artifacts are gates and coefficients,
never orders, so every hypothetical result is a labelled simulation — the
summary sign convention is that a positive delta means the shadow would have
done better.
"""

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.valuation_v1.calculations import settings

ROOT = Path(__file__).resolve().parents[3]
LABELS = yaml.safe_load((ROOT / "config" / "data" / "shadow_labels.yaml").read_text())
_NY = ZoneInfo("America/New_York")

_BUY = ("buy_to", "buy_swing", "buy_watch")


def _json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _factor_value(payload):
    data = _json(payload)
    if isinstance(data, dict):
        data = data.get("value")
    return _num(data)


def divergence_counts(connection, day, cutoff):
    """Same-day factor verdicts: divergent only when both sides evaluated."""
    row = connection.execute(
        """
        SELECT count(*) FILTER (
                   WHERE would_pass IS NOT NULL AND rule_a_entry_pass IS NOT NULL) AS evaluated,
               count(*) FILTER (
                   WHERE would_pass IS NOT NULL AND rule_a_entry_pass IS NOT NULL
                     AND would_pass <> rule_a_entry_pass) AS divergent,
               count(*) FILTER (
                   WHERE would_pass IS NULL OR rule_a_entry_pass IS NULL) AS unevaluable
        FROM factor_shadow.daily
        WHERE date = %s AND generated_at < %s
        """,
        (day, cutoff),
    ).fetchone()
    return {
        "evaluated": row["evaluated"],
        "divergent": row["divergent"],
        "unevaluable": row["unevaluable"],
    }


def _default_cutoff(as_of):
    # Same convention as the page layer: ET D+1 01:00.
    return datetime.combine(as_of + timedelta(days=1), time(1, 0), tzinfo=_NY)


def _gate_reason(row, *, only=None):
    """Chinese gate sentences from config; `only` restricts to named gates."""
    c = settings()["shadow"]
    texts = LABELS["gate_reasons"]
    parts = []
    if row["vt1"] and only in (None, "vt1"):
        parts.append(texts["vt1"].format(p=c["vt1_p"]))
    if row["vt2"] and only in (None, "vt2"):
        parts.append(texts["vt2"].format(p=c["vt2_p"]))
    if row["v3_trim_flag"] and only in (None, "v3_trim"):
        parts.append(texts["v3_trim"].format(p=c["v3_p"]))
    return "；".join(parts)


def _inputs(connection, as_of, dates, cutoff):
    """PIT-scoped rows for the window; every artifact respects `cutoff`."""
    shadows = connection.execute(
        "SELECT trade_date, ticker, vt1, vt2, v1_score, v2_coef, v3_trim_flag "
        "FROM valuation_v1.shadow_rules WHERE trade_date = ANY(%s) AND observed_at <= %s",
        (dates, cutoff),
    ).fetchall()
    orders = connection.execute(
        "SELECT trade_date, ticker, status, qty, fill_price, reason_zh, "
        "intent->>'action' AS action, intent->>'label' AS label "
        "FROM trading.orders WHERE trade_date = ANY(%s)",
        (dates,),
    ).fetchall()
    positions = connection.execute(
        "SELECT l.trade_date, k AS ticker, "
        "(l.state->'positions'->k->>'shares')::float AS shares "
        "FROM trading.ledger l, LATERAL jsonb_object_keys(l.state->'positions') k "
        "WHERE l.phase = 'plan' AND l.extractor = 'fixed' AND l.rule_set = 'A' "
        "AND l.trade_date = ANY(%s) AND l.observed_at <= %s "
        "ORDER BY l.observed_at",
        (dates, cutoff),
    ).fetchall()
    factors = connection.execute(
        "SELECT date, ticker, factor_id, would_pass, rule_a_entry_pass, "
        "value, substituted_value, gap_detail "
        "FROM factor_shadow.daily WHERE date = ANY(%s) AND generated_at <= %s",
        (dates, cutoff),
    ).fetchall()
    plans = {
        str(row["trade_date"]): str(row["signal_date"])
        for row in connection.execute(
            "SELECT trade_date, signal_date FROM trading.plan WHERE trade_date = ANY(%s)",
            (dates,),
        ).fetchall()
    }
    scores = {}
    signal_dates = sorted(set(plans.values()))
    if signal_dates:
        for row in connection.execute(
            "SELECT signal_date, ticker, tier, entry_pass, valuation, growth, quality, timing, "
            "m31_adjusted_valuation FROM trading.daily_scores WHERE signal_date = ANY(%s) "
            "AND extractor='fixed' AND rule_set='A' AND params_version='p-2026.10'",
            (signal_dates,),
        ).fetchall():
            scores[(str(row["signal_date"]), row["ticker"])] = row
    tickers = sorted({row["ticker"] for row in shadows})
    bars = {}
    if tickers:
        for row in connection.execute(
            "SELECT ticker, trade_date, open, close FROM ingest.bars_daily "
            "WHERE ticker = ANY(%s) AND trade_date <= %s AND trade_date > %s "
            "ORDER BY ticker, trade_date",
            (tickers, as_of, min(dates) - timedelta(days=10)),
        ).fetchall():
            bars.setdefault(row["ticker"], {})[str(row["trade_date"])] = row

    held = {(str(p["trade_date"]), p["ticker"]): p["shares"] for p in positions}
    buys, sells, sells_by_ticker = {}, {}, {}
    for order in orders:
        key = (str(order["trade_date"]), order["ticker"])
        if order["action"] in _BUY:
            buys.setdefault(key, []).append(order)
        elif str(order["action"] or "").startswith("sell"):
            sells.setdefault(key, []).append(order)
            sells_by_ticker.setdefault(order["ticker"], []).append(order)
    return {
        "shadows": shadows,
        "factors": factors,
        "plans": plans,
        "scores": scores,
        "bars": bars,
        "held": held,
        "buys": buys,
        "sells": sells,
        "sells_by_ticker": sells_by_ticker,
    }


def _latest_close(bars, ticker):
    series = bars.get(ticker) or {}
    if not series:
        return None, None
    day = max(series)
    return _num(series[day]["close"]), day


def _terminal(sells_by_ticker, bars, ticker, after):
    """Earliest filled Rule A sell after `after`, else the latest close."""
    options = [
        row
        for row in sells_by_ticker.get(ticker, [])
        if str(row["trade_date"]) > str(after) and row["status"] == "filled" and row["fill_price"] is not None
    ]
    if options:
        row = min(options, key=lambda item: str(item["trade_date"]))
        return _num(row["fill_price"]), str(row["trade_date"])
    close, _day = _latest_close(bars, ticker)
    return close, None


def _blocked_buys(inputs):
    """Group A: shadow vetoed (vt1) yet Rule A had a buy that day."""
    rows = []
    for shadow in inputs["shadows"]:
        if not shadow["vt1"]:
            continue
        day = str(shadow["trade_date"])
        for order in inputs["buys"].get((day, shadow["ticker"]), []):
            row = {
                "date": day,
                "ticker": shadow["ticker"],
                "action_label": order.get("label") or order.get("action"),
                "rule_reason": order.get("reason_zh"),
                "status": order.get("status"),
                "status_label": LABELS["order_status"].get(order.get("status"), order.get("status")),
                "gate_reason": _gate_reason(shadow),
                "sold_on": None,
                "end_price": None,
                "close_price": _latest_close(inputs["bars"], shadow["ticker"])[0],
                "delta_usd": None,
                "delta_pct": None,
            }
            qty, fill = _num(order.get("qty")), _num(order.get("fill_price"))
            row["qty"], row["fill_price"] = qty, fill
            if order.get("status") == "filled" and qty and fill:
                end, sold_on = _terminal(inputs["sells_by_ticker"], inputs["bars"], shadow["ticker"], day)
                row["end_price"], row["sold_on"] = end, sold_on
                if end is not None:
                    row["delta_usd"] = qty * (fill - end)
                    row["delta_pct"] = (fill - end) / fill * 100
            rows.append(row)
    return rows


def _missed_trims(inputs):
    """Group B: shadow flagged a one-third trim; held at the time; Rule A did not sell that day."""
    rows = []
    for shadow in inputs["shadows"]:
        if not shadow["v3_trim_flag"]:
            continue
        day = str(shadow["trade_date"])
        shares = _num(inputs["held"].get((day, shadow["ticker"])))
        if shares is None or inputs["sells"].get((day, shadow["ticker"])):
            continue
        series = inputs["bars"].get(shadow["ticker"]) or {}
        next_day = next((d for d in sorted(series) if d > day), None)
        open_price = None if next_day is None else _num(series[next_day]["open"])
        end, sold_on = _terminal(inputs["sells_by_ticker"], inputs["bars"], shadow["ticker"], day)
        trim_shares = shares / 3
        delta_usd = delta_pct = None
        if open_price is not None and end is not None:
            delta_usd = trim_shares * (open_price - end)
            delta_pct = (open_price - end) / open_price * 100
        rows.append(
            {
                "date": day,
                "ticker": shadow["ticker"],
                "shares": shares,
                "trim_shares": trim_shares,
                "gate_reason": _gate_reason(shadow, only="v3_trim"),
                "open_date": next_day,
                "open_price": open_price,
                "end_price": end,
                "sold_on": sold_on,
                "delta_usd": delta_usd,
                "delta_pct": delta_pct,
            }
        )
    return rows


def _entry_divergence(inputs):
    """Group C: factor verdicts where both sides evaluated and disagreed.

    Collapsed to one row per ticker — the same names disagree every record
    day, so the row carries the span and the latest day's evidence.
    """
    book_of = LABELS["factor_books"]
    seen, factor_days, record_days = {}, set(), 0
    for row in inputs["factors"]:
        factor_days.add(str(row["date"]))
        if row["would_pass"] is None or row["rule_a_entry_pass"] is None:
            continue
        if row["would_pass"] == row["rule_a_entry_pass"]:
            continue
        record_days += 1
        book = book_of.get(row["factor_id"])
        score = inputs["scores"].get((inputs["plans"].get(str(row["date"])), row["ticker"])) or {}
        raw = score.get(book) if book else None
        effective = (
            score.get("m31_adjusted_valuation")
            if book == "valuation" and score.get("m31_adjusted_valuation") is not None
            else raw
        )
        shortfall = (_json(row.get("gap_detail")) or {}).get("book_shortfall") or {}
        seen.setdefault(row["ticker"], []).append(
            {
                "date": str(row["date"]),
                "direction": "影子放行、规则 A 拒绝" if row["would_pass"] else "影子拒绝、规则 A 放行",
                "factor_label": LABELS["factors"].get(row["factor_id"], row["factor_id"]),
                "book_label": LABELS["books"].get(book),
                "shadow_value": _factor_value(
                    row["substituted_value"] if row["substituted_value"] is not None else row["value"]
                ),
                "shadow_shortfall": _num(shortfall.get(book)) if book else None,
                "rule_book_value": _num(raw),
                "rule_effective_value": _num(effective),
                "tier_label": LABELS["tiers"].get(score.get("tier"), score.get("tier")),
                "would_pass": row["would_pass"],
            }
        )
    rows = []
    for ticker, items in seen.items():
        items.sort(key=lambda item: item["date"])
        latest = items[-1]
        directions = {item["direction"] for item in items}
        rows.append(
            {
                **latest,
                "ticker": ticker,
                "first_date": items[0]["date"],
                "days": len(items),
                "direction": latest["direction"] if len(directions) == 1 else "、".join(sorted(directions)),
            }
        )
    rows.sort(key=lambda item: (item["first_date"], item["ticker"]))
    return rows, factor_days, record_days


def _total(rows):
    parts = [row["delta_usd"] for row in rows if row["delta_usd"] is not None]
    return None if not parts else sum(parts)


def shadow_report(connection, as_of, *, days=20, cutoff=None):
    """Compare recorded shadow gates against the orders Rule A actually issued."""
    as_of = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of))
    cutoff = cutoff or _default_cutoff(as_of)
    dates = [
        row["trade_date"]
        for row in connection.execute(
            "SELECT DISTINCT trade_date FROM valuation_v1.shadow_rules "
            "WHERE trade_date <= %s ORDER BY trade_date DESC LIMIT %s",
            (as_of, days),
        ).fetchall()
    ]
    counts = divergence_counts(connection, as_of, cutoff)
    if not dates:
        return {
            "as_of": str(as_of),
            "days": 0,
            "counts": counts,
            "blocked_buys": [],
            "missed_trims": [],
            "entry_divergence": [],
            "summary": {
                "blocked_buys": 0,
                "missed_trims": 0,
                "entry_divergence": 0,
                "entry_divergence_days": 0,
                "blocked_delta_usd": None,
                "missed_trim_delta_usd": None,
                "factor_days": 0,
                "shadow_days": 0,
            },
            "reason": "影子估值记录暂缺",
        }
    inputs = _inputs(connection, as_of, dates, cutoff)
    blocked = sorted(_blocked_buys(inputs), key=lambda row: (row["date"], row["ticker"]))
    trims = sorted(_missed_trims(inputs), key=lambda row: (row["date"], row["ticker"]))
    entries, factor_days, record_days = _entry_divergence(inputs)
    return {
        "as_of": str(as_of),
        "days": len(dates),
        "counts": counts,
        "blocked_buys": blocked,
        "missed_trims": trims,
        "entry_divergence": entries,
        "summary": {
            "blocked_buys": len(blocked),
            "missed_trims": len(trims),
            "entry_divergence": len(entries),
            "entry_divergence_days": record_days,
            "blocked_delta_usd": _total(blocked),
            "missed_trim_delta_usd": _total(trims),
            "factor_days": len(factor_days),
            "shadow_days": len({str(row["trade_date"]) for row in inputs["shadows"]}),
        },
        "reason": None,
    }
