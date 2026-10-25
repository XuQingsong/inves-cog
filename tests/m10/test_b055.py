"""B-055: news on the brief pages, stock-only events, and the close estimate."""

import re
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import NY, trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.brief import citation_stale_note, close_estimate, event_has_stock, event_reasons
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO = "b055-paper"
DAY = date(2036, 10, 22)
PREV = date(2036, 10, 21)
SEEN = cutoff(DAY) - timedelta(hours=6)
LATE = cutoff(DAY) + timedelta(minutes=30)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
CASH = 1000
LEDGER_EQUITY = 500000
SHARES = {"NVDA": 10, "AAPL": 2}
CLOSES = {"NVDA": (90, 100), "AAPL": (80, 70)}
CHAIN = [
    "NVDA",
    "AMD",
    "AVGO",
    "MRVL",
    "MU",
    "SKHY",
    "WDC",
    "STX",
    "SNDK",
    "AMAT",
    "LRCX",
    "KLAC",
    "ASML",
    "ANET",
    "CIEN",
    "COHR",
    "LITE",
    "NOK",
    "VRT",
    "ETN",
    "GEV",
    "CEG",
    "DELL",
]
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)


def _visible(html):
    text = _STYLE.sub(" ", html)
    return unescape(_TAG.sub(" ", text))


def _row(html, ticker):
    return next(part for part in html.split("<tr") if f">{ticker}<" in part)


def test_stock_event_and_stale_citation_rules():
    pool = {"NVDA"}
    wide = {"ACME"}
    assert event_has_stock(["NVDA"], pool, wide)
    assert event_has_stock(["ACME"], pool, wide)
    assert event_has_stock(["XLP", "NVDA"], pool, wide)
    assert not event_has_stock(["XLP"], pool, wide)
    assert not event_has_stock(["iwm_qqq"], pool, wide)
    assert not event_has_stock([], pool, wide)
    same = datetime(2036, 10, 22, 14, tzinfo=timezone.utc)
    three = datetime(2036, 10, 19, 14, tzinfo=timezone.utc)
    four = datetime(2036, 10, 18, 14, tzinfo=timezone.utc)
    assert citation_stale_note(same.isoformat(), DAY) is None
    assert citation_stale_note(three.isoformat(), DAY) is None
    assert citation_stale_note(four.isoformat(), DAY) == "引用的是 4 天前的新闻"
    report = {
        "daily_text": "可能的原因：早页原因 2036-10-22T14:00:00+00:00",
        "move_card": {
            "解释": [
                {"怎么影响": "供给增加", "发布时间": "2036-10-22T14:00:00+00:00"},
                {"怎么影响": "需求放缓", "发布时间": "2036-10-10T14:00:00+00:00"},
                {"怎么影响": "第三条", "发布时间": "2036-10-22T16:00:00+00:00"},
            ]
        },
    }
    reasons = event_reasons(report, DAY)
    assert [item["text"] for item in reasons] == ["供给增加", "需求放缓"]
    assert reasons[1]["stale_note"] == "引用的是 12 天前的新闻"
    assert reasons[0]["stale_note"] is None
    page_only = event_reasons({"daily_text": report["daily_text"]}, DAY)
    assert page_only[0]["text"] == "早页原因"
    assert page_only[0]["cited_at"] == "2036-10-22T14:00:00+00:00"


def test_close_estimate_uses_every_holding():
    context = {
        "ledger": {"cash": CASH},
        "positions": {ticker: {"shares": shares} for ticker, shares in SHARES.items()},
        "bars": {
            ticker: [
                {"trade_date": PREV, "close": pair[0]},
                {"trade_date": DAY, "close": pair[1]},
            ]
            for ticker, pair in CLOSES.items()
        },
    }
    estimate = close_estimate(context, DAY)
    assert estimate["equity"] == CASH + 10 * 100 + 2 * 70
    assert estimate["day_pnl"] == 10 * (100 - 90) + 2 * (70 - 80)
    assert estimate["label"] == "按 10月22日 收盘估算"
    context["bars"]["AAPL"] = []
    assert close_estimate(context, DAY) is None


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b055_web') THEN "
        "CREATE ROLE b055_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b055_web")


