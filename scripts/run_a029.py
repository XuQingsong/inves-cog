"""Run A029 on the Mac-local read-only replay database and save JSON evidence."""

import argparse
import json
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.evaluate import rolling_start_eval, signal_level_eval
from inves_cog.backtest.loader import BacktestLoader
from inves_cog.backtest.overval import load_quintiles, quintile_at
from inves_cog.backtest.runner import prepare_inputs, run_backtest
from inves_cog.trading.execution.state import PARAMS

CASE = set("UNH KO MA V NFLX META AAPL TSM AMAT MCD AMZN LULU INTC NVDA GOOGL MU SNDK AMD TSLA MSFT".split())
FLAGS = {
    "veto": "overval_veto",
    "f1": "buy_consistency",
    "f2": "breakdown_confirm",
    "f3": "reentry_after_price_exit",
    "f4": "watch_promote",
    "f5": "ceiling_gate",
}


def save(path, result):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, default=str, indent=2))
    temp.replace(path)


def case_results(connection, spec, variants):
    prepared = prepare_inputs(connection, spec)
    panel, days = load_quintiles(spec["overval_panel"], financials=set(spec["overval_financials"]))
    fridays = [day for day in days if day.weekday() == 4]
    out = {}
    for label, flags in {"base": {}, **variants}.items():
        result = run_backtest(None, {**spec, "label": label, "flags": flags}, prepared=prepared, write=False)
        trades = []
        for trade in result["trades"]:
            ticker, signal_day = trade["ticker"], trade["signal_date"]
            if ticker not in CASE:
                continue
            visible = [day for day in fridays if day < signal_day]
            trades.append({**trade, "prior_friday_m8_quintile": quintile_at(panel, visible, ticker, signal_day)})
        out[label] = {"metrics": result["metrics"], "trades": trades}
    for ticker in sorted(CASE):
        bars = prepared["prices"].get(ticker, {})
        visible = [bars[d] for d in sorted(bars) if spec["start"] <= d <= spec["end"] and bars[d]["close"]]
        out.setdefault("buy_and_hold", {})[ticker] = (
            {
                "start": visible[0]["trade_date"],
                "end": visible[-1]["trade_date"],
                "return_pct": 100 * (visible[-1]["close"] / visible[0]["close"] - 1),
            }
            if len(visible) > 1
            else None
        )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--sectors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("rolling", "signals", "case"), required=True)
    parser.add_argument("--without-market-input", action="store_true", help="Partial evidence only. Omit F2 and combo.")
    args = parser.parse_args()
    financials = json.loads(args.sectors.read_text())["financials"]
    if not financials:
        parser.error("The financial-sector exclusion list must be populated")
    variants = {label: {flag: True} for label, flag in FLAGS.items()}
    if args.without_market_input:
        del variants["f2"]
    else:
        variants["combo"] = dict.fromkeys(FLAGS.values(), True)
    spec = {
        "start": date(2018, 1, 2),
        "end": date(2026, 10, 30),
        "universe": "config",
        "extractor": "fixed",
        "mode": "paper",
        "load_fear_levels": not args.without_market_input,
        "overval_panel": str(args.panel),
        "overval_financials": financials,
    }
    with psycopg.connect(
        host="127.0.0.1",
        dbname="inves_cog_bt",
        connect_timeout=5,
        autocommit=True,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as connection:
        if args.mode == "case":
            spec["start"] = date(2024, 1, 2)
            spec["universe"] = sorted(
                set(BacktestLoader.universe("config", PARAMS["replay_tickers"])) | {"KO", "MCD", "LULU"}
            )
            result = case_results(connection, spec, variants)
        elif args.mode == "signals":
            result = signal_level_eval(connection, spec, variants)
        else:
            result = rolling_start_eval(connection, spec, variants, workers=4)
    save(args.output, {"mode": args.mode, "partial": args.without_market_input, "result": result})


if __name__ == "__main__":
    main()
