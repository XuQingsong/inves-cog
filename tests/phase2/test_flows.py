from datetime import date, datetime
from unittest.mock import MagicMock

from inves_cog.flows.collectors import (
    collect_cboe_chain,
    parse_cboe_chain,
    parse_direxion,
    parse_occ_oi_summary,
    parse_occ_volume,
    parse_proshares,
)
from inves_cog.flows.store import save_raw

CBOE = {
    "data": {
        "timestamp": "2026-10-30T15:45:00-04:00",
        "options": [
            {
                "option": "QQQ  260320C00500000",
                "bid": 1.5,
                "ask": 1.7,
                "iv": 0.28,
                "open_interest": 12345,
                "volume": 999,
                "delta": 0.52,
                "gamma": 0.01,
            },
            {
                "option": "QQQ  261220P00450000",
                "bid": 0.8,
                "ask": 0.9,
                "iv": 0.31,
                "open_interest": 5555,
                "volume": 100,
            },
        ],
    }
}


def test_parse_cboe_chain():
    rows = parse_cboe_chain(CBOE, "QQQ", 60, date(2026, 10, 30))
    assert len(rows) == 2
    q = rows[0]
    assert q["underlying"] == "QQQ" and q["cp"] == "C" and q["expiry"] == date(2026, 3, 20)
    assert q["oi"] == 12345 and q["source"] == "CBOE" and q["strike"] == 500.0


def test_parse_occ_volume():
    csv = (
        "quantity,underlying,symbol,actype,porc,exchange,actdate\n"
        "100,SPY,SPY  251031C500,C,C,1,10/30/2026\n"
        "200,SPY,SPY  251031C500,C,C,1,10/30/2026\n"
        "50,QQQ,QQQ  251031P400,C,P,1,10/30/2026\n"
    )
    rows = parse_occ_volume(csv)
    by_key = {(r["underlying"], r["account_type"], r["cp"]): r["quantity"] for r in rows}
    assert by_key[("SPY", "C", "C")] == 300
    assert by_key[("QQQ", "C", "P")] == 50


def test_parse_occ_oi():
    text = (
        "Date,Equity,,,Index/Other,,,Debt,,,Futures,OCC Total\n"
        ",Calls,Puts,Total,Calls,Puts,Total,Calls,Puts,Total,Total,\n"
        '10/30/2026,"1,000","2,000","3,000","4,000","5,000","9,000","0","0","0","100","12,000",\n'
    )
    rows = parse_occ_oi_summary(text, date(2026, 10, 30))
    assert {r["series_id"] for r in rows} >= {"occ_oi_equity_calls", "occ_oi_index_puts"}


def test_parse_direxion():
    text = "Fund: SOXL\nShares Outstanding:543210\nholdings...\n"
    rows = parse_direxion(text, "SOXL", datetime(2026, 10, 30))
    assert rows[0]["shares"] == 543210 and rows[0]["issuer"] == "Direxion"


def test_parse_proshares():
    text = "Date,NAV,Shares Outstanding (000),AUM\n2026-10-30,52.1,1000,1e9\n"
    rows = parse_proshares(text, "TQQQ", datetime(2026, 10, 30))
    assert rows and rows[0]["shares"] == 1_000_000 and rows[0]["nav"] == 52.1


def test_save_raw(tmp_path):
    class C:
        def execute(self, sql, args):
            return self

        def fetchone(self):
            return {"raw_file_id": 1}

    out = save_raw(tmp_path, "cboe-chain", "u", "2026-10-30", b"data", C())
    import hashlib

    assert out["sha256"] == hashlib.sha256(b"data").hexdigest()
    assert "cboe-chain/2026-10-30" in out["path"]


def test_collect_failure_records_health(tmp_path):
    http = MagicMock()
    http.request.side_effect = RuntimeError("down")
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    out = collect_cboe_chain(http, conn, "QQQ", tmp_path, today=date(2026, 10, 30))
    assert out["rows"] == 0 and "error" in out
    calls = [c.args[0] for c in conn.execute.call_args_list if "source_health" in c.args[0]]
    assert calls


def test_parse_occ_oi_real_csv():
    text = (
        "Daily Open Interest - October 2026\n"
        "Date,Equity,,,Index/Other,,,Debt,,,Futures,OCC Total\n"
        ",Calls,Puts,Total,Calls,Puts,Total,Calls,Puts,Total,Total,\n"
        '10/30/2026,"359,968,983","266,052,729","626,021,712","22,764,890","21,558,366","44,323,256","0","0","0","402,809","670,747,777",\n'
    )
    rows = parse_occ_oi_summary(text, date(2026, 10, 30))
    by = {r["series_id"]: r["value"] for r in rows}
    assert by["occ_oi_equity_calls"] == 359_968_983 and by["occ_oi_index_puts"] == 21_558_366
    assert by["occ_oi_total"] == 670_747_777


def test_strike_always_div_1000():
    p = {
        "data": {"options": [{"option": "QQQ261030C00005000", "bid": 0.1, "ask": 0.2}]},
        "timestamp": "2026-10-30 15:45:00",
    }
    rows = parse_cboe_chain(p, "QQQ", None, date(2026, 10, 30))
    assert rows[0]["strike"] == 5.0


def test_eod_keeps_full_chain():
    p = {"data": {"options": [{"option": "QQQ261030C00500000"}, {"option": "QQQ271217C00500000"}]}}
    assert len(parse_cboe_chain(p, "QQQ", None, date(2026, 10, 30))) == 2
    assert len(parse_cboe_chain(p, "QQQ", 60, date(2026, 10, 30))) == 1


def test_top_level_timestamp_ny():
    from inves_cog.ingest.market import NY

    p = {"data": {"options": [{"option": "QQQ261030C00500000"}]}, "timestamp": "2026-10-30 15:45:00"}
    snap = parse_cboe_chain(p, "QQQ", None, date(2026, 10, 30))[0]["snapshot_at"]
    assert snap.tzinfo is not None and snap.tzinfo == NY and snap.hour == 15


def test_health_upsert_ok():
    conn = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    from inves_cog.flows.store import record_health

    record_health(conn, "Flows:X", True, 5, "note", 0.1)
    sql = conn.execute.call_args[0][0]
    assert "ON CONFLICT (source)" in sql and "consecutive_failures" in sql