def _clear(admin):
    admin.execute("DELETE FROM perception.reports WHERE anomaly_id LIKE 'b055-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b055-%'")
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND params_version = 'b055'", (DAY,))
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b055'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b055-%'")
    admin.execute("DELETE FROM ingest.wide_universe WHERE trade_date = %s AND ticker = ANY(%s)", (DAY, ["ACME", "XLP"]))
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date = %s AND factor_set = 'b055'", (DAY,))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM graph.baskets WHERE basket_id LIKE 'b055-%'")


def _news(admin, info_id, published, seen, tickers, headline, source, card=None):
    admin.execute(
        """
        INSERT INTO ingest.info_items (
            info_id, kind, published_at, first_seen_at, source, source_level, headline,
            tickers, entities, extraction_status, flags, payload, extraction_source
        ) VALUES (%s, 'news', %s, %s, %s, 1, %s, %s, '{}', 'ok', '{}', '{}', %s)
        """,
        (info_id, published, seen, source, headline, tickers, Jsonb({} if card is None else {"news_card": card})),
    )


def _anomaly(admin, anomaly_id, baskets, names, score, direction):
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
            direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
            status, universe, params_version, generated_at
        ) VALUES (
            %s, %s, 'close', ARRAY['A'], 'L3', 'alert', %s, %s,
            %s, %s, '{}', '{}', '{}', ARRAY[]::text[],
            '已发现·原因未明', 'pool', 'b055', %s
        )
        """,
        (anomaly_id, DAY, baskets, Jsonb([{"ticker": name} for name in names]), direction, score, SEEN),
    )


def _report():
    return {
        "move_card": {
            "解释": [
                {"怎么影响": "供给增加", "发布时间": "2036-10-22T14:00:00+00:00"},
                {"怎么影响": "需求放缓", "发布时间": "2036-10-10T14:00:00+00:00"},
                {"怎么影响": "第三条不应出现", "发布时间": "2036-10-22T16:00:00+00:00"},
            ]
        },
        "daily_text": (
            "可能的原因：早页原因一 2036-10-22T14:00:00+00:00\n"
            "可能的原因：早页原因二 2036-10-21T14:00:00+00:00\n"
            "可能的原因：早页第三条"
        ),
    }


def _seed(admin):
    assert trading_day(DAY)
    _clear(admin)
    stocks = yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]
    assert len(CHAIN) == 23
    assert {name for name in CHAIN}.issubset({row["ticker"] for row in stocks})
    for ticker, (previous, close) in CLOSES.items():
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, %s, 100, 'b055'), (%s, %s, %s, 100, 'b055')
            """,
            (ticker, PREV, previous, ticker, DAY, close),
        )
    admin.execute(
        """
        INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
        VALUES (%s, 'NVDA', 'close', -0.044, 'b055', '{}'), (%s, 'NVDA', 'post', 0.02, 'b055', '{}')
        """,
        (DAY, DAY),
    )
    for kind, name, session, ret in (
        ("index", "SPY", "close", -0.0118),
        ("index", "SPY", "post", 0.0002),
        ("index", "QQQ", "close", -0.0286),
        ("index", "QQQ", "post", -0.0019),
        ("index", "IWM", "close", 0.0007),
        ("index", "IWM", "post", -0.0004),
    ):
        admin.execute(
            """
            INSERT INTO marketstate.rotation (trade_date, session, group_kind, group_id, ret, health_codes)
            VALUES (%s, %s, %s, %s, %s, '{}')
            """,
            (DAY, session, kind, name, ret),
        )
    admin.execute(
        """
        INSERT INTO marketstate.market (
            trade_date, shock_flag, l1_state, style_spread_z, vix, vix3m,
            down_share_5d_pct, spy_drawdown_252_pct, sector_spread_z
        ) VALUES (%s, false, '正常', '{}', 18.72, 20.12, 37.9, -1.9, 5.4)
        """,
        (DAY,),
    )
    for basket_id, names, level, label in (
        ("b055-ai", CHAIN, "L2", "AI 产业链"),
        ("b055-eq", ["AMAT", "LRCX", "KLAC", "ASML"], "L3", "半导体设备"),
    ):
        admin.execute(
            """
            INSERT INTO graph.baskets (basket_id, level, name, benchmark, members, factor_basis)
            VALUES (%s, %s, %s, 'SMH', %s, '{}')
            """,
            (basket_id, level, label, Jsonb([{"ticker": name} for name in names])),
        )
    _anomaly(admin, "b055-ai", ["b055-ai", "b055-eq"], CHAIN, 4.7, "down")
    _anomaly(admin, "b055-xlp", ["b055-xlp"], ["XLP"], 9.9, "up")
    _anomaly(admin, "b055-style", ["b055-style"], ["iwm_qqq"], 8.8, "up")
    admin.execute(
        """
        INSERT INTO perception.reports (anomaly_id, report) VALUES ('b055-ai', %s)
        """,
        (Jsonb(_report()),),
    )
    admin.execute(
        """
        INSERT INTO ingest.wide_universe (trade_date, ticker, mktcap, adv20, included, exclude_reason, notes)
        VALUES (%s, 'XLP', 100, 10, true, 'non_common', '{}')
        """,
        (DAY,),
    )
    window_start = datetime.combine(DAY, datetime.min.time().replace(hour=4), tzinfo=NY)
    inside_early = datetime(2036, 10, 22, 14, 0, tzinfo=timezone.utc)
    inside_late = datetime(2036, 10, 22, 18, 30, tzinfo=timezone.utc)
    outside = window_start + timedelta(days=1)
    _news(admin, "b055-zh", inside_early, SEEN, ["NVDA"], "NVDA order", "路透", {"说了什么": "英伟达获得大单"})
    _news(admin, "b055-en", inside_late, SEEN, ["NVDA"], "NVDA beats", "Wire", None)
    _news(admin, "b055-late", inside_early, LATE, ["NVDA"], "after cutoff", "路透", {"说了什么": "截点后不计入"})
    _news(admin, "b055-out", outside, SEEN, ["NVDA"], "next session", "路透", {"说了什么": "下一交易日"})
    held = {}
    for ticker, shares in SHARES.items():
        held[ticker] = {"shares": shares, "avg_cost": 50, "peak_price": 80}
    state = {"positions": held}
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'b055', %s, %s, 800000, %s, %s)
        """,
        (PORTFOLIO, DAY, CASH, LEDGER_EQUITY, Jsonb(state), SEEN),
    )
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (
            %s, 'MRVL', 'b055', 'v1', 'v1', 'base', 'ok',
            10, 20, 30, false, %s, %s
        )
        """,
        (DAY, Jsonb({"inputs": {"pe_p25": 53, "pe_p50": 53, "pe_p75": 53}}), SEEN),
    )


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
    bundle = {"admin": admin, "dsn": f"postgresql://b055_web@{host}/inves_cog"}
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


