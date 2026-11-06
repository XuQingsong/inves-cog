"""Bounded A031 R2 research, only the Mac-local read-only replay database."""

import argparse
import bisect
import json
import multiprocessing
import signal
import time
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.evaluate import rolling_start_eval, signal_level_eval
from inves_cog.backtest.runner import prepare_inputs, run_backtest

VARIANTS = {"F2": {"breakdown_confirm": True}, "v2": {"breakdown_v2": True}, "v2b": {"breakdown_v2b": True}}


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def sale_audit(trades, prices):
    result = []
    for trade in trades:
        if trade["side"] != "sell":
            continue
        ticker, day = trade["ticker"], trade["trade_date"]
        bars = prices[ticker]
        days = sorted(bars)
        index = bisect.bisect_left(days, day)
        fwd = {}
        for n in (20, 60):
            future = index + n
            fwd[str(n)] = (
                100 * (bars[days[future]]["close"] / bars[day]["close"] - 1)
                if future < len(days) and bars[day]["close"]
                else None
            )
        special = ticker in {"NVDA", "GOOGL", "META"} and (
            date(2025, 2, 1) <= day <= date(2025, 5, 31) or day.year == 2026
        )
        if special or "M-55" in trade["rule_ids"]:
            result.append({**trade, "requested_case": special, "forward_pct": fwd})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seconds", type=int, default=1800)
    args = p.parse_args()

    def deadline(signum, frame):
        for child in multiprocessing.active_children():
            child.terminate()
        for child in multiprocessing.active_children():
            child.join(timeout=2)
        raise TimeoutError("A031 evaluation deadline reached; preserve completed checkpoints")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(args.seconds)
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    spec = dict(
        start=date(2018, 1, 2),
        end=date(2026, 10, 30),
        universe="config",
        extractor="fixed",
        mode="paper",
        load_fear_levels=True,
    )
    with psycopg.connect(
        host="127.0.0.1",
        dbname="inves_cog_bt",
        connect_timeout=5,
        autocommit=True,
        row_factory=dict_row,
        options="-c default_transaction_read_only=on -c statement_timeout=30000",
    ) as db:
        pre = prepare_inputs(db, spec)
        save(args.output / "progress.json", {"phase": "prepared", "elapsed": time.monotonic() - started})
        for name, flags in {"base": {}, **VARIANTS}.items():
            checkpoint = args.output / (name + ".json")
            if checkpoint.exists() and "metrics" in json.loads(checkpoint.read_text()):
                continue
            result = run_backtest(None, {**spec, "flags": flags, "label": name}, prepared=pre, write=False)
            save(
                args.output / (name + ".json"),
                dict(metrics=result["metrics"], sales=sale_audit(result["trades"], pre["prices"])),
            )
            save(args.output / "progress.json", {"phase": name, "elapsed": time.monotonic() - started})
        save(args.output / "signals.json", signal_level_eval(db, spec, VARIANTS, prepared=pre))
        save(args.output / "rolling.json", rolling_start_eval(db, spec, VARIANTS, prepared=pre, workers=4))
    save(
        args.output / "progress.json",
        {"phase": "complete", "elapsed": time.monotonic() - started, "database": "inves_cog_bt", "workers": 4},
    )


if __name__ == "__main__":
    main()
