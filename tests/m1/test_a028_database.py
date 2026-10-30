"""Disposable Postgres end-to-end for A028 grants, writes and restart deduplication."""

from datetime import date, timedelta
from unittest.mock import Mock

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.ingest.implied_moves import collect_moves
from tests.m1.test_a028 import clock, snapshots
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking


def test_a028_database_ingest_write_web_read_and_same_day_dedupe():
    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row
    ) as db:
        try:
            db.execute("SET LOCAL ROLE role_ingest")
            db.execute(
                "INSERT INTO ingest.earnings_calendar(ticker,report_date,time,source,fetched_at) "
                "VALUES ('NVDA','2026-11-17','post','Nasdaq',%s) ON CONFLICT DO NOTHING",
                (clock().now_utc(),),
            )
            at = clock().now_utc().replace(second=0) - timedelta(seconds=1)
            db.execute(
                "INSERT INTO ingest.intraday_snapshots(ticker,as_of,session,last,delay_minutes,source,fetched_at) "
                "VALUES ('NVDA',%s,'regular',213.7,0,'AlpacaIEX',%s) ON CONFLICT DO NOTHING",
                (at, clock().now_utc()),
            )
            http = Mock()
            http.get.return_value = snapshots()
            values = {"APCA_API_KEY_ID": "offline", "APCA_API_SECRET_KEY": "offline"}
            assert collect_moves(clock=clock(), db=db, values=values, http=http)["processed_count"] == 1
            assert collect_moves(clock=clock(), db=db, values=values, http=http)["processed_count"] == 0
            assert http.get.call_count == 1
            db.execute("RESET ROLE")
            db.execute("SET LOCAL ROLE role_web")
            row = db.execute(
                "SELECT * FROM ingest.earnings_implied_moves WHERE ticker='NVDA' AND report_date=%s",
                (date(2026, 11, 17),),
            ).fetchone()
            assert row["feed"] == "indicative" and row["iv_call"] is None and row["iv_put"] is None
            assert row["spot_source"] == "IEX"
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute("DELETE FROM ingest.earnings_implied_moves")
        finally:
            db.rollback()