def _nvda(pages):
    stocks = _json(pages, "/api/pages/brief/stocks")
    return next(row for theme in stocks["themes"] for row in theme["members"] if row["ticker"] == "NVDA")


def test_w1_stock_news_count_and_preview(pages):
    nvda = _nvda(pages)
    assert nvda["news_count"] == 2
    assert [item["summary"] for item in nvda["news"]] == ["NVDA beats", "英伟达获得大单"]
    assert nvda["news"][0]["published_beijing"] == "2036-10-23 02:30"
    assert nvda["news"][1]["source"] == "路透"
    assert all(item["summary"] != "截点后不计入" for item in nvda["news"])
    # B-062: the stock table dropped its news column; the stock page lists the news instead.
    html = _get(pages, "/s/NVDA").text
    cell = html.split("最近新闻", 1)[1]
    assert "英伟达获得大单" in cell and "路透" in cell and "2036-10-22 22:00" in cell
    assert "NVDA beats" in cell and "Wire" in cell and "2036-10-23 02:30" in cell
    assert "截点后不计入" not in html and "下一交易日" not in html
    stocks_html = _get(pages, "/stocks").text
    assert "截点后不计入" not in stocks_html and "下一交易日" not in stocks_html
    stocks = _json(pages, "/api/pages/brief/stocks")
    chip = next(theme for theme in stocks["themes"] if theme["sector"] == "AI 算力芯片")
    assert chip["news_count"] == 2


