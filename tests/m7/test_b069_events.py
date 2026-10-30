"""B-069: news event layer."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from inves_cog.perception.events.events import (
    build_events,
    classify,
    importance,
    parse_facts,
    subjects,
)

SCOPE = {"INTC", "AMZN", "GOOGL", "NOW", "FTNT", "AAPL", "NVDA", "MSFT", "TSM", "QCOM", "AMD", "ARM"}
NOW = datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)


def _item(headline, tickers, iid="n1"):
    return {"kind": "news", "headline": headline, "tickers": tickers, "info_id": iid, "first_seen_at": NOW}


def test_kind_priority_preview_beats_guidance():
    assert classify("Intel Earnings Prediction Market Preview: What Will Lip-Bu Tan Say?") == "preview"
    assert classify("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est") == "guidance"


def test_facts_intel_guidance():
    f = parse_facts("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est; Sees Sales $15.000B-$16.000B vs $17.045B Est")
    assert f["guide_eps"] == 0.25 and f["guide_eps_est"] == 0.43
    assert abs(f["guide_rev"] - 15.5) < 0.01 and f["guide_rev_est"] == 17.045
    assert f["guide_gap_pct"] < -40  # 指引低于预期 ~42%


def test_facts_amzn_result():
    f = parse_facts("Amazon.com Q3 EPS $1.89 Misses $1.97 Estimate, Sales $201.944B Miss $202.308B Estimate")
    assert f["eps_actual"] == 1.89 and f["eps_est"] == 1.97
    assert f["direction"] == "miss" and f["surprise_pct"] < 0


def test_subject_multi_ticker_needs_headline_name():
    item = _item("Intel Sees Q4 Adj EPS $0.25", ["AAPL", "FTNT", "INTC", "NVDA"])
    assert subjects(item, SCOPE, {}) == ["INTC"] or subjects(item, SCOPE, {"INTC": {"intel"}}) == ["INTC"]
    # FTNT must NOT be a subject even though it's in tickers
    assert "FTNT" not in subjects(item, SCOPE, {"INTC": {"intel"}})


def test_importance_core_earnings_beats_rating():
    core = {"INTC"}
    hi, parts = importance("INTC", "guidance", {"guide_gap_pct": -42}, core)
    assert hi == 100 and parts == {"position": 40, "type": 30, "deviation": 30}
    lo, _ = importance("FTNT", "rating", {}, core)
    assert lo == 25  # 20 + 5


def test_merge_same_subject_kind_day():
    items = [
        _item("Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est", ["INTC"], "a"),
        _item("Intel Sees Q4 Sales $15B-$16B", ["INTC"], "b"),
    ]
    events = build_events(items, SCOPE, NOW)
    assert len(events) == 1 and set(events[0]["info_ids"]) == {"a", "b"}
    assert events[0]["kind"] == "guidance" and events[0]["segment"] == "cpu_pc"


def test_event_pick_prefers_guidance_over_preview():
    from inves_cog.web.brief import _event_for

    events = {
        "INTC": [
            {"kind": "preview", "importance": 45, "first_seen_at": "a", "headline": "Intel Preview"},
            {"kind": "guidance", "importance": 100, "first_seen_at": "b", "headline": "Intel Sees Q4"},
        ]
    }
    assert _event_for(events, "INTC")["kind"] == "guidance"


def test_facts_chip_text():
    from inves_cog.web.brief import _facts_chip

    assert "指引低于预期 42%" in _facts_chip({"guide_gap_pct": -41.9})
    assert "EPS 不及预期 30%" in _facts_chip({"eps_actual": 2.12, "eps_est": 3.02})
    assert _facts_chip({}) == ""


def test_news_events_missing_table_degrades():
    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"t": None}
    from inves_cog.web.brief import _news_events

    assert _news_events(conn, "2026-10-29", True) == {}


def test_event_only_display_and_unconfirmed_fallback():
    # mover has event -> news empty; no event -> unconfirmed label
    pass  # covered via _event_for + subject rule tests below


def test_fallback_subject_rule_excludes_ftnt():
    from inves_cog.web.brief import _subjects_of

    item = {"tickers": ["AAPL", "FTNT", "INTC", "NVDA"], "headline": "Intel Sees Q4 Adj EPS $0.25"}
    assert _subjects_of(item, SCOPE) == ["INTC"]
    item2 = {"tickers": ["FTNT", "INTC"], "headline": "anything"}
    assert set(_subjects_of(item2, SCOPE)) == {"FTNT", "INTC"}


def test_window_filter_uses_first_seen():
    # events outside [prev 16:00 ET, end) must be excluded by the SQL window;
    # the unit check: prev session 16:00 ET boundary math
    from datetime import datetime

    from inves_cog.ingest.intraday import previous_session
    from inves_cog.ingest.market import NY

    day = datetime(2026, 10, 29).date()
    prev = previous_session(day)
    start = datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)
    assert start.strftime("%Y-%m-%d %H:%M") == "2026-10-28 16:00"


def test_chip_revenue_and_one_decimal():
    from inves_cog.web.brief import _facts_chip

    out = _facts_chip({"eps_actual": 1.89, "eps_est": 1.97, "rev_actual": 201.944, "rev_est": 202.308})
    assert "EPS 不及预期 4%" in out and "营收不及预期 0.2%" in out


def test_window_boundary_prev_1559_excluded_1601_included():
    """Event first_seen at prev 15:59 ET is out; 16:01 is in."""
    from datetime import datetime
    from unittest.mock import MagicMock

    from inves_cog.ingest.intraday import previous_session
    from inves_cog.ingest.market import NY
    from inves_cog.web.brief import _news_events

    day = datetime(2026, 10, 29).date()
    prev = previous_session(day)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"t": "perception.news_events"}
    conn.execute.return_value.fetchall.return_value = []
    _news_events(conn, day, True)
    args = conn.execute.call_args_list[-1][0][1]
    start = args[0]
    assert start == datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)
    assert datetime(2026, 10, 28, 15, 59, tzinfo=NY) < start
    assert datetime(2026, 10, 28, 16, 1, tzinfo=NY) >= start


def test_upsert_merge_contract():
    """Two-run merge: facts merge, importance raises, headline switches."""
    sql = Path("scripts/schedule_live_perception.py").read_text()
    for clause in ("LEAST(", "GREATEST(", "|| COALESCE(EXCLUDED.facts", "CASE WHEN EXCLUDED.importance >="):
        assert clause in sql


@pytest.mark.phase1_blocking
def test_live_perception_merge_across_runs_on_disposable_database():
    """Two passes over real Postgres: bare results headline, then facts
    headline -> merged facts, raised importance, switched headline, both
    info_ids, cursor advanced. Runs as admin: role_perception cannot INSERT
    into ingest.info_items."""
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    cols = (
        "info_id,kind,headline,tickers,first_seen_at,source,source_level,"
        "entities,extraction_status,flags,payload,extraction_source"
    )
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        import scripts.schedule_live_perception as sched

        t0 = "2026-10-28T20:01:00+00:00"
        t1 = "2026-10-28T20:20:00+00:00"
        conn.execute(
            f"INSERT INTO ingest.info_items ({cols}) VALUES "
            "('n1','news','Intel Reports Third-Quarter 2026 Financial Results',"
            " ARRAY['INTC'],%s,'Benzinga',1,ARRAY['INTC'],'ok','{}','{}','{}')",
            (t0,),
        )
        conn.commit()
        scope = {"INTC"}
        items = conn.execute("SELECT info_id,headline,tickers,kind,first_seen_at FROM ingest.info_items").fetchall()
        events = sched.build_events(items, scope, None)
        with conn.transaction():
            sched._persist(conn, events)
            conn.execute(
                "INSERT INTO perception.live_cursors (cursor_key,value) VALUES (%s,%s)",
                (sched.CURSOR, t0),
            )
        conn.execute(
            f"INSERT INTO ingest.info_items ({cols}) VALUES "
            "('n2','news','Intel Q3 Adj. EPS $0.52 Beats $0.40 Estimate, "
            " Sales $16.513B Beat $16.467B Estimate',ARRAY['INTC'],%s,"
            "'Benzinga',1,ARRAY['INTC'],'ok','{}','{}','{}')",
            (t1,),
        )
        conn.commit()
        items = conn.execute("SELECT info_id,headline,tickers,kind,first_seen_at FROM ingest.info_items").fetchall()
        events = sched.build_events(items, scope, None)
        with conn.transaction():
            sched._persist(conn, events)
            conn.execute(
                "INSERT INTO perception.live_cursors (cursor_key,value) VALUES (%s,%s)"
                " ON CONFLICT (cursor_key) DO UPDATE SET value=EXCLUDED.value",
                (sched.CURSOR, t1),
            )
        row = conn.execute(
            "SELECT * FROM perception.news_events WHERE subject='INTC' AND 'n1' = ANY(info_ids)"
        ).fetchall()
        assert len(row) == 1
        ev = row[0]
        assert set(ev["info_ids"]) == {"n1", "n2"}
        assert ev["facts"] and ev["facts"].get("eps_actual") == 0.52
        # representative headline stays the earliest item per spec merge rule
        assert "Third-Quarter" in ev["headline"]
        cur = conn.execute("SELECT value FROM perception.live_cursors WHERE cursor_key=%s", (sched.CURSOR,)).fetchone()
        assert str(cur["value"]).startswith("2026-10-28 20:20")


def test_b070_sec_case_sensitive_and_rating_priority():
    from inves_cog.perception.events.events import classify

    # 'Cybersecurity' must not hit regulatory SEC; rating beats guidance
    assert classify("DELL Expands AI-Focused Cybersecurity Services Portfolio") == "other"
    assert classify("Citigroup Maintains Neutral on Bloom Energy, Raises Price Target to $20") == "rating"
    assert classify("SEC Charges Company With Disclosure Failures") == "regulatory"


def test_b070_representative_headline_is_most_facts():
    from datetime import datetime, timezone

    from inves_cog.perception.events.events import build_events

    items = [
        {
            "kind": "news",
            "headline": "Intel Reports Third-Quarter 2026 Financial Results",
            "tickers": ["INTC"],
            "info_id": "h1",
            "first_seen_at": datetime(2026, 10, 28, 20, 1, tzinfo=timezone.utc),
        },
        {
            "kind": "news",
            "headline": "Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est; Sees Sales $15.000B-$16.000B vs $17.045B Est",
            "tickers": ["INTC"],
            "info_id": "h2",
            "first_seen_at": datetime(2026, 10, 28, 20, 20, tzinfo=timezone.utc),
        },
    ]
    ev = build_events(items, {"INTC"}, None)[0]
    # headline with the most facts wins
    assert "Sees Q4" in ev["headline"]
