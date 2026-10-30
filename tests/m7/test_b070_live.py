"""B-070 live detection."""
import numpy as np

from inves_cog.perception.live.detect import basket_hits, market_hits, stock_hits

RULE = {"path_b_abs_ret": 0.05, "path_b_z": 2.0, "path_a_z": 2.0,
        "path_a_same_sign": 0.5, "spy_abs": 0.02, "qqq_abs": 0.025}


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

    from tests.m8.test_attribution import _disposable_database
    from inves_cog.perception.live.detect import apply_round

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
        assert conn.execute("SELECT status FROM perception.live_anomalies WHERE subject='INTC'").fetchone()["status"] == "faded"
        # direction flip -> second row
        apply_round(conn, [dict(hit, direction="up", ret=0.3, z=8.0)], "2026-10-29T17:15:00+00:00", "2026-10-29", "post")
        conn.commit()
        assert conn.execute("SELECT count(*) c FROM perception.live_anomalies WHERE subject='INTC'").fetchone()["c"] == 2
