"""fin_state PIT windowing for M9 inputs — latest filed wins, future filings invisible."""

from datetime import date, datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.clock import FrozenClock
from inves_cog.shadow.inputs import ReadInputs
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking

TARGET = date(2026, 10, 21)
SIGNAL_DAY = date(2026, 10, 20)


def _seed(conn):
    conn.execute(
        "INSERT INTO trading.daily_scores "
        "(signal_date,ticker,extractor,rule_set,params_version,tech,derived,"
        "quality,growth,valuation,timing,timing_subitems,rank_score,red_lines,"
        "tier,tier_changed_on,certainty,certainty_points,hold_score,hold_ok,"
        "fund_bad,runway_ok,m31_adjusted_valuation,m32_ok,gate_pass,entry_pass,"
        "consec_pass,tradable,null_reason) VALUES "
        "('2026-10-20','TEST1','fixed','A','p-2026.10','{}','{}',"
        "70,70,70,70,'{}',70,'{}','normal',NULL,'high',10,70,true,"
        "false,true,70,true,true,true,1,true,NULL) ON CONFLICT DO NOTHING"
    )
    rows = [
        # latest period, latest filed -> financial
        ("TEST1", "fixed", "acc-a", "10-Q", "2026-10-19", "2026-09-30", 100, 10, 5),
        # same period, older filing -> superseded duplicate
        ("TEST1", "fixed", "acc-b", "10-Q", "2026-10-10", "2026-09-30", 90, 9, 4.5),
        # previous distinct period -> previous
        ("TEST1", "fixed", "acc-c", "10-Q", "2026-08-01", "2026-06-30", 80, 8, 4),
        # filed after the signal day -> must stay invisible
        ("TEST1", "fixed", "acc-d", "10-K/A", "2026-10-30", "2026-09-30", 999, 99, 9),
    ]
    for ticker, extractor, accession, form, filed, period_end, rev, ni, eps in rows:
        conn.execute(
            "INSERT INTO fundamentals.fin_state "
            "(ticker,extractor,accession,form,filed,period_end,fiscal_period,"
            "rev_ttm,ni_ttm,eps_ttm,health_codes,field_sources,values_extra) "
            "VALUES (%s,%s,%s,%s,%s,%s,'Q',%s,%s,%s,'{}','{}','{}')",
            (ticker, extractor, accession, form, filed, period_end, rev, ni, eps),
        )
    conn.commit()


def test_fin_state_latest_filed_wins_and_future_filing_stays_invisible():
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        _seed(conn)
        bundle = ReadInputs(conn).load(
            clock=FrozenClock(datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)),
            target=TARGET,
            tickers=["TEST1"],
        )
        raw = bundle["factor_inputs"]["TEST1"]
        assert raw["rev_ttm"] == 100  # latest filed row for the latest period
        assert raw["accession"] == "acc-a"
        assert raw["prev_eps_ttm"] == 4  # second distinct period, not the superseded duplicate
        assert raw["rev_ttm"] != 999  # filed > signal_day never leaks