def test_w2_event_reasons_then_morning_page(pages):
    market = _json(pages, "/api/pages/brief/market")
    html = _get(pages, "/").text
    event = next(row for row in market["events"] if row["anomaly_id"] == "b055-ai")
    assert [item["text"] for item in event["reasons"]] == ["供给增加", "需求放缓"]
    assert "第三条不应出现" not in html
    assert "早页原因一" not in html
    assert "引用的是 12 天前的新闻" in html
    assert "2036-10-10T14:00:00+00:00" in html
    admin = pages["admin"]
    try:
        admin.execute(
            "UPDATE perception.reports SET report = %s WHERE anomaly_id = 'b055-ai'",
            (Jsonb({"daily_text": _report()["daily_text"]}),),
        )
        fresh = _get(pages, "/").text
        assert "早页原因一" in fresh and "早页原因二" in fresh
        assert "早页第三条" not in fresh
        assert "供给增加" not in fresh
    finally:
        admin.execute(
            "UPDATE perception.reports SET report = %s WHERE anomaly_id = 'b055-ai'",
            (Jsonb(_report()),),
        )


def test_w3_news_status_follows_the_fixture(pages):
    trust = _json(pages, "/api/pages/brief/trust")
    assert trust["news_day_count"] == 2
    expected = SEEN.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    assert trust["news_seen_beijing"] == expected
    html = _get(pages, "/trust").text
    assert "最近入库" in html and trust["news_seen_beijing"] in html
    assert "最近 1 个交易日 2 条" in html


def test_w4_only_stock_events_and_both_sessions(pages):
    market = _json(pages, "/api/pages/brief/market")
    titles = [row["title"] for row in market["events"]]
    assert titles == ["AI 产业链 23 只同日下跌"]
    html = _get(pages, "/").text
    events = html.split("今天的大事", 1)[1].split("<footer", 1)[0]
    assert "XLP" not in events and "iwm_qqq" not in events
    spy = next(row for row in market["indexes"] if row["id"] == "SPY")
    assert spy["ret"] == pytest.approx(-0.0118)
    assert spy["post"] == pytest.approx(0.0002)
    admin = pages["admin"]
    try:
        admin.execute(
            """
            INSERT INTO ingest.wide_universe (trade_date, ticker, mktcap, adv20, included, exclude_reason, notes)
            VALUES (%s, 'ACME', 100, 10, true, NULL, '{}')
            """,
            (DAY,),
        )
        _anomaly(admin, "b055-wide", ["b055-wide"], ["ACME"], 1.1, "up")
        shown = _json(pages, "/api/pages/brief/market")["events"]
        wide = next(row for row in shown if row["members"] == ["ACME"])
        assert wide["title"].endswith("1 只集体上涨")
        assert "AI 产业链 23 只同日下跌" in [row["title"] for row in shown]
    finally:
        admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id = 'b055-wide'")
        admin.execute("DELETE FROM ingest.wide_universe WHERE trade_date = %s AND ticker = 'ACME'", (DAY,))


