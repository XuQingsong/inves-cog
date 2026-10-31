"""B-070 live detection."""

from inves_cog.perception.live.detect import basket_hits, market_hits, stock_hits

RULE = {
    "path_b_abs_ret": 0.05,
    "path_b_z": 2.0,
    "path_a_z": 2.0,
    "path_a_same_sign": 0.5,
    "spy_abs": 0.02,
    "qqq_abs": 0.025,
}


def test_stock_hit_median_baseline():
    quotes = {"INTC": {"ret": -0.23}, "AMD": {"ret": -0.07}, "MU": {"ret": 0.01}}
    l3 = {"INTC": {"basket_id": "cpu", "members": ["INTC", "AMD", "MU"]}}
    sigmas = {"INTC": 0.03}
    hits = stock_hits(quotes, l3, sigmas, RULE, "post")
    assert len(hits) == 1 and hits[0]["subject"] == "INTC" and hits[0]["direction"] == "down"
    # resid = -0.23 - median(-0.07, 0.01) = -0.20 -> z = -0.20/0.03 = -6.67
    assert abs(hits[0]["z"] + 6.67) < 0.5


def test_stock_no_hit_below_threshold():
    hits = stock_hits({"A": {"ret": -0.03}}, {}, {"A": 0.02}, RULE, "post")
    assert hits == []


def test_basket_hit_sigma_and_share():
    quotes = {"A": {"ret": -0.07}, "B": {"ret": -0.09}, "C": {"ret": 0.001}}
    baskets = [{"basket_id": "cpu", "members": ["A", "B", "C"]}]
    hits = basket_hits(quotes, baskets, {"cpu": 0.02}, RULE)
    assert hits and hits[0]["subject"] == "cpu" and hits[0]["direction"] == "down"


def test_basket_skip_below_2_members():
    hits = basket_hits({"A": {"ret": -0.07}}, [{"basket_id": "x", "members": ["A"]}], {"x": 0.02}, RULE)
    assert hits == []


def test_market_hit_spy_qqq():
    hits = market_hits({"SPY": {"ret": -0.03}, "QQQ": {"ret": -0.01}}, RULE)
    assert [h["subject"] for h in hits] == ["SPY"]


def test_direction_flip_creates_second_row():
    up = stock_hits({"A": {"ret": 0.10}}, {}, {"A": 0.02}, RULE, "post")
    down = stock_hits({"A": {"ret": -0.10}}, {}, {"A": 0.02}, RULE, "post")
    assert up[0]["direction"] == "up" and down[0]["direction"] == "down"


def test_live_anomalies_upsert_and_fade_on_disposable_database():
    """Two rounds on real Postgres: upsert updates last/peak; a vanished
    trigger fades; a direction flip creates a second row."""
    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.perception.live.detect import apply_round
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    now = "2026-10-29T17:00:00+00:00"
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        hit = {"scope": "stock", "subject": "INTC", "ret": -0.23, "z": -6.0, "direction": "down", "as_of": now}
        apply_round(conn, [hit], now, "2026-10-29", "post")
        conn.commit()
        hit2 = dict(hit, ret=-0.25, z=-7.0, as_of="2026-10-29T17:05:00+00:00")
        apply_round(conn, [hit2], "2026-10-29T17:05:00+00:00", "2026-10-29", "post")
        conn.commit()
        row = conn.execute("SELECT * FROM perception.live_anomalies WHERE subject='INTC'").fetchone()
        assert row["last_ret"] == -0.25 and row["peak_ret"] == -0.25 and row["status"] == "active"
        # faded when no longer triggered
        apply_round(conn, [], "2026-10-29T17:10:00+00:00", "2026-10-29", "post")
        conn.commit()
        assert (
            conn.execute("SELECT status FROM perception.live_anomalies WHERE subject='INTC'").fetchone()["status"]
            == "faded"
        )
        # direction flip -> second row
        apply_round(
            conn, [dict(hit, direction="up", ret=0.3, z=8.0)], "2026-10-29T17:15:00+00:00", "2026-10-29", "post"
        )
        conn.commit()
        assert (
            conn.execute("SELECT count(*) c FROM perception.live_anomalies WHERE subject='INTC'").fetchone()["c"] == 2
        )


