"""P2-D2: one-off history backfill. Idempotent; prints coverage reports.
Usage: backfill_flows.py <job> [--start YYYY-MM-DD] [--end YYYY-MM-DD]
Jobs: proshares ssga cboe_pc cboe_idx occ cftc finra fred ofr all"""

import argparse
import json
from datetime import date, timedelta

from inves_cog.clock import SystemClock
from inves_cog.flows import backfill
from inves_cog.flows.store import DEFAULT_RAW, polite_http
from inves_cog.ingest.market import NY
from inves_cog.ingest.settings import read_environment


def _conn(values):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(values["Database"]["INVES_COG_DATABASE_URL"], row_factory=dict_row, autocommit=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("job")
    p.add_argument("--start", type=date.fromisoformat, default=None)
    p.add_argument("--end", type=date.fromisoformat, default=None)
    args = p.parse_args()
    clock = SystemClock()
    now = clock.now_utc().astimezone(NY)
    today = now.date()
    http = polite_http()
    values = read_environment()
    conn = _conn(values)
    start, end = args.start or date(2006, 1, 1), args.end or today
    reports = []
    if args.job in ("proshares", "all"):
        reports += backfill.backfill_proshares(http, conn, DEFAULT_RAW, today, now)
    if args.job in ("ssga", "all"):
        reports += backfill.backfill_ssga(http, conn, DEFAULT_RAW, today, now)
    if args.job in ("cboe_pc", "all"):
        reports += backfill.backfill_cboe_pc_csv(http, conn, DEFAULT_RAW, backfill.published_at, today)
        reports.append(backfill.backfill_cboe_pc(http, conn, DEFAULT_RAW, start, end, now))
    if args.job in ("cboe_idx", "all"):
        reports += backfill.backfill_cboe_idx(http, conn, DEFAULT_RAW, today, now)
    if args.job in ("occ", "all"):
        reports.append(backfill.backfill_occ(http, conn, DEFAULT_RAW, end - timedelta(days=730), end, now))
    if args.job in ("cftc", "all"):
        reports.append(backfill.backfill_cftc(http, conn, DEFAULT_RAW, start, end, now))
    if args.job in ("finra", "all"):
        reports.append(backfill.backfill_finra_margin(http, conn, DEFAULT_RAW, now))
    if args.job in ("fred", "all"):
        reports += backfill.backfill_fred(http, conn, DEFAULT_RAW, now)
    if args.job in ("ofr", "all"):
        reports.append(backfill.backfill_ofr(http, conn, DEFAULT_RAW, now))
    print(json.dumps(reports, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
