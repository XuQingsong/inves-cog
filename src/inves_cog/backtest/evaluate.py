"""Evaluation methods for P2-R4: rolling-start distribution + signal-level analysis."""

import multiprocessing
import statistics
from datetime import date

from inves_cog.ingest.market import next_trading_day

from .runner import prepare_inputs, run_backtest

_G_PREPARED = None


def quarter_starts(begin=date(2018, 1, 1), end=date(2024, 12, 31)):
    out = []
    y, m = begin.year, 1
    while date(y, m, 1) <= end:
        out.append(date(y, m, 1))
        m += 3
        if m > 12:
            m, y = 1, y + 1
    return out


def _one_replay(spec):
    result = run_backtest(None, spec, write=False, prepared=_G_PREPARED)
    return {**result["metrics"], "short_hold_sales": short_hold_sales(result["trades"])}


def short_hold_sales(trades):
    """Count sells on the same or next exchange session after a buy in the same name."""
    until = {}
    count = 0
    for trade in trades:
        ticker, day = trade["ticker"], trade["trade_date"]
        if trade["side"] == "buy":
            until[ticker] = next_trading_day(day)
        elif trade["side"] == "sell" and ticker in until and day <= until[ticker]:
            count += 1
    return count


def rolling_start_eval(connection, spec, variants, *, starts=None, workers=4):
    """For each quarter start, run baseline + each variant; report the distribution.

    Scores/prices are computed once for the earliest start and inherited by fork
    (children get _G_PREPARED via copy-on-write — no pickling).
    """
    global _G_PREPARED
    starts = starts or quarter_starts()
    _G_PREPARED = prepare_inputs(
        connection,
        {**spec, "start": min(starts), "load_fear_levels": any(f.get("breakdown_confirm") for f in variants.values())},
    )
    jobs = []
    for st in starts:
        jobs.append({**spec, "start": st, "label": f"base-{st}", "flags": {}})
        jobs += [{**spec, "start": st, "label": f"{n}-{st}", "flags": f} for n, f in variants.items()]
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(max(1, min(workers, 4))) as pool:
        results = pool.map(_one_replay, jobs)
    i = 0
    rows = []
    for st in starts:
        base, i = results[i], i + 1
        for name in variants:
            m, i = results[i], i + 1
            rows.append(
                {
                    "variant": name,
                    "start": str(st),
                    "ret": m["return_pct"],
                    "dd": m["max_drawdown_pct"],
                    "rdd": m.get("return_over_maxdd"),
                    "base_ret": base["return_pct"],
                    "base_dd": base["max_drawdown_pct"],
                    "base_rdd": base.get("return_over_maxdd"),
                    "beats": m["return_pct"] > base["return_pct"],
                    "short_hold_sales": m["short_hold_sales"],
                }
            )
    return _distribution(rows)


def _distribution(rows):
    out = {}
    for name in {r["variant"] for r in rows}:
        rs = [r for r in rows if r["variant"] == name]
        ret_diffs = [r["ret"] - r["base_ret"] for r in rs]
        dd_diffs = [r["dd"] - r["base_dd"] for r in rs]
        rdd_diffs = [r["rdd"] - r["base_rdd"] for r in rs if r["rdd"] is not None and r["base_rdd"] is not None]
        out[name] = {
            "n_starts": len(rs),
            "short_hold_sales_total": sum(r["short_hold_sales"] for r in rs),
            "beats_baseline_pct": round(100 * sum(r["beats"] for r in rs) / len(rs), 1),
            **_quantiles("ret_diff", ret_diffs),
            **_quantiles("dd_diff", dd_diffs),
            **_quantiles("rdd_diff", rdd_diffs),
            "rows": rs,
        }
    return out


def _quantiles(prefix, values):
    if len(values) >= 2:
        q25, _, q75 = statistics.quantiles(values, n=4, method="inclusive")
    else:
        q25 = q75 = values[0] if values else None
    return {
        prefix + "_median": statistics.median(values) if values else None,
        prefix + "_q25": q25,
        prefix + "_q75": q75,
    }


def signal_level_eval(connection, spec, variants, *, lookahead=(20, 60), prepared=None):
    """Path-independent: per baseline buy intent, compare variant action + fwd returns."""
    prepared = prepared or prepare_inputs(connection, spec)
    base = run_backtest(None, {**spec, "flags": {}}, write=False, prepared=prepared)
    base_buys = [t for t in base["trades"] if t.get("side") == "buy"]
    out = {}
    for name, flags in variants.items():
        var = run_backtest(None, {**spec, "flags": flags}, write=False, prepared=prepared)
        var_buys = {}
        for t in var["trades"]:
            if t.get("side") == "buy":
                var_buys.setdefault((t["ticker"], t.get("signal_date")), []).append(t)
        groups = {"allowed": [], "delayed": [], "blocked": []}
        for b in base_buys:
            vb = var_buys.get((b["ticker"], b.get("signal_date")))
            fwd = {w: _fwd(prepared["prices"][b["ticker"]], b["trade_date"], w) for w in lookahead}
            if vb:
                groups["allowed" if vb[0]["trade_date"] == b["trade_date"] else "delayed"].append(
                    {"fwd": fwd, "variant_entry": vb[0].get("fill_price"), "base_entry": b.get("fill_price")}
                )
            else:
                groups["blocked"].append({"fwd": fwd})
        out[name] = {
            k: {
                "n": len(v),
                **{
                    f"ret{w}": (
                        round(statistics.median([x["fwd"][w] for x in v if x["fwd"][w] is not None]), 1)
                        if any(x["fwd"][w] is not None for x in v)
                        else None
                    )
                    for w in lookahead
                },
            }
            for k, v in groups.items()
        }
    return out


def _fwd(price_rows, day, window):
    days = sorted(d for d in price_rows if d > day)
    if len(days) < window or day not in price_rows:
        return None
    return round(100 * (price_rows[days[window - 1]]["close"] / price_rows[day]["close"] - 1), 1)