def test_link_stock_picks_strong_event_and_signed_lag():
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock

    from inves_cog.perception.live.link import link_causes

    day = datetime(2026, 10, 29).date()
    fs = datetime(2026, 10, 29, 20, 5, tzinfo=timezone.utc)  # anomaly 16:05 ET
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"scope": "stock", "subject": "INTC", "direction": "down", "first_seen_at": fs}
    ]
    ev_fs = fs + timedelta(minutes=6)  # news lands 16:11 -> lag = -6
    conn.execute.return_value.fetchone.return_value = {
        "event_id": "INTC:guidance:2026-10-29",
        "kind": "guidance",
        "first_seen_at": ev_fs,
    }
    n = link_causes(conn, day, {"INTC"})
    assert n == 1
    upd = conn.execute.call_args_list[-1]
    assert upd[0][1][2] == -6.0  # negative lag: price moved before news


def test_session_end_bucket():
    from datetime import datetime, timezone

    from inves_cog.ingest.market import NY
    from inves_cog.perception.live.link import _session_end

    post = _session_end(datetime(2026, 10, 29, 20, 5, tzinfo=timezone.utc))
    assert (post.astimezone(NY).hour, post.astimezone(NY).minute) == (20, 0)


def test_live_pass_end_to_end_on_disposable_database():
    """live_pass twice on real Postgres: detection rows, fade on pass 2,
    linking with negative lag, reaction base from published_at, m15 only
    after +15min, session_end absent before 20:00 ET."""
    from datetime import datetime, timedelta, timezone

    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.perception.live.run import live_pass
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    now1 = datetime(2026, 10, 29, 20, 5, tzinfo=timezone.utc)  # 16:05 ET post
    now2 = now1 + timedelta(minutes=5)
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        # seed marketstate sigma + basket + snapshots + bars
        conn.execute(
            "INSERT INTO marketstate.daily (trade_date, session, ticker, sigma)"
            " VALUES ('2026-10-29','close','INTC',0.04), ('2026-10-29','close','AMZN',0.02)"
            " ON CONFLICT DO NOTHING"
        )
        for t, px in (("INTC", 75.0), ("AMZN", 229.0)):
            conn.execute(
                "INSERT INTO ingest.intraday_snapshots (ticker,as_of,session,last,prev_close,"
                " delay_minutes,source,fetched_at) VALUES (%s,%s,'post',%s,%s,15,'IEX',%s)"
                " ON CONFLICT DO NOTHING",
                (t, now1, px, px * 1.25, now1),
            )
        conn.execute(
            "INSERT INTO ingest.info_items (info_id,kind,headline,tickers,first_seen_at,"
            " published_at,source,source_level,entities,extraction_status,flags,payload,extraction_source)"
            " VALUES ('e1','news','Intel Sees Q4 GAAP EPS $0.10 vs $0.15 Est','{INTC}',"
            " %s,%s,'Benzinga',1,'{INTC}','ok','{}','{}','{}') ON CONFLICT DO NOTHING",
            (now1 + timedelta(minutes=6), now1 + timedelta(minutes=6)),
        )
        conn.execute(
            "INSERT INTO perception.news_events (event_id,subject,kind,et_date,session,"
            " first_seen_at,last_seen_at,info_ids,headline,facts,importance,importance_parts)"
            " VALUES ('INTC:guidance:2026-10-29','INTC','guidance','2026-10-29','post',"
            " %s,%s,'{e1}','Intel Sees Q4 GAAP EPS $0.10 vs $0.15 Est','{}',80,'{}')"
            " ON CONFLICT DO NOTHING",
            (now1 + timedelta(minutes=6),) * 2,
        )
        conn.commit()
        r1 = live_pass(conn, now1)
        conn.commit()
        assert r1["hits"] >= 1
        rows = conn.execute(
            "SELECT scope,subject,direction,status,cause_event_id,cause_lag_minutes"
            " FROM perception.live_anomalies ORDER BY subject"
        ).fetchall()
        subjects = {r["subject"] for r in rows}
        assert "INTC" in subjects and "AMZN" in subjects
        intc = [r for r in rows if r["subject"] == "INTC"][0]
        assert intc["cause_event_id"] == "INTC:guidance:2026-10-29"
        assert intc["cause_lag_minutes"] == -6.0
        # pass 2: INTC recovers -> fades; AMZN still hit
        conn.execute(
            "INSERT INTO ingest.intraday_snapshots (ticker,as_of,session,last,prev_close,"
            " delay_minutes,source,fetched_at) VALUES ('INTC',%s,'post',%s,%s,15,'IEX',%s)"
            " ON CONFLICT DO NOTHING",
            (now2, 95.0, 120.0, now2),
        )
        live_pass(conn, now2)
        conn.commit()
        faded = conn.execute(
            "SELECT count(*) c FROM perception.live_anomalies WHERE subject='INTC' AND status='faded'"
        ).fetchone()["c"]
        assert faded >= 1
        # reaction: base from published_at/first_seen_at; m15 absent (now2 < +15m)
        ev = conn.execute(
            "SELECT reaction FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
        ).fetchone()
        assert ev["reaction"] and ev["reaction"]["base"]["source"] in ("published_at", "first_seen_at")
        assert "m15" not in ev["reaction"] and "session_end" not in ev["reaction"]


