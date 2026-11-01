"""P2-R1: run a backtest against the DB loader. Writes only to the backtest schema.

Usage: run_backtest.py --label x --universe config|v18|NVDA,AMD --start YYYY-MM-DD
        --end YYYY-MM-DD --mode paper|replay_v18 --extractor fixed|legacy [--no-write]
"""

import argparse
import json
from datetime import date

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.runner import run_backtest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--universe", default="config")
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--mode", default="paper")
    p.add_argument("--extractor", default="fixed")
    p.add_argument("--initial-cash", type=float, default=None)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()

    import os

    dsn = os.environ["INVES_COG_DATABASE_URL"]
    conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    universe = args.universe.split(",") if "," in args.universe else args.universe
    spec = {
        "label": args.label,
        "universe": universe,
        "start": args.start,
        "end": args.end,
        "mode": args.mode,
        "extractor": args.extractor,
        "initial_cash": args.initial_cash,
    }
    result = run_backtest(conn, spec, write=not args.no_write)
    m = result["metrics"]
    print(json.dumps({"run_id": result.get("run_id"), **m}, default=str))


if __name__ == "__main__":
    main()
