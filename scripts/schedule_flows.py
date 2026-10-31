"""Phase-2 flows collectors — separate process, holiday-aware. Failures isolated from phase-1."""

import json
import time
from datetime import date, datetime, timedelta

from inves_cog.clock import SystemClock
from inves_cog.flows.collectors import (
    CBOE_URL,
    DIREXION_TICKERS,
    PROSHARES_TICKERS,
    collect_cboe_chain,
    collect_occ_oi,
    collect_occ_volume,
    collect_etf_shares,
)
from inves_cog.flows.store import DEFAULT_RAW, polite_http
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.settings import read_environment

INDEX_SYMS = ["_SPX", "SPY", "QQQ", "IWM", "SMH"]
INTRA_TIMES = [(h, m) for h in range(9, 16) for m in (45, 15, 30)]  # 09:45..16:00 grid


def _connection(values):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(values.ingest_dsn, row_factory=dict_row, autocommit=True)


def _universe(connection):
    return [
        r["ticker"] for r in connection.execute("SELECT DISTINCT ticker FROM marketstate.daily").fetchall()
    ] or INDEX_SYMS


def _intra_slot(now):
    h, m = now.hour, now.minute
    return (9, 45) <= (h, m) < (16, 0) and m in (0, 15, 30, 45)


def run_once(clock, values):
    local = clock.now_utc().astimezone(NY)
    if not trading_day(local.date()):
        return {"status": "skipped", "reason": "non-trading day"}
    http = polite_http()
    conn = _connection(values)
    h, m = local.hour, local.minute
    result = {}
    try:
        if _intra_slot(local):
            result["cboe"] = [collect_cboe_chain(http, conn, s, DEFAULT_RAW, 60, local.date()) for s in INDEX_SYMS]
        if (h, m) == (16, 30):
            result["cboe_eod"] = [
                collect_cboe_chain(http, conn, s, DEFAULT_RAW, 0, local.date()) for s in _universe(conn)
            ]
        if (h, m) == (17, 30):
            result["etf"] = collect_etf_shares(http, conn, DEFAULT_RAW, datetime.now())
        if (h, m) == (7, 0):
            prev = local.date() - timedelta(days=1)
            result["occ_vol"] = collect_occ_volume(http, conn, prev, DEFAULT_RAW)
            result["occ_oi"] = collect_occ_oi(http, conn, prev, DEFAULT_RAW)
        return {"status": "ok", "at": str(local), **result}
    finally:
        conn.close()


def main():
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock, read_environment())
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
