"""B-072 earnings cards — disposable-DB end-to-end + unit coverage."""

from datetime import date, datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.perception.earnings.cards import build_card, update_cards
from tests.m8.test_attribution import _disposable_database

NY = "America/New_York"


def _seed(conn):
    conn.execute(
        "INSERT INTO ingest.earnings_calendar (ticker, report_date, time) VALUES "
        "('INTC','2026-10-29','post'),('AMD','2026-11-03','post'),('ARM','2026-11-04','post') "
        "ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO ingest.bars_daily (ticker, trade_date, close) VALUES "
        "('INTC','2026-10-28',95.53),('INTC','2026-10-29',87.42),('INTC','2026-10-30',75.00),"
        "('AMD','2026-10-29',250.00),('AMD','2026-10-30',255.00),"
        "('ARM','2026-10-29',210.00),('ARM','2026-10-30',212.00),"
        "('QCOM','2026-10-29',170.00),('QCOM','2026-10-30',171.00) "
        "ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO perception.news_events "
        "(event_id,subject,kind,et_date,session,first_seen_at,last_seen_at,info_ids,"
        " headline,facts,importance) VALUES "
        "('INTC:guidance:2026-10-29','INTC','guidance','2026-10-29','post',"
        " '2026-10-29 20:11:00+00','2026-10-29 20:11:00+00','{n1}',"
        " 'Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est',"
        " '{\"guide_gap_pct\": -41.9}',100),"
        "('INTC:earnings_result:2026-10-29','INTC','earnings_result','2026-10-29','post',"
        " '2026-10-29 20:05:00+00','2026-10-29 20:05:00+00','{n2}',"
        " 'Intel Reports Q3', '{\"surprise_pct\": 3.0}',80) "
        "ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO ingest.earnings_implied_moves "
        "(ticker, report_date, report_time, captured_at, straddle_pct, spot) VALUES "
        "('AMD','2026-11-03','post','2026-10-30 19:50:00+00',0.089,501.95) "
        "ON CONFLICT DO NOTHING"
    )
    conn.commit()


def test_intc_voted_card_on_disposable_database():
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        _seed(conn)
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)  # after 10-30 close
        stage, card, missing = build_card(
            conn, "INTC", date(2026, 10, 29), "post", now, segment="cpu_pc", peers=["ARM", "QCOM"]
        )
        assert stage == "voted"
        # vote = 75.00 / 87.42 - 1
        assert card["vote_ret"] == pytest.approx(75.00 / 87.42 - 1)
        assert card["vs_implied"] == "无期权参照"  # no INTC implied-move row
        kinds = {e["kind"] for e in card["events"]}
        assert {"guidance", "earnings_result"} <= kinds
        assert card["events"][0]["kind"] == "guidance"  # importance order
        seg = card["segment_reaction"]
        assert seg is not None and seg["peers"]


def test_amd_upcoming_card_with_implied_move():
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        _seed(conn)
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        stage, card, missing = build_card(
            conn, "AMD", date(2026, 11, 3), "post", now, segment="compute", peers=["NVDA"]
        )
        assert stage == "upcoming"
        assert card["implied_move"]["straddle_pct"] == pytest.approx(0.089)
        assert "一致预期" in missing  # no consensus row seeded
        assert card["history"]["note"] == "历史不足"


def test_update_cards_writes_rows():
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        _seed(conn)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS perception.earnings_cards ("
            "ticker text, report_date date, report_time text, stage text,"
            " card jsonb, missing text[], updated_at timestamptz,"
            " PRIMARY KEY (ticker, report_date))"
        )
        conn.commit()
        n = update_cards(
            conn,
            datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
            {"INTC": "cpu_pc", "AMD": "compute", "ARM": "cpu_pc"},
        )
        assert n >= 2
        row = conn.execute("SELECT stage FROM perception.earnings_cards WHERE ticker='INTC'").fetchone()
        assert row["stage"] == "voted"


def test_reaction_base_kind_post_session():
    """Post-session event -> base_kind session_close (same-day regular close)."""
    from inves_cog.perception.live import link

    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO ingest.bars_daily (ticker, trade_date, close) VALUES "
            "('INTC','2026-10-29',87.42),('INTC','2026-10-28',95.53) ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO perception.news_events "
            "(event_id,subject,kind,et_date,session,first_seen_at,last_seen_at,info_ids,"
            " headline,facts,importance) VALUES "
            "('INTC:guidance:t','INTC','guidance','2026-10-29','post',"
            " '2026-10-29 20:11:00+00','2026-10-29 20:11:00+00','{}','h','{}',100) "
            "ON CONFLICT DO NOTHING"
        )
        conn.commit()
        link.update_reactions(conn, datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc))
        row = conn.execute("SELECT reaction FROM perception.news_events WHERE event_id='INTC:guidance:t'").fetchone()
        assert row["reaction"]["base"]["base_kind"] == "session_close"
        assert row["reaction"]["base"]["px"] == 87.42


def test_guidance_classifier_rejects_market_wraps():
    from inves_cog.perception.events.events import classify

    assert classify("Alphabet Posts Worst Week Since 2011, Intel Suffers as Chip Stocks Plunge") == "other"
    assert classify("Cantor Fitzgerald Maintains Overweight on Alphabet") == "rating"
    assert classify("Amazon Sees Best NFL Start Ever, Prime Video Ads") == "other"
    assert classify("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est") == "guidance"


def test_replay_rebuilds_and_clears_stale_events_on_disposable_database():
    """--replay: rows in range are deleted and rebuilt; out-of-range untouched;
    anomaly causes pointing at deleted ids reset to NULL."""
    import scripts.schedule_live_perception as sched

    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO perception.news_events "
            "(event_id,subject,kind,et_date,session,first_seen_at,last_seen_at,info_ids,"
            " headline,facts,importance) VALUES "
            "('INTC:guidance:2026-10-29','INTC','guidance','2026-10-29','post',"
            " '2026-10-29 20:00:00+00','2026-10-29 20:00:00+00','{stale}','Stale h','{}',100),"
            "('OLD:x:2026-10-01','OLD','earnings_result','2026-10-01','post',"
            " '2026-10-01 20:00:00+00','2026-10-01 20:00:00+00','{x}','Outside','{}',50) "
            "ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO perception.live_anomalies "
            "(trade_date,session,scope,subject,direction,first_seen_at,last_seen_at,"
            " first_ret,last_ret,peak_ret,peak_z,cause_event_id) VALUES "
            "('2026-10-29','post','stock','INTC','down','2026-10-29 20:05:00+00',"
            " '2026-10-29 20:05:00+00',-0.1,-0.1,-0.1,-5,'INTC:guidance:2026-10-29') "
            "ON CONFLICT DO NOTHING"
        )
        conn.commit()

        class Args:
            replay = ("2026-10-27", "2026-10-31")

        sched._run(conn, set(), [], [], Args())
        conn.commit()
        gone = conn.execute(
            "SELECT count(*) n FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
        ).fetchone()["n"]
        kept = conn.execute(
            "SELECT count(*) n FROM perception.news_events WHERE event_id='OLD:x:2026-10-01'"
        ).fetchone()["n"]
        anom = conn.execute("SELECT cause_event_id FROM perception.live_anomalies WHERE subject='INTC'").fetchone()
        assert gone == 0 and kept == 1
        assert anom["cause_event_id"] is None