def test_due_scheduling_decision():
    from scripts.schedule_live_perception import due

    assert due(0, 0, 400) == (True, True)
    assert due(390, 90, 400) == (False, True)  # events 10s ago, live 310s ago
    assert due(280, 350, 400) == (True, False)  # events 120s, live 50s
    assert due(300, 350, 400) == (False, False)


def test_post_session_ret_uses_session_close():
    from datetime import date, datetime, timezone
    from unittest.mock import MagicMock

    from inves_cog.perception.live.run import _latest_quotes

    day = date(2026, 10, 29)
    now = datetime(2026, 10, 29, 20, 30, tzinfo=timezone.utc)
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"ticker": "INTC", "last": 70.0, "prev_close": 95.0, "session": "post", "as_of": now},
        {"ticker": "AMD", "last": 90.0, "prev_close": 100.0, "session": "pre", "as_of": now},
    ]
    conn.execute.return_value.fetchone.return_value = {"last": 80.0}
    quotes, skipped = _latest_quotes(conn, day, now)
    # post: 70/80-1 = -12.5% vs session close, not 70/95-1 = -26% vs prev_close
    assert abs(quotes["INTC"]["ret"] - (-0.125)) < 0.001 and quotes["INTC"]["basis"] == "session_close"
    # a row from another session is not scored in a post pass
    assert "AMD" not in quotes
    regular = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
    conn.execute.return_value.fetchall.return_value = [
        {"ticker": "AMD", "last": 90.0, "prev_close": 100.0, "session": "regular", "as_of": regular},
    ]
    quotes, _ = _latest_quotes(conn, day, regular)
    assert abs(quotes["AMD"]["ret"] - (-0.10)) < 0.001 and quotes["AMD"]["basis"] == "prev_close"


def test_sigma_cache_resets_each_et_day():
    from datetime import date

    from inves_cog.perception.live import run

    run._reset_caches(date(2026, 10, 29))
    run._SIGMA_CACHE["NVDA"] = 0.02
    run._reset_caches(date(2026, 10, 29))
    assert run._SIGMA_CACHE.get("NVDA") == 0.02
    run._reset_caches(date(2026, 10, 30))
    assert "NVDA" not in run._SIGMA_CACHE


def test_post_session_skipped_without_close():
    from datetime import date, datetime, timezone
    from unittest.mock import MagicMock

    from inves_cog.perception.live.run import _latest_quotes

    day = date(2026, 10, 29)
    now = datetime(2026, 10, 29, 20, 30, tzinfo=timezone.utc)
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"ticker": "INTC", "last": 70.0, "prev_close": 95.0, "session": "post", "as_of": now},
    ]
    conn.execute.return_value.fetchone.return_value = None  # no regular snap, no bar
    quotes, skipped = _latest_quotes(conn, day, now)
    assert "INTC" not in quotes and skipped == 1


def test_lag_text_survives_json_serialized_payload():
    """Rows reach _live_module JSON-serialized; the tag must still render."""
    import json
    from datetime import date, datetime, timezone

    from inves_cog.web.investor_html import _live_module

    base = {
        "scope": "stock",
        "subject": "INTC",
        "last_ret": -0.31,
        "peak_ret": -0.31,
        "first_seen_at": datetime(2026, 10, 30, 14, 9, tzinfo=timezone.utc),
        "cause_event_id": "INTC:guidance:2026-10-29",
        "trade_date": date(2026, 10, 30),
        "cause_headline": "Intel Sees Q4 Weak",
        "status": "active",
    }
    rows = [
        dict(base, cause_lag_minutes=1078.7, cause_first_seen=datetime(2026, 10, 29, 20, 1, tzinfo=timezone.utc)),
        dict(base, cause_lag_minutes=45, cause_first_seen=datetime(2026, 10, 30, 13, 0, tzinfo=timezone.utc)),
        dict(base, cause_lag_minutes=-6.0, cause_first_seen=datetime(2026, 10, 30, 14, 15, tzinfo=timezone.utc)),
    ]
    payload = json.loads(json.dumps({"news_modules": {"live": rows}}, default=str))
    html = _live_module(payload)
    assert "事件后约 18 小时（上一交易日盘后）" in html
    assert "事件后 45 分钟" in html
    assert "股价先动，新闻晚 6 分钟入库" in html


