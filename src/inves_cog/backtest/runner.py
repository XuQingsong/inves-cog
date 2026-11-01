"""run_backtest — generalizes execution/replay.run_frozen onto the prod DB loader."""

import copy
import json
import logging
import subprocess
from datetime import datetime, timezone

from inves_cog.backtest.loader import BacktestLoader
from inves_cog.backtest.metrics import bench_buy_and_hold, equity_metrics, trade_hash
from inves_cog.clock import FrozenClock
from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.signals import enrich
from inves_cog.trading.execution.state import PARAMS
from inves_cog.trading.scoring import score_history

log = logging.getLogger(__name__)


def _code_rev():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return "unknown"


def run_backtest(connection, spec, *, write=True):
    """spec: {universe, start, end, initial_cash, mode, extractor, params_path, label}.

    Engine stays in memory — persist_orders is never called; writes go only to
    the backtest schema (when write=True).
    """
    loader = BacktestLoader(connection)
    tickers = (
        spec["universe"]
        if isinstance(spec["universe"], list)
        else BacktestLoader.universe(spec["universe"], PARAMS["replay_tickers"])
    )
    start, end = spec["start"], spec["end"]
    initial = spec.get("initial_cash") or PARAMS["initial_cash"]
    mode, extractor = spec.get("mode", "paper"), spec.get("extractor", "fixed")
    # tickers enter on their first bar date (IPO); bars loader already covers it
    prices, signals = {}, {}
    for t in tickers + ["SPY", "QQQ"]:
        prices[t] = {r["trade_date"]: r for r in loader.bars(t, end=end)}
    for t in tickers:
        snaps = score_history(
            t,
            loader.bars(t, end=end),
            state_asof=loader.state_asof,
            extractor=extractor,
            start=start,
            end=end,
        )
        signals[t] = enrich(snaps, loader.state_asof, t, extractor)
    vix = loader.vix(end)
    days = sorted({d for rows in prices.values() for d in rows if start <= d <= end})
    clock = FrozenClock(datetime.combine(end, datetime.min.time(), timezone.utc))
    engine = ExecutionEngine(
        clock=clock, initial_cash=initial, mode=mode, portfolio_id=f"bt-{spec.get('label', 'run')}"
    )
    for day in days:
        daily = {t: signals[t][day] for t in tickers if day in signals[t]}
        # PIT audit: a signal dated after the decision day must never appear
        for t, s in daily.items():
            if s["signal_date"] > day:
                raise ValueError(f"PIT violation: signal {t} {s['signal_date']} > {day}")
        opening = {t: prices[t][day]["open"] for t in prices if day in prices[t]}
        closing = {
            t: prices[t][day]["close"] * (prices[t][day].get("adj_factor") or 1.0) for t in prices if day in prices[t]
        }
        engine.fill(day, opening, daily)
        spy = [prices["SPY"][d]["close"] for d in sorted(prices["SPY"]) if d <= day]
        returns = (
            100 * (spy[-1] / spy[-2] - 1) if len(spy) >= 2 else None,
            100 * (spy[-1] / spy[-6] - 1) if len(spy) >= 6 else None,
        )
        history = {
            t: [r["close"] * (r.get("adj_factor") or 1.0) for d, r in sorted(rows.items()) if d <= day]
            for t, rows in prices.items()
        }
        engine.decide(
            day,
            daily,
            prices=closing,
            history=history,
            spy_returns=returns,
            vix=vix.get(day),
            vix_history=[v for d, v in sorted(vix.items()) if d <= day],
        )
    metrics = equity_metrics(
        [{"date": r["day"], "equity": r["equity"], "cash": r["cash"]} for r in engine.curve],
        engine.trades,
        initial,
        bench={
            "SPY": bench_buy_and_hold(sorted(prices["SPY"].values(), key=lambda r: r["trade_date"]), start, end),
            "QQQ": bench_buy_and_hold(
                sorted(prices.get("QQQ", {}).values(), key=lambda r: r["trade_date"]), start, end
            ),
        },
    )
    metrics["trade_hash"] = trade_hash(engine.trades)
    metrics["survivorship_bias"] = spec.get("universe") == "config"
    result = {
        "spec": spec,
        "metrics": metrics,
        "trades": copy.deepcopy(engine.trades),
        "curve": engine.curve,
        "positions": engine.positions,
        "audit": {
            "state_lookups": len(loader.audit["state_lookups"]),
            "late_filings": sum(
                1 for x in loader.audit["state_lookups"] if x["filed"] is not None and x["filed"] > x["as_of"]
            ),
        },
    }
    if write:
        run_id = _persist(connection, spec, result)
        result["run_id"] = run_id
    return result


def _persist(connection, spec, result):
    now = datetime.now(timezone.utc)
    cur = connection.execute(
        "INSERT INTO backtest.runs (label, spec, code_rev, started_at, finished_at, status, metrics) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING run_id",
        (
            spec.get("label", "run"),
            json.dumps(spec, default=str),
            _code_rev(),
            now,
            now,
            "done",
            json.dumps(result["metrics"], default=str),
        ),
    )
    run_id = cur.fetchone()["run_id"]
    with connection.cursor() as c:
        c.executemany(
            "INSERT INTO backtest.trades (run_id,trade_date,ticker,label,qty,price,amount) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [
                (run_id, t["trade_date"], t["ticker"], t["label"], t["qty"], t.get("fill_price"), t.get("notional"))
                for t in result["trades"]
            ],
        )
        c.executemany(
            "INSERT INTO backtest.equity_curve (run_id,date,equity,cash,drawdown) VALUES (%s,%s,%s,%s,%s)",
            [(run_id, r["day"], r["equity"], r["cash"], 0) for r in result["curve"]],
        )
    return run_id
