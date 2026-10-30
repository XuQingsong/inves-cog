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


def test_live_link_and_reaction_on_disposable_database():
    """Anomaly first, event lands later (+30min grace) -> linked on a later
    pass; reaction jsonb filled from snapshots, never recomputed."""
    from datetime import date

    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.perception.live.detect import apply_round
    from inves_cog.perception.live.link import link_causes, update_reactions
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    day = date(2026, 10, 29)
    t0 = "2026-10-29T20:05:00+00:00"  # anomaly 16:05 ET
    t1 = "2026-10-29T20:11:00+00:00"  # event first_seen 16:11 ET (lag -6)
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as conn:
        apply_round(
            conn,
            [{"scope": "stock", "subject": "INTC", "ret": -0.21, "z": -5.4, "direction": "down", "as_of": t0}],
            t0,
            day,
            "post",
        )
        conn.execute(
            "INSERT INTO perception.news_events (event_id,subject,kind,et_date,session,"
            " first_seen_at,last_seen_at,info_ids,headline,facts,importance,importance_parts)"
            " VALUES ('INTC:guidance:2026-10-29','INTC','guidance','2026-10-29','post',"
            " %s,%s,'{e1}','Intel Sees Q4 Weak','{}',80,'{}')",
            (t1, t1),
        )
        for px, ts in (
            (100.0, "2026-10-29T20:00:00+00:00"),
            (96.0, "2026-10-29T20:20:00+00:00"),
            (92.0, "2026-10-29T21:15:00+00:00"),
            (90.0, "2026-10-29T23:59:00+00:00"),
        ):
            conn.execute(
                "INSERT INTO ingest.intraday_snapshots (ticker,as_of,session,last,prev_close,"
                " delay_minutes,source,fetched_at) VALUES ('INTC',%s,'post',%s,%s,15,'IEX',%s)"
                " ON CONFLICT DO NOTHING",
                (ts, px, px * 1.05, ts),
            )
        conn.commit()
        # pass 1: window end = 20:35 -> event (20:11) already inside -> linked immediately
        n = link_causes(conn, day, {"INTC"})
        conn.commit()
        row = conn.execute("SELECT * FROM perception.live_anomalies WHERE subject='INTC'").fetchone()
        assert n == 1 and row["cause_event_id"] == "INTC:guidance:2026-10-29"
        assert row["cause_lag_minutes"] == -6.0
        update_reactions(conn, "2026-10-29T20:30:00+00:00")
        conn.commit()
        ev = conn.execute(
            "SELECT reaction FROM perception.news_events WHERE event_id='INTC:guidance:2026-10-29'"
        ).fetchone()
        r = ev["reaction"]
        # base falls back to first_seen_at when published_at missing
        assert r["base"]["px"] == 100.0 and r["base"]["source"] == "first_seen_at"
        assert abs(r["m15"]["ret"] - (96.0 / 100.0 - 1)) < 1e-9
        assert r["m60"] is not None


def test_live_module_render_and_degrade():
    from datetime import datetime, timezone

    from inves_cog.web.investor_html import _live_module

    assert _live_module({"news_modules": {}}) == ""  # empty -> module hidden
    row = {
        "scope": "stock",
        "subject": "INTC",
        "last_ret": -0.21,
        "peak_ret": -0.23,
        "first_seen_at": datetime(2026, 10, 29, 20, 5, tzinfo=timezone.utc),
        "cause_event_id": "INTC:guidance:2026-10-29",
        "cause_lag_minutes": -6.0,
        "cause_headline": "Intel Sees Q4 Weak",
        "status": "active",
    }
    html = _live_module({"news_modules": {"live": [row]}})
    assert "实时异常" in html and "股价先动，新闻晚 6 分钟入库" in html and "Intel Sees Q4" in html
    row2 = dict(row, cause_event_id=None, cause_lag_minutes=None, status="faded")
    html2 = _live_module({"news_modules": {"live": [row2]}})
    assert "原因未明" in html2 and "已消退" in html2
