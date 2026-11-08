"""Recompute ingest.bars_daily adj_factor from Alpaca corporate actions (dry-run by default).

Uses the same mechanism as the ingest pipeline: alpaca_splits() fetches forward/reverse
splits, split_factors() assigns rows dated before each ex_date the cumulative 1/ratio.
--dry-run (default) prints every row whose stored factor differs plus the before/after
day-on-day adjusted return at each ex_date. --apply writes the corrections in one transaction.
"""

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg
from psycopg.rows import dict_row

from inves_cog.clock import SystemClock
from inves_cog.ingest.adapters import alpaca_splits
from inves_cog.ingest.market import split_factors
from inves_cog.ingest.providers import Alpaca


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--first", type=date.fromisoformat, default=None, help="default: earliest stored row")
    parser.add_argument("--last", type=date.fromisoformat, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = psycopg.connect(os.environ["INVES_COG_DATABASE_URL"], row_factory=dict_row)
    alpaca = Alpaca(
        clock=SystemClock(),
        key=os.environ["APCA_API_KEY_ID"],
        secret=os.environ["APCA_API_SECRET_KEY"],
    )
    diffs = []
    for ticker in args.tickers:
        first = (
            args.first
            or conn.execute("SELECT min(trade_date) d FROM ingest.bars_daily WHERE ticker=%s", (ticker,)).fetchone()[
                "d"
            ]
        )
        rows = conn.execute(
            "SELECT trade_date, close, adj_factor FROM ingest.bars_daily"
            " WHERE ticker=%s AND trade_date>=%s AND trade_date<=%s ORDER BY trade_date",
            (ticker, first, args.last + timedelta(days=1)),
        ).fetchall()
        splits = alpaca_splits(alpaca, [ticker], first, args.last + timedelta(days=1))
        found = splits.get(ticker, [])
        for s in found:
            print(f"{ticker}: Alpaca {s['raw'].get('type', 'split')} ratio x{s['ratio']:.6g} ex_date {s['date']}")
        expected = split_factors([r["trade_date"] for r in rows], found)
        changed = [i for i, (r, f) in enumerate(zip(rows, expected)) if abs((r["adj_factor"] or 1) - f) > 1e-9]
        for i in changed:
            r = rows[i]
            print(
                f"  {ticker} {r['trade_date']} adj_factor {r['adj_factor']} -> {expected[i]:.9f} (close {r['close']})"
            )
        for s in found:
            pre = next((i for i, r in enumerate(rows) if r["trade_date"] >= s["date"]), None)
            if pre:
                cur, prev = rows[pre], rows[pre - 1]
                raw_ret = cur["close"] / prev["close"] - 1
                adj_ret = cur["close"] * expected[pre] / (prev["close"] * expected[pre - 1]) - 1
                print(f"  {ticker} ex {s['date']}: raw {raw_ret:+.2%} -> adjusted {adj_ret:+.2%}")
        diffs += [(ticker, rows[i]["trade_date"], expected[i]) for i in changed]
    print(f"total rows to update: {len(diffs)}")
    if not args.apply or not diffs:
        return
    with conn.transaction():
        for ticker, day, factor in diffs:
            conn.execute(
                "UPDATE ingest.bars_daily SET adj_factor=%s WHERE ticker=%s AND trade_date=%s",
                (factor, ticker, day),
            )
    print(f"applied {len(diffs)} updates")


if __name__ == "__main__":
    main()
