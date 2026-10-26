"""B-057: short interest, put/call sentiment, and the VIX fallback on the brief pages."""

import re
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.brief import (
    OPTION_CATEGORIES,
    option_percentile,
    option_tone,
)
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

DAY = date(2037, 6, 15)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG_DECIMAL = re.compile(r"\d+\.\d{4,}")


def _sessions(day, count):
    found = []
    cursor = day
    while len(found) < count:
        if trading_day(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
    found.reverse()
    return found


SESSIONS = _sessions(DAY, 25)


def test_s1_threshold_edges_and_s3_rank_edges():
    assert option_tone(80) is None
    assert option_tone(80.01) == "偏谨慎"
    assert option_tone(20) is None
    assert option_tone(19.99) == "偏乐观"
    high = [0.8] * 19 + [1.5]
    low = [0.4] * 19 + [0.11]
    assert option_percentile(1.5, high) == 100
    assert option_percentile(0.11, low) == 5
    assert option_percentile(1.5, high[:-1]) is None
    assert [label for _code, label in OPTION_CATEGORIES] == ["全市场", "股票期权"]


def _visible(html):
    text = _STYLE.sub(" ", html)
    return unescape(_TAG.sub(" ", text))


def _row(html, ticker):
    parts = [part for part in html.split("<tr") if f">{ticker}<" in part]
    for marker in (f'data-ticker="{ticker}"', f'data-th="{ticker}"'):
        found = [part for part in parts if marker in part]
        if found:
            return found[0]
    return parts[0]


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b057_web') THEN "
        "CREATE ROLE b057_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b057_web")


def _clear(admin):
    admin.execute("DELETE FROM ingest.short_interest WHERE observation_id LIKE 'b057-%'")
    admin.execute("DELETE FROM ingest.options_stats WHERE source = 'b057'")
    admin.execute(
        "DELETE FROM ingest.macro_observations WHERE series_id = 'VIXCLS' AND observation_date >= %s",
        (DAY - timedelta(days=40),),
    )
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))


def _short(admin, name, ticker, settlement, pct, days, change):
    admin.execute(
        """
        INSERT INTO ingest.short_interest (
            observation_id, ticker, settlement_date, publish_date, short_interest,
            avg_daily_volume, days_to_cover, si_pct_shares_outstanding, source, raw
        ) VALUES (%s, %s, %s, NULL, 1000, 100, %s, %s, 'b057', %s)
        """,
        (f"b057-{name}", ticker, settlement, days, pct, Jsonb({"changePercent": change})),
    )


def _option(admin, session, category, ratio):
    admin.execute(
        """
        INSERT INTO ingest.options_stats (
            trade_date, category, call_volume, put_volume, put_call_ratio, open_interest, source
        ) VALUES (%s, %s, 100, 80, %s, 1, 'b057')
        """,
        (session, category, ratio),
    )


def _vix(admin, observed, value, visible):
    admin.execute(
        """
        INSERT INTO ingest.macro_observations (
            series_id, observation_date, value, units, realtime_start, fetched_at
        ) VALUES ('VIXCLS', %s, %s, 'index', %s, %s)
        """,
        (observed, value, visible, CLOCK.now_utc()),
    )


def _seed(admin):
    assert trading_day(DAY)
    assert len(SESSIONS) == 25 and SESSIONS[-1] == DAY
    _clear(admin)
    current = DAY - timedelta(days=10)
    _short(admin, "nvda-old", "NVDA", DAY - timedelta(days=40), 8.0, 2.0, 1.5)
    _short(admin, "nvda", "NVDA", current, 12.34, 3.2, -4.75)
    _short(admin, "nvda-late", "NVDA", DAY + timedelta(days=3), 40.0, 9.0, 80.0)
    _short(admin, "amd", "AMD", current, 10.0, 1.0, 0.0)
    _short(admin, "avgo", "AVGO", current, 3.0, 5.0, 0.4)
    _short(admin, "amat", "AMAT", current, 2.0, 5.1, 1.2)
    for index, session in enumerate(SESSIONS):
        if index < 5:
            total, equity = 9.99, 0.05
        elif session == DAY:
            total, equity = 1.5, 0.11
        else:
            total, equity = 0.8, 0.4
        _option(admin, session, "total", total)
        _option(admin, session, "equity", equity)
    admin.execute(
        """
        INSERT INTO marketstate.market (trade_date, shock_flag, l1_state, style_spread_z, vix)
        VALUES (%s, false, '正常', '{}', NULL)
        """,
        (DAY,),
    )
    _vix(admin, DAY - timedelta(days=1), 11.11, DAY - timedelta(days=1))
    _vix(admin, DAY, 19.03, DAY)
    _vix(admin, DAY, 99.99, DAY + timedelta(days=30))


