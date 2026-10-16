"""Replay frozen inputs through this project's M2, M3 and M4; compare only afterwards."""

import copy
import csv
from datetime import date, datetime, timezone
from functools import lru_cache
from io import StringIO

from inves_cog.clock import FrozenClock
from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.signals import enrich
from inves_cog.trading.execution.state import PARAMS
from inves_cog.trading.scoring import score_history
from tests.harness.tools.golden import load_golden


@lru_cache(maxsize=1)
def frozen_inputs():
    # Reuse this project's already tested M2 legacy preparation; never import or run Muse code.
    from tests.m3.replay_support import price_rows, states_for

    first, last = date(2026, 1, 2), date(2026, 10, 7)
    hashes = load_golden("v18/companyfacts_used.json")["companyfacts_sha256_uncompressed"]
    signals, prices = {}, {}
    for ticker in PARAMS["replay_tickers"]:
        bars = price_rows(ticker)
        states = states_for(ticker, last, hashes[ticker])
        snapshots = score_history(ticker, bars, state_asof=states.state_asof, extractor="legacy", start=first, end=last)
        signals[ticker] = enrich(snapshots, states.state_asof, ticker, "legacy")
        prices[ticker] = {r["trade_date"]: r for r in bars}
    prices["SPY"] = {r["trade_date"]: r for r in price_rows("SPY")}
    raw = load_golden("v18/vix_close.csv").decode()
    vix = {date.fromisoformat(row["date"]): float(row["vix"]) for row in csv.DictReader(StringIO(raw))}
    return signals, prices, vix


def compare(trades, oracle):
    actual = [(str(r["trade_date"]), r["ticker"], r["label"], r["qty"]) for r in trades]
    expected = [(r["日期"], r["代码"], r["动作"], r["股数"]) for r in oracle]
    differences = []
    for i in range(max(len(actual), len(expected))):
        left, right = actual[i] if i < len(actual) else None, expected[i] if i < len(expected) else None
        if left != right:
            differences.append({"index": i, "actual": left, "expected": right})

    def keys(rows):
        return [(r[0], r[1], r[2]) for r in rows]

    unmatched = keys(expected)
    matched = 0
    for key in keys(actual):
        if key in unmatched:
            unmatched.remove(key)
            matched += 1
    return {
        "match_rate": matched / max(len(expected), len(actual), 1),
        "differences": differences,
        "expected_count": len(expected),
        "actual_count": len(actual),
    }


def run_frozen(*, end=date(2026, 10, 7), mode="replay_v18"):
    signals, prices, vix = frozen_inputs()
    days = sorted({day for rows in signals.values() for day in rows if day <= end})
    clock = FrozenClock(datetime.combine(end, datetime.min.time(), timezone.utc))
    engine = ExecutionEngine(clock=clock, mode=mode, portfolio_id="v18-legacy")
    for day in days:
        daily = {ticker: rows[day] for ticker, rows in signals.items() if day in rows}
        opening = {ticker: rows[day]["open"] for ticker, rows in prices.items() if day in rows}
        closing = {ticker: rows[day]["close"] for ticker, rows in prices.items() if day in rows}
        engine.fill(day, opening, daily)
        spy = [r["close"] for d, r in sorted(prices["SPY"].items()) if d <= day]
        returns = (
            100 * (spy[-1] / spy[-2] - 1) if len(spy) >= 2 else None,
            100 * (spy[-1] / spy[-6] - 1) if len(spy) >= 6 else None,
        )
        history = {ticker: [r["close"] for d, r in sorted(rows.items()) if d <= day] for ticker, rows in prices.items()}
        engine.decide(
            day,
            daily,
            prices=closing,
            history=history,
            spy_returns=returns,
            vix=vix.get(day),
            vix_history=[value for d, value in sorted(vix.items()) if d <= day],
        )
    highest, drawdown = None, 0.0
    for row in engine.curve:
        highest = row["equity"] if highest is None else max(highest, row["equity"])
        drawdown = min(drawdown, 100 * (row["equity"] / highest - 1))
    # The standard answer is consumed only here, after all trade decisions and fills.
    oracle = load_golden("v18/paper_trade_v18full_trades.json")["trades"]
    oracle = [r for r in oracle if date.fromisoformat(r["日期"]) <= end]
    return {
        "mode": mode,
        "start": days[0],
        "end": end,
        "extractor": "legacy",
        "rule_set": "A",
        "equity": engine.last_equity,
        "return_pct": 100 * (engine.last_equity / engine.initial_cash - 1),
        "max_drawdown_pct": drawdown,
        "cash": engine.cash,
        "trades": copy.deepcopy(engine.trades),
        "curve": engine.curve,
        "positions": engine.positions,
        "comparison": compare(engine.trades, oracle),
        "negative_cash_days": sum(row["cash"] < 0 for row in engine.curve),
        "minimum_cash": min(row["cash"] for row in engine.curve),
    }
