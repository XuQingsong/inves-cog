"""A031 whole-pool gate diagnosis; local DB read-only, no production rule edits."""

import argparse
import json
import signal
import time
from collections import Counter
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.evaluate import _fwd
from inves_cog.backtest.runner import prepare_inputs, run_backtest
from inves_cog.backtest.selection_gap import quantile
from inves_cog.trading.execution.state import PARAMS


def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def outcomes(trades, prices):
    result = []
    for trade in trades:
        if trade["side"] == "buy" and trade["trade_date"] >= date(2024, 1, 1):
            result.append(
                {
                    **trade,
                    "forward_pct": {
                        str(n): _fwd(prices[trade["ticker"]], trade["trade_date"], n) for n in (20, 60, 120)
                    },
                }
            )
    return result


def summary(rows):
    out = dict(buys=len(rows), tickers=sorted({r["ticker"] for r in rows}))
    for n in (20, 60, 120):
        vals = [r["forward_pct"][str(n)] for r in rows if r["forward_pct"][str(n)] is not None]
        out[str(n)] = dict(
            n=len(vals),
            median_pct=quantile(vals, 0.5),
            win_pct=100 * sum(v > 0 for v in vals) / len(vals) if vals else None,
        )
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    signal.alarm(1200)
    started = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    spec = dict(start=date(2018, 1, 2), end=date(2026, 10, 30), universe="config", extractor="fixed", mode="paper")
    with psycopg.connect(
        host="127.0.0.1",
        dbname="inves_cog_bt",
        row_factory=dict_row,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=30000",
    ) as db:
        pre = prepare_inputs(db, spec)
        base = run_backtest(
            None,
            {**spec, "audit_selection": pre["tickers"], "audit_selection_start": date(2024, 1, 1)},
            prepared=pre,
            write=False,
        )
        audit = base["selection_audit"]
        held = {r["ticker"] for r in audit if r.get("held") or r.get("buy_intents")}
        gainers = []
        for ticker in pre["tickers"]:
            ds = sorted(d for d in pre["prices"][ticker] if date(2024, 1, 1) <= d <= spec["end"])
            if len(ds) > 1:
                gainers.append(
                    dict(
                        ticker=ticker,
                        return_pct=100
                        * (pre["prices"][ticker][ds[-1]]["close"] / pre["prices"][ticker][ds[0]]["close"] - 1),
                        start=ds[0],
                        end=ds[-1],
                        held_during_window=ticker in held,
                    )
                )
        missed = sorted(
            [r for r in gainers if not r["held_during_window"]], key=lambda r: r["return_pct"], reverse=True
        )[:10]
        selected = {"AMD", "SNDK", "MU", "AMAT", "TSM"} | {r["ticker"] for r in missed}
        detail = [r for r in audit if r["ticker"] in selected]
        table = {}
        for ticker in sorted(selected):
            rows = [r for r in detail if r["ticker"] == ticker]
            gates = Counter(k for r in rows for k in r["blockers"])
            dynamic = Counter()
            for row in rows:
                for text in row.get("skip_reasons", []):
                    for key, part in [
                        ("capacity", "名额"),
                        ("tier_capacity", "持仓已达"),
                        ("budget", "额度"),
                        ("cooldown", "冷却"),
                        ("drawdown", "回撤"),
                    ]:
                        if part in text:
                            dynamic[key] += 1
                if row.get("watch_waiting"):
                    dynamic["watch_confirmation"] += 1
                if row.get("hold_score") is not None and row["hold_score"] < PARAMS["entry_hold_min"]:
                    dynamic["entry_hold_score"] += 1
            passed = next((r for r in rows if r.get("entry_pass") and not r["blockers"]), None)
            intended = next((r for r in rows if r.get("buy_intents")), None)
            table[ticker] = dict(
                days=len(rows),
                gate_days=gates,
                dynamic_gate_days=dynamic,
                first_score_pass={k: passed[k] for k in ("date", "price")} if passed else None,
                first_buy_intent={k: intended[k] for k in ("date", "price", "buy_intents")} if intended else None,
            )
        base_buys = outcomes(base["trades"], pre["prices"])
        save(
            args.output / "baseline.json",
            dict(
                metrics=base["metrics"],
                selected=sorted(selected),
                missed_top10=missed,
                gainers=gainers,
                gate_summary=table,
                daily=detail,
                buys=base_buys,
                buy_summary=summary(base_buys),
            ),
        )
        keys = Counter((r["ticker"], r["signal_date"], r["action"]) for r in base_buys)
        for book in ("quality", "growth", "valuation", "timing"):
            variant = run_backtest(None, {**spec, "relax_book": book}, prepared=pre, write=False)
            buys = outcomes(variant["trades"], pre["prices"])
            seen = Counter()
            extra = []
            for row in buys:
                key = row["ticker"], row["signal_date"], row["action"]
                seen[key] += 1
                if seen[key] > keys[key]:
                    extra.append(row)
            save(
                args.output / (book + ".json"),
                dict(
                    method="same-day whole-pool p60, min(original threshold, p60), missing never imputed",
                    metrics=variant["metrics"],
                    extra=extra,
                    extra_summary=summary(extra),
                    baseline_summary=summary(base_buys),
                ),
            )
            save(args.output / "progress.json", dict(phase=book, elapsed=time.monotonic() - started))
    save(args.output / "progress.json", dict(phase="complete", elapsed=time.monotonic() - started))


if __name__ == "__main__":
    main()