def test_event_headline_facts_follow_largest_gap_part_on_disposable_database():
    """Both part orders + a two-pass upsert: largest-|gap| part owns headline
    AND facts; guide_gap_pct stays 42 (the chip value)."""
    from datetime import datetime, timedelta, timezone

    import psycopg
    from psycopg.rows import dict_row

    import scripts.schedule_live_perception as sched
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    t0 = datetime(2026, 10, 29, 20, 1, tzinfo=timezone.utc)
    adjusted = {
        "info_id": "a1",
        "kind": "news",
        "tickers": ["INTC"],
        "first_seen_at": t0,
        "headline": "Intel Sees Q4 Adj EPS $0.25 vs $0.43 Est",
    }
    gaap = {
        "info_id": "g1",
        "kind": "news",
        "tickers": ["INTC"],
        "first_seen_at": t0 + timedelta(minutes=5),
        "headline": "Intel Sees Q4 GAAP EPS $0.10 vs $0.15 Est",
    }
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        for order, label in (([adjusted, gaap], "adjusted-first"), ([gaap, adjusted], "gaap-first")):
            conn.execute("DELETE FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'")
            conn.commit()
            sched._persist(conn, sched.build_events(order, {"INTC"}, None))
            conn.commit()
            row = conn.execute(
                "SELECT headline,facts FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
            ).fetchone()
            assert "Adj EPS" in row["headline"], label
            assert row["facts"].get("guide_gap_pct") == -41.9, label
        # two-pass: GAAP lands in a later pass -> existing must keep its facts+headline
        conn.execute("DELETE FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'")
        conn.commit()
        sched._persist(conn, sched.build_events([adjusted], {"INTC"}, None))
        conn.commit()
        sched._persist(conn, sched.build_events([gaap], {"INTC"}, None))
        conn.commit()
        row = conn.execute(
            "SELECT headline,facts FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
        ).fetchone()
        assert "Adj EPS" in row["headline"]
        assert row["facts"].get("guide_gap_pct") == -41.9


def test_event_headline_updates_to_facts_richest_on_replay():
    """Pre-existing GAAP headline row + replay of guidance part -> upsert
    switches headline when EXCLUDED.importance >= existing."""
    from datetime import datetime, timezone

    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.perception.events.events import build_events
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    fs = datetime(2026, 10, 29, 20, 1, tzinfo=timezone.utc)
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        # stale row: GAAP headline, no facts
        conn.execute(
            "INSERT INTO perception.news_events (event_id,subject,kind,et_date,session,"
            " first_seen_at,last_seen_at,info_ids,headline,facts,importance,importance_parts)"
            " VALUES ('INTC:guidance:2026-10-29','INTC','guidance','2026-10-29','post',"
            " %s,%s,'{n1}','Intel Reports Third-Quarter 2026 Financial Results','{}',100,'{}')"
            " ON CONFLICT DO NOTHING",
            (fs, fs),
        )
        conn.commit()
        # replay item with the facts-richest headline
        items = [
            {
                "info_id": "n2",
                "kind": "news",
                "tickers": ["INTC"],
                "first_seen_at": fs,
                "headline": "Intel Sees Q4 GAAP EPS $0.10 vs $0.15 Est",
            },
        ]
        events = build_events(items, {"INTC"}, None)
        conn.execute(
            """INSERT INTO perception.news_events
               (event_id,subject,kind,et_date,session,first_seen_at,last_seen_at,
                info_ids,headline,facts,segment,importance,importance_parts,updated_at)
               VALUES (%(event_id)s,%(subject)s,%(kind)s,%(et_date)s,'post',%(first_seen_at)s,%(last_seen_at)s,
                       %(info_ids)s,%(headline)s,%(facts)s,%(segment)s,%(importance)s,%(importance_parts)s,now())
               ON CONFLICT (event_id) DO UPDATE SET
                last_seen_at=GREATEST(perception.news_events.last_seen_at,EXCLUDED.last_seen_at),
                info_ids=(SELECT array_agg(DISTINCT x) FROM unnest(
                    perception.news_events.info_ids || EXCLUDED.info_ids) x),
                facts=perception.news_events.facts || COALESCE(EXCLUDED.facts,'{}'::jsonb),
                headline=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.headline ELSE perception.news_events.headline END,
                importance=GREATEST(perception.news_events.importance,EXCLUDED.importance),
                importance_parts=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.importance_parts ELSE perception.news_events.importance_parts END,
                segment=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.segment ELSE perception.news_events.segment END,
                updated_at=now()""",
            events[0],
        )
        conn.commit()
        row = conn.execute(
            "SELECT headline FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
        ).fetchone()
        assert "Sees Q4" in row["headline"]