@pytest.fixture(scope="module")
def pages():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    _roles(admin)
    _seed(admin)
    bundle = {"admin": admin, "dsn": f"postgresql://b057_web@{host}/inves_cog"}
    yield bundle
    _clear(admin)
    admin.close()


def _get(pages, path):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params={"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _json(pages, path):
    return _get(pages, path).json()


def _member(pages, ticker):
    stocks = _json(pages, "/api/pages/brief/stocks")
    return next(row for theme in stocks["themes"] for row in theme["members"] if row["ticker"] == ticker)


def test_s1_short_column_matches_the_latest_visible_print(pages):
    # B-063: short interest removed from investor pages; column now shows 形态.
    nvda = _member(pages, "NVDA")
    assert "short" not in nvda and "tech" in nvda
    for ticker in ("NVDA", "AMD", "AVGO", "AMAT", "MRVL"):
        row = _row(_get(pages, "/stocks").text, ticker)
        assert "拥挤" not in row and "结算" not in row
        assert "数据不足" in row or "暂缺" in row or "排列" in row or "回调" in row or "反弹" in row or "震荡" in row


def test_s2_theme_average_skips_missing_members(pages):
    stocks = _json(pages, "/api/pages/brief/stocks")
    chip = next(theme for theme in stocks["themes"] if theme["sector"] == "AI 算力芯片")
    assert "short_covered" not in chip and "short_average" not in chip
    html = _get(pages, "/stocks").text
    assert "8.4%（覆盖 3/4）" not in html


def test_s3_put_call_uses_total_then_equity(pages):
    market = _json(pages, "/api/pages/brief/market")
    window = [9.99] * 0 + [0.8] * 19 + [1.5]
    assert option_percentile(1.5, window) == 100
    view = market["put_call"]
    assert view["category"] == "total"
    assert view["label"] == "全市场"
    assert view["value"] == 1.5
    assert view["percentile"] == 100
    assert view["tone"] == "偏谨慎"
    assert view["text"] == "1.50（全市场），近 20 个交易日 100 分位，偏谨慎"
    html = _get(pages, "/").text
    assert view["text"] in html
    assert "total" not in _visible(html) and "equity" not in _visible(html)
    admin = pages["admin"]
    try:
        admin.execute(
            "DELETE FROM ingest.options_stats WHERE source = 'b057' AND category = 'total' AND trade_date = %s",
            (DAY,),
        )
        switched = _json(pages, "/api/pages/brief/market")["put_call"]
        assert switched["category"] == "equity"
        assert switched["label"] == "股票期权"
        assert switched["value"] == 0.11
        assert switched["percentile"] == 5
        assert switched["tone"] == "偏乐观"
        assert switched["text"] == "0.11（股票期权），近 20 个交易日 5 分位，偏乐观"
        page = _get(pages, "/").text
        assert switched["text"] in page
        assert "equity" not in _visible(page)
    finally:
        _option(admin, DAY, "total", 1.5)


def test_s4_vix_fallback_four_ways(pages):
    admin = pages["admin"]

    def shown():
        market = _json(pages, "/api/pages/brief/market")
        html = _get(pages, "/").text
        return market, html

    market, html = shown()
    assert market["vix"] == pytest.approx(19.03)
    assert market["vix_source"] == "FRED"
    assert "19.03" in html and "来源 FRED" in html
    assert "11.11" not in html and "99.99" not in html and "VIXCLS" not in html
    try:
        admin.execute("UPDATE marketstate.market SET vix = 18.72 WHERE trade_date = %s", (DAY,))
        both, both_html = shown()
        # B-063: the page resolves VIX from ingest.macro_observations, not marketstate.market.
        assert both["vix"] == pytest.approx(19.03)
        assert both["vix_source"] == "FRED"
        assert "来源 CBOE" not in both_html
        admin.execute(
            """
            DELETE FROM ingest.macro_observations
            WHERE series_id = 'VIXCLS' AND observation_date = %s AND value = 19.03
            """,
            (DAY,),
        )
        market_only, market_html = shown()
        assert market_only["vix"] == pytest.approx(11.11)
        assert market_only["vix_source"] == "FRED"
        admin.execute("UPDATE marketstate.market SET vix = NULL WHERE trade_date = %s", (DAY,))
        neither, neither_html = shown()
        # B-063: stale series fall back to the latest observation with an as-of note.
        assert neither["vix"] == pytest.approx(11.11) and neither["vix_source"] == "FRED"
        assert "11.11" in neither_html and "截至" in neither_html
    finally:
        admin.execute("UPDATE marketstate.market SET vix = NULL WHERE trade_date = %s", (DAY,))
        admin.execute(
            """
            DELETE FROM ingest.macro_observations
            WHERE series_id = 'VIXCLS' AND observation_date = %s AND value = 19.03
            """,
            (DAY,),
        )
        _vix(admin, DAY, 19.03, DAY)


def test_s5_short_and_option_freshness(pages):
    trust = _json(pages, "/api/pages/brief/trust")
    states = {row["item"]: row for row in trust["statuses"]}
    # B-063: short interest removed from all pages including 复盘数据状态.
    assert "空头数据" not in states
    assert states["期权数据"]["state"] == "新鲜"
    assert states["期权数据"]["detail"] == "最近 6/15"
    html = _get(pages, "/trust").text
    assert "空头数据" not in html and "期权数据" in html and "最近 6/15" in html
    admin = pages["admin"]
    try:
        admin.execute("DELETE FROM ingest.options_stats WHERE source = 'b057' AND trade_date > %s", (SESSIONS[-4],))
        quiet = {row["item"]: row for row in _json(pages, "/api/pages/brief/trust")["statuses"]}
        assert quiet["期权数据"]["state"] == "过期"
    finally:
        _clear(admin)
        _seed(admin)


def test_s6_two_pages_stay_in_plain_language(pages):
    market = _get(pages, "/").text
    stocks = _get(pages, "/stocks").text
    visible = _visible(market) + "\n" + _visible(stocks)
    root = Path(__file__).resolve().parents[2]
    names = yaml.safe_load((root / "config/universe.yaml").read_text())["stocks"]
    allowed = {row["ticker"].lower() for row in names}
    leaked = [token for token in _LOWER.findall(visible) if token not in allowed]
    assert leaked == []
    assert _LONG_DECIMAL.search(visible) is None
    assert "1.50（全市场），近 20 个交易日 100 分位，偏谨慎" in market
    assert "19.03" in market and "来源 FRED" in market
    assert "拥挤" not in " ".join(_visible(stocks).split()) and "空头" not in stocks
    for path in ("/", "/stocks", "/account", "/trust"):
        assert _get(pages, path).status_code == 200


def test_s7_vix_yahoo_source_label(pages):
    """VIX_YAHOO wins the same-day slot when VIX_CBOE is missing (B-063 order)."""
    admin = pages["admin"]
    admin.execute(
        """
        INSERT INTO ingest.macro_observations (
            series_id, observation_date, value, units, realtime_start, fetched_at
        ) VALUES ('VIX_YAHOO', %s, 20.5, 'index', %s, %s)
        """,
        (DAY, DAY, CLOCK.now_utc()),
    )
    try:
        market = _json(pages, "/api/pages/brief/market")
        assert market["vix"] == pytest.approx(20.5)
        assert market["vix_source"] == "Yahoo"
        assert "Yahoo" in _get(pages, "/").text
    finally:
        admin.execute(
            "DELETE FROM ingest.macro_observations WHERE series_id = 'VIX_YAHOO' AND observation_date = %s", (DAY,)
        )


def test_s8_stale_vix_marks_trust_and_page(pages):
    """Latest value older than 3 sessions renders 过期 on the page and trust (B-063)."""
    admin = pages["admin"]
    try:
        admin.execute(
            "DELETE FROM ingest.macro_observations WHERE series_id = 'VIXCLS' AND observation_date >= %s",
            (DAY - timedelta(days=1),),
        )
        admin.execute(
            """
            INSERT INTO ingest.macro_observations (
                series_id, observation_date, value, units, realtime_start, fetched_at
            ) VALUES ('VIX_CBOE', %s, 17.7, 'index', %s, %s)
            """,
            (DAY - timedelta(days=6), DAY - timedelta(days=6), CLOCK.now_utc()),
        )
        market = _json(pages, "/api/pages/brief/market")
        assert market["vix"] == pytest.approx(17.7)
        assert market["vix_source"] == "CBOE" and market["vix_stale"]
        assert "过期" in _get(pages, "/").text
        states = {row["item"]: row["state"] for row in _json(pages, "/api/pages/brief/trust")["statuses"]}
        assert states["VIX"] == "过期"
    finally:
        admin.execute("DELETE FROM ingest.macro_observations WHERE series_id = 'VIX_CBOE'")
        _clear(admin)
        _seed(admin)
