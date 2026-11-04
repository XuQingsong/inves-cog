"""run_backtest — generalizes execution/replay.run_frozen onto the prod DB loader."""

import bisect
import copy
import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def prepare_inputs(connection, spec):
    """Load prices/signals/vix once — reused across replays and rolling starts."""
    loader = BacktestLoader(connection)
    tickers = (
        spec["universe"]
        if isinstance(spec["universe"], list)
        else BacktestLoader.universe(spec["universe"], PARAMS["replay_tickers"])
    )
    start, end = spec["start"], spec["end"]
    extractor = spec.get("extractor", "fixed")
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
    return {"loader": loader, "tickers": tickers, "prices": prices, "signals": signals, "vix": vix}


def run_backtest(connection, spec, *, write=True, prepared=None):  # noqa: C901
    """spec: {universe, start, end, initial_cash, mode, extractor, params_path, label}.

    Engine stays in memory — persist_orders is never called; writes go only to
    the backtest schema (when write=True). `prepared` reuses prepare_inputs() output.
    """
    pre = prepared or prepare_inputs(connection, spec)
    loader, tickers = pre["loader"], pre["tickers"]
    prices, signals, vix = pre["prices"], pre["signals"], pre["vix"]
    start, end = spec["start"], spec["end"]
    initial = spec.get("initial_cash") or PARAMS["initial_cash"]
    mode = spec.get("mode", "paper")
    days = sorted({d for rows in prices.values() for d in rows if start <= d <= end})
    clock = FrozenClock(datetime.combine(end, datetime.min.time(), timezone.utc))
    engine = ExecutionEngine(
        clock=clock,
        initial_cash=initial,
        mode=mode,
        portfolio_id=f"bt-{spec.get('label', 'run')}",
        flags=spec.get("flags") or {},
    )
    flags = spec.get("flags") or {}
    flag_counts = {}
    veto_events = []
    overval = None
    if flags.get("overval_veto"):
        from .overval import load_quintiles
        from .overval import quintile_at as overval_quintile
        from .overval import vetoed as overval_vetoed

        panel_path = spec.get("overval_panel") or str(Path.home() / "inves-cog-bt" / "valuation" / "panel_sp500.csv")
        financials = set(spec.get("overval_financials") or ())
        overval = load_quintiles(panel_path, financials=financials)
    locked = {}
    if flags.get("tier_lock"):
        import yaml

        cfg = Path(__file__).resolve().parents[3] / "config" / "v19_tiers.yaml"
        locked = yaml.safe_load(open(cfg))["tiers"]
    rule_tier_map, gap_map, valuation_rows = {}, {}, []
    states_map = {}
    if flags.get("rule_tiers") or flags.get("gap_judgment") or flags.get("chase_v2") or spec.get("valuation_output"):
        from .gap_judgment import gap_events
        from .rule_tiers import tier_history
        from .valuation import valuation_inputs

        spy = prices.get("SPY", {})
        for t in tickers:
            states = states_map[t] = loader.states_for(t, end=end)
            if flags.get("rule_tiers"):
                rule_tier_map[t] = {h["date"]: h["tier"] for h in tier_history(t, prices.get(t, {}), spy, states)}
            if flags.get("gap_judgment") or flags.get("chase_v2"):
                filings = [
                    {
                        "filed": f["filed"] if isinstance(f, dict) else getattr(f, "filed", None),
                        "form": f["form"] if isinstance(f, dict) else getattr(f, "form", None),
                    }
                    for f in loader.filings(t)
                ]
                gap_map[t] = gap_events(
                    t,
                    prices.get(t, {}),
                    filings,
                    states,
                    lambda tt, dd, states=states: valuation_inputs(tt, dd, prices.get(tt, {}), states),
                    start,
                    end,
                )
            if spec.get("valuation_output"):
                for d in sorted({d for rows in signals.get(t, {}).items() for d in [rows[0]]}):
                    valuation_rows.append(valuation_inputs(t, d, prices.get(t, {}), states))
    chase_upgrades = {}
    if flags.get("chase_v2"):
        from .chase_v2 import chase_trigger
        from .gap_judgment import _st

        for t in tickers:
            bars = prices.get(t, {})
            fil_rows = loader.filings(t)
            for day in sorted(signals.get(t, {})):
                if not chase_trigger(bars, day):
                    continue
                for f in fil_rows:
                    fd = f["filed"] if isinstance(f, dict) else getattr(f, "filed", None)
                    fo = f["form"] if isinstance(f, dict) else getattr(f, "form", None)
                    if fd and day < fd <= day + timedelta(days=45) and fo in ("10-Q", "10-K"):
                        st_f = _st(states_map.get(t, []), fd)
                        confirmed = bool(
                            st_f
                            and (st_f.values.get("rev_accel_pp") or 0) > 0
                            and (
                                (st_f.values.get("gross_margin_change_pp") or 0) > 0
                                or (st_f.values.get("fcf_margin") or 0) > 0
                            )
                        )
                        val = valuation_inputs(t, fd, bars, states_map.get(t, []))
                        chase_upgrades.setdefault(t, {})[fd] = {
                            "confirmed": confirmed,
                            "pe_pct": val.get("pe_pctile_3y"),
                        }
                        break
    engine.chase_upgrades = chase_upgrades
    prev_blocked = set()
    for day in days:
        daily = {t: dict(signals[t][day]) for t in tickers if day in signals[t]}
        if flags.get("tier_lock"):
            for t, sc in daily.items():
                if t in locked:
                    sc["tier"] = locked[t]
        if rule_tier_map:
            for t, sc in daily.items():
                past = [d for d in rule_tier_map.get(t, {}) if d <= day]
                if past:
                    sc["tier"] = rule_tier_map[t][max(past)]
        if flags.get("chase_v2"):
            from .chase_v2 import category, chase_trigger, tranche
            from .valuation import valuation_inputs

            for t, sc in daily.items():
                tr = chase_trigger(prices.get(t, {}), day)
                if tr and sc.get("entry_pass"):
                    st = states_map.get(t, [])
                    val = valuation_inputs(t, day, prices.get(t, {}), st) if st else {}
                    cat = category(gap_map.get(t, {}).get(day) if gap_map else None, val)
                    sc["chase_v2"] = {
                        "category": cat,
                        "frac": tranche(cat),
                        "stop": tr[1],
                        "anchor": prices.get(t, {}).get(day, {}).get("close"),
                        "gap_mid": (tr[1] + prices.get(t, {}).get(day, {}).get("open", tr[1])) / 2,
                    }
                    flag_counts["chase_v2_" + cat] = flag_counts.get("chase_v2_" + cat, 0) + 1
        if gap_map and flags.get("gap_judgment"):
            for t, sc in daily.items():
                ev = gap_map.get(t, {}).get(day)
                if ev and sc.get("entry_pass"):
                    d = ev["decision"]
                    if d == "block":
                        sc["entry_pass"] = False
                        flag_counts["gap_block_" + ev["cause"]] = flag_counts.get("gap_block_" + ev["cause"], 0) + 1
                    elif d == "pullback":
                        flag_counts["gap_pullback"] = flag_counts.get("gap_pullback", 0) + 1
                    else:
                        flag_counts["gap_allow"] = flag_counts.get("gap_allow", 0) + 1
        if flags.get("chase_block"):
            now_blocked = set()
            for t, sc in daily.items():
                hist = [r["close"] for d, r in sorted(prices[t].items()) if d <= day]
                if (
                    len(hist) >= 6
                    and sc.get("entry_pass")
                    and (hist[-1] / hist[-6] - 1) > flags.get("chase_threshold", 0.08)
                ):
                    sc["entry_pass"] = False
                    now_blocked.add(t)
                    flag_counts["chase_block"] = flag_counts.get("chase_block", 0) + 1
                    if t not in prev_blocked:  # distinct would-be order = start of a blocked streak
                        flag_counts["chase_orders"] = flag_counts.get("chase_orders", 0) + 1
            prev_blocked = now_blocked
        if overval is not None:
            qmap, qdays = overval
            for t, sc in daily.items():
                if sc.get("entry_pass") and overval_vetoed(qmap, qdays, t, day):
                    sc["entry_pass"] = False
                    flag_counts["overval_veto"] = flag_counts.get("overval_veto", 0) + 1
                    fidx = bisect.bisect_right(qdays, day) - 1
                    veto_events.append(
                        {
                            "ticker": t,
                            "date": day,
                            "price": prices.get(t, {}).get(day, {}).get("close"),
                            "quintile": overval_quintile(qmap, qdays, t, day),
                            "m8": qmap[qdays[fidx]]["m8"].get(t) if fidx >= 0 else None,
                        }
                    )
        # PIT audit: a signal dated after the decision day must never appear
        for t, s in daily.items():
            if s["signal_date"] > day:
                raise ValueError(f"PIT violation: signal {t} {s['signal_date']} > {day}")
        opening = {t: prices[t][day]["open"] for t in prices if day in prices[t]}
        closing = {
            t: prices[t][day]["close"] * (prices[t][day].get("adj_factor") or 1.0) for t in prices if day in prices[t]
        }
        engine.fill(
            day,
            opening,
            daily,
            day_bars={
                t: {"open": r[day]["open"], "low": r[day]["low"], "close": r[day]["close"]}
                for t, r in prices.items()
                if day in r
            },
        )
        spy = [prices["SPY"][d]["close"] for d in sorted(prices["SPY"]) if d <= day]
        returns = (
            100 * (spy[-1] / spy[-2] - 1) if len(spy) >= 2 else None,
            100 * (spy[-1] / spy[-6] - 1) if len(spy) >= 6 else None,
        )
        history = {t: [r["close"] for d, r in sorted(rows.items()) if d <= day] for t, rows in prices.items()}
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
    flag_counts.update(getattr(engine, "flags_counts", {}))
    metrics["flags_counts"] = flag_counts
    result = {
        "flag_diag": getattr(engine, "flag_diag", {}),
        "spec": spec,
        "metrics": metrics,
        "trades": copy.deepcopy(engine.trades),
        "veto_events": veto_events,
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
        run_id = _persist(connection, spec, result, clock)
        result["run_id"] = run_id
    return result


def _persist(connection, spec, result, clock):
    now = clock.now_utc()
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
        high, dd_rows = None, []
        for r in result["curve"]:
            high = r["equity"] if high is None else max(high, r["equity"])
            dd_rows.append((run_id, r["day"], r["equity"], r["cash"], 100 * (r["equity"] / high - 1)))
        c.executemany(
            "INSERT INTO backtest.equity_curve (run_id,date,equity,cash,drawdown) VALUES (%s,%s,%s,%s,%s)",
            dd_rows,
        )
        c.executemany(
            "INSERT INTO backtest.skips (run_id,date,ticker,reason) VALUES (%s,%s,%s,%s)",
            [
                (
                    run_id,
                    sk.get("trade_date") or sk.get("signal_date"),
                    sk["ticker"],
                    str(sk.get("reason_zh") or sk.get("reason") or ""),
                )
                for sk in result.get("skips", [])
            ],
        )
        for day, marks in (result.get("positions_eod") or {}).items():
            c.executemany(
                "INSERT INTO backtest.positions_eod (run_id,date,ticker,qty,price) VALUES (%s,%s,%s,%s,%s)",
                [(run_id, day, t, m["qty"], m.get("price")) for t, m in marks.items()],
            )
    return run_id
