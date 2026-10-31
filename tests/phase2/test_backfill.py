from datetime import date, datetime
from unittest.mock import MagicMock

from inves_cog.flows.backfill import _report, backfill_cboe_index, backfill_fred, backfill_occ, backfill_ofr


def test_report_gaps():
    r = _report("X", {date(2026, 10, 26): 5, date(2026, 10, 30): 3})
    assert r["first"] == "2026-10-26" and r["last"] == "2026-10-30"
    assert r["gap_count"] >= 2  # 27,28,29 trading days missing


def test_backfill_occ_upserts():
    csv = "quantity,underlying,symbol,actype,porc,exchange,actdate\n100,SPY,x,C,C,1,10/30/2026\n"
    http = MagicMock()
    http.request.return_value = csv
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    import inves_cog.ingest.market as M

    orig = M.trading_day
    M.trading_day = lambda d: True
    r = backfill_occ(http, conn, "/tmp/x", date(2026, 10, 30), date(2026, 10, 30), datetime(2026, 10, 31), pace=0)
    M.trading_day = orig
    assert r["rows"] == 1


def test_backfill_fred_parse():
    text = "observation_date,WALCL\n2026-10-30,8000000\n2026-10-29,7990000\n"
    http = MagicMock()
    http.request.return_value = text
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    reports = backfill_fred(http, conn, "/tmp/x", datetime(2026, 10, 31))
    walcl = next(r for r in reports if r["source"] == "FRED:WALCL")
    assert walcl["rows"] == 2 and walcl["first"] == "2026-10-29"


def test_backfill_cboe_index_parse():
    text = "DATE,VIX9D\n2026-10-30,15.5\n"
    http = MagicMock()
    http.request.return_value = text
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    reports = backfill_cboe_index(http, conn, "/tmp/x", date(2026, 10, 30), datetime(2026, 10, 31))
    assert any(r["source"] == "CboeIdx:VIX9D" and r["rows"] == 1 for r in reports)


def test_backfill_ofr_parse():
    text = "date,OFR FSI\n2026-10-30,0.5\n2026-10-29,0.6\n"
    http = MagicMock()
    http.request.return_value = text
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    conn.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    r = backfill_ofr(http, conn, "/tmp/x", datetime(2026, 10, 31))
    assert r["rows"] == 2
