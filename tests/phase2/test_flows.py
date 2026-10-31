from datetime import date, datetime
from unittest.mock import MagicMock

from inves_cog.flows.collectors import (
    collect_cboe_chain,
    parse_cboe_chain,
    parse_direxion,
    parse_occ_oi_summary,
    parse_occ_series,
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
    rows, skipped = parse_occ_volume(csv)
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


def test_collect_failure_returns_error(tmp_path):
    http = MagicMock()
    http.request.side_effect = RuntimeError("down")
    conn = MagicMock()
    out = collect_cboe_chain(http, conn, "QQQ", tmp_path, today=date(2026, 10, 30))
    assert out["rows"] == 0 and "error" in out


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

    record_health(conn, "Flows:X", True, datetime(2026, 10, 30), 5, "note", 0.1)
    sql = conn.execute.call_args[0][0]
    assert "ON CONFLICT (source)" in sql and "consecutive_failures" in sql


def test_parse_occ_series_fixture():
    import pathlib

    path = pathlib.Path("/tmp/probe/ss.txt")
    text = path.read_text() if path.exists() else "NVDA  \t\t2026\t10\t30\t50\t000\tC P \t0\t50\t250000000\n"
    rows = parse_occ_series(text, "NVDA", datetime(2026, 10, 30))
    if path.exists():
        assert rows, "fixture should parse"
    assert all(r["source"] == "OCC" for r in rows)
    calls = [r for r in rows if r["cp"] == "C"]
    puts = [r for r in rows if r["cp"] == "P"]
    assert calls and puts


def test_parse_cboe_pc_fixture():
    from inves_cog.flows.collectors import parse_cboe_pc

    payload = {
        "ratios": [
            {"name": "TOTAL PUT/CALL RATIO", "value": 0.94},
            {"name": "INDEX PUT/CALL RATIO", "value": 1.23},
            {"name": "SPX PUT/CALL RATIO", "value": 1.5},
        ]
    }
    rows = parse_cboe_pc(payload, date(2026, 10, 30), datetime(2026, 10, 31))
    assert {r["series_id"] for r in rows} >= {"cboe_pc_total"}
    assert all(r["obs_date"] == date(2026, 10, 30) for r in rows)


def test_intraday_window_skip(tmp_path):
    """A slot runs only within [slot, slot+15min): at 17:45 the 16:00 slot is skipped."""
    from unittest.mock import MagicMock

    from scripts import schedule_flows as S

    state_file = tmp_path / "st.json"
    S.STATE = state_file
    clock = MagicMock()
    clock.now_utc.return_value = datetime(2026, 10, 30, 21, 45, tzinfo=__import__("datetime").timezone.utc)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"c": 1}
    http = MagicMock()
    S._intra_slots = lambda d: ["09:45", "10:00", "16:00"]
    import inves_cog.ingest.market as M

    M.trading_day = lambda d: True
    r = S.run_once(clock, {}, http=http, conn=conn, raw_dir=tmp_path)
    assert not any(k.startswith("intra:") for k in r), r.keys()


def test_occ_runs_on_non_trading_day(tmp_path):
    from unittest.mock import MagicMock

    from scripts import schedule_flows as S

    S.STATE = tmp_path / "st.json"
    clock = MagicMock()
    clock.now_utc.return_value = datetime(2026, 10, 31, 12, 0, tzinfo=__import__("datetime").timezone.utc)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"c": 1}
    http = MagicMock()
    import inves_cog.ingest.market as M

    M.trading_day = lambda d: d == date(2026, 10, 30)
    S._prev_trading_days = lambda d, n=5: [date(2026, 10, 30)]
    r = S.run_once(clock, {}, http=http, conn=conn, raw_dir=tmp_path)
    assert "occ_vol:2026-10-30" in r or "occ_xchk:2026-10-31" in r


def test_health_agg_degraded_note():
    from inves_cog.flows.store import record_health_agg

    conn = MagicMock()
    res = [{"symbol": "QQQ", "rows": 4806}, {"symbol": "X", "rows": 0, "error": "404"}]
    assert record_health_agg(conn, "Flows:CboeChain", res, datetime(2026, 10, 30))
    args = conn.execute.call_args[0][1]
    assert args[3] == "degraded" and "X" in args[6] and args[5] == 4806


def test_health_failure_writes_false_and_valid_ts():
    from inves_cog.flows.store import record_health

    conn = MagicMock()
    conn.execute.side_effect = RuntimeError("db down")
    assert record_health(conn, "Flows:X", False, datetime(2026, 10, 30), 0, "err") is False
    conn2 = MagicMock()
    assert record_health(conn2, "Flows:X", False, datetime(2026, 10, 30), 0, "err")
    args = conn2.execute.call_args[0][1]
    assert args[2].year == 2026 and args[1] is None  # last_success stays None on failure


def test_parse_occ_volume_skips_unknown_actype():
    csv = (
        "quantity,underlying,symbol,actype,porc,exchange,actdate\n"
        "100,SPY,x,B,C,1,10/30/2026\n"
        "10,QQQ,x,C,C,1,10/30/2026\n"
    )
    rows, skipped = parse_occ_volume(csv)
    assert skipped == 1 and len(rows) == 1


def test_cboe_chain_requires_asof():
    import pytest

    p = {"data": {"options": [{"option": "QQQ261030C00500000"}]}}
    with pytest.raises(ValueError, match="asof"):
        parse_cboe_chain(p, "QQQ", None, None)


def test_proshares_newest_first_fixture():
    text = (
        "Date,NAV,Shares Outstanding (000),AUM\n"
        "2026-10-30,52.1,1000,1e9\n2026-10-29,51.9,1000,1e9\n2009-01-05,10.0,500,5e8\n"
    )
    rows = parse_proshares(text, "TQQQ", datetime(2026, 10, 30))
    assert rows[-1]["date"] == date(2026, 10, 30)  # sorted, all rows returned


def test_pc_series_id_map():
    from inves_cog.flows.collectors import pc_series_id

    assert pc_series_id("TOTAL PUT/CALL RATIO") == "cboe_pc_total"
    assert pc_series_id("INDEX PUT/CALL RATIO") == "cboe_pc_index"
    assert pc_series_id("SPX + SPXW PUT/CALL RATIO") == "cboe_pc_spx"
    assert pc_series_id("CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO") == "cboe_pc_vix"
    assert pc_series_id("SOMETHING ELSE").startswith("cboe_pc_other_")


def test_parse_cboe_pc_stable_ids():
    from inves_cog.flows.collectors import parse_cboe_pc

    payload = {
        "ratios": [{"name": "TOTAL PUT/CALL RATIO", "value": 0.94}, {"name": "INDEX PUT/CALL RATIO", "value": 1.23}]
    }
    rows = parse_cboe_pc(payload, date(2026, 10, 30), datetime(2026, 10, 30))
    assert {r["series_id"] for r in rows} == {"cboe_pc_total", "cboe_pc_index"}