def test_w5_close_estimate_replaces_the_ledger_day(pages):
    account = _json(pages, "/api/pages/brief/account")
    estimate = account["close_estimate"]
    assert estimate["equity"] == CASH + 10 * 100 + 2 * 70
    assert estimate["day_pnl"] == 10 * (100 - 90) + 2 * (70 - 80)
    assert estimate["label"] == "按 10月22日 收盘估算"
    assert account["equity"] == LEDGER_EQUITY
    html = _get(pages, "/account").text
    assert "$2,140" in html and "$80" in html
    assert html.count("按 10月22日 收盘估算") == 2
    assert "$500,000" not in html
    detail = _json(pages, "/api/pages/paper/portfolio")
    assert detail["equity"] == LEDGER_EQUITY
    assert detail["cash"] == CASH


def test_w6_equal_percentiles_say_the_sample_is_thin(pages):
    stocks = _json(pages, "/api/pages/brief/stocks")
    mrvl = next(row for theme in stocks["themes"] for row in theme["members"] if row["ticker"] == "MRVL")
    assert mrvl["valuation"]["pe_p25"] == mrvl["valuation"]["pe_p50"] == mrvl["valuation"]["pe_p75"] == 53
    page = _get(pages, "/s/MRVL").text
    cell = page.split("<h2>基本面与估值</h2>", 1)[1].split("</p>", 1)[0]
    assert "历史样本不足" in cell
    assert "53" not in cell


def test_w1_missing_news_shows_zero_and_untrusted(pages):
    admin = pages["admin"]
    try:
        admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b055-%'")
        published = datetime(2036, 10, 15, 15, 0, tzinfo=timezone.utc)
        _news(admin, "b055-old", published, published, ["NVDA"], "old wire", "路透", {"说了什么": "半个月前的新闻"})
        nvda = _nvda(pages)
        assert nvda["news_count"] == 0
        assert _get(pages, "/stocks").status_code == 200
        home = _get(pages, "/").text
        assert "原因暂不可信" in home
        assert "供给增加" in home
        assert "引用的是" in home
        trust = _json(pages, "/api/pages/brief/trust")
        assert trust["news_day_count"] == 0
        assert trust["news_seen_beijing"] == "2036-10-15 23:00"
        assert "最近 1 个交易日 0 条" in _get(pages, "/trust").text
    finally:
        admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b055-%'")
        window_start = datetime.combine(DAY, datetime.min.time().replace(hour=4), tzinfo=NY)
        _news(
            admin,
            "b055-zh",
            datetime(2036, 10, 22, 14, 0, tzinfo=timezone.utc),
            SEEN,
            ["NVDA"],
            "NVDA order",
            "路透",
            {"说了什么": "英伟达获得大单"},
        )
        _news(
            admin,
            "b055-en",
            datetime(2036, 10, 22, 18, 30, tzinfo=timezone.utc),
            SEEN,
            ["NVDA"],
            "NVDA beats",
            "Wire",
            None,
        )
        _news(
            admin,
            "b055-late",
            datetime(2036, 10, 22, 14, 0, tzinfo=timezone.utc),
            LATE,
            ["NVDA"],
            "after cutoff",
            "路透",
            {"说了什么": "截点后不计入"},
        )
        _news(
            admin,
            "b055-out",
            window_start + timedelta(days=1),
            SEEN,
            ["NVDA"],
            "next session",
            "路透",
            {"说了什么": "下一交易日"},
        )


def test_w7_three_page_digest(pages):
    parts = []
    for path, title in (("/", "市场总览"), ("/stocks", "我的标的"), ("/account", "纸面账户"), ("/s/NVDA", "个股")):
        parts.append(f"## {title}\n{_visible(_get(pages, path).text)}")
    Path("/tmp/b055-digest.txt").write_text("\n\n".join(parts), encoding="utf-8")
    text = Path("/tmp/b055-digest.txt").read_text(encoding="utf-8")
    assert "AI 产业链 23 只同日下跌" in text
    assert "英伟达获得大单" in text
    assert "按 10月22日 收盘估算" in text
