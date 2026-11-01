"""Backtest metrics from an equity curve + trades."""

import hashlib
import json
from collections import defaultdict


def equity_metrics(curve, trades, initial_cash, bench=None):
    """curve: [{date, equity, cash}] sorted; trades: [{trade_date,ticker,label,qty,price}].

    Definitions:
    - exposure_pct: share of days with invested capital (equity - cash > 0).
    - turnover_x: sum |traded notional| / starting equity (not annualized).
    - win_rate: sell trades whose fill beat the matching open buy's fill.
    - avg_holding_days: mean days between a buy and its matched sell (FIFO)."""
    if not curve:
        return {}
    first, last = curve[0]["equity"], curve[-1]["equity"]
    days = (curve[-1]["date"] - curve[0]["date"]).days or 1
    high, maxdd = None, 0.0
    for row in curve:
        high = row["equity"] if high is None else max(high, row["equity"])
        maxdd = min(maxdd, 100 * (row["equity"] / high - 1))
    total = 100 * (last / first - 1)
    ann = 100 * ((last / first) ** (365.25 / days) - 1)
    by_year = defaultdict(lambda: {"first": None, "last": None, "maxdd": 0.0, "high": None})
    for row in curve:
        y = by_year[row["date"].year]
        if y["first"] is None:
            y["first"] = row["equity"]
        y["last"] = row["equity"]
        y["high"] = row["equity"] if y["high"] is None else max(y["high"], row["equity"])
        y["maxdd"] = min(y["maxdd"], 100 * (row["equity"] / y["high"] - 1))
    yearly = {
        str(k): {"return_pct": 100 * (v["last"] / v["first"] - 1), "maxdd_pct": v["maxdd"]}
        for k, v in sorted(by_year.items())
    }
    buys = [t for t in trades if t.get("side") == "buy"]
    closed = 0
    open_pos, wins, holds = {}, 0, []
    for t in sorted(trades, key=lambda x: x["trade_date"]):
        tk = t["ticker"]
        if t.get("side") == "sell":
            closed += 1
            if open_pos.get(tk):
                o = open_pos[tk].pop(0)
                holds.append((t["trade_date"] - o["trade_date"]).days)
                if (t.get("fill_price") or 0) > (o.get("fill_price") or 0):
                    wins += 1
        else:
            open_pos.setdefault(tk, []).append(t)
    exposure = sum(1 for r in curve if r["equity"] - r["cash"] > 0) / max(len(curve), 1) * 100
    turnover = sum(abs(float(t.get("notional") or 0)) for t in trades) / max(first, 1)
    out = {
        "return_pct": total,
        "annualized_pct": ann,
        "max_drawdown_pct": maxdd,
        "return_over_maxdd": total / abs(maxdd) if maxdd else None,
        "trades": len(trades),
        "buys": len(buys),
        "sells": closed,
        "turnover_x": turnover,
        "win_rate": wins / closed if closed else None,
        "avg_holding_days": (sum(holds) / len(holds)) if holds else None,
        "exposure_pct": exposure,
        "yearly": yearly,
    }
    if bench:
        out["benchmarks"] = bench
    return out


def bench_buy_and_hold(bars, start, end, initial=1.0):
    """SPY/QQQ buy-and-hold return over the same window."""
    closes = {r["trade_date"]: r["close"] * (r.get("adj_factor") or 1.0) for r in bars}
    days = sorted(d for d in closes if start <= d <= end)
    if len(days) < 2:
        return None
    return 100 * (closes[days[-1]] / closes[days[0]] - 1)


def trade_hash(trades):
    payload = json.dumps(
        [(str(t["trade_date"]), t["ticker"], t["label"], float(t["qty"])) for t in trades],
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
