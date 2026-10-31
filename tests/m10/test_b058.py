"""B-058 investor stock page: path, one-liner, trend, sentiment, news, valuation, position."""

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from html import unescape

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.fundamentals.health import BLOCKING
from inves_cog.ingest.market import NY, trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY, EXCLUDED
from inves_cog.web.brief import citation_stale_note, level, volume_multiple
from inves_cog.web.pages import VALUATION_LABEL
from inves_cog.web.public import create_app
from inves_cog.web.stock_brief import (
    _BOOK_BELOW,
    _BOOK_MISSING,
    _HEALTH_REASON,
    buy_blocker,
    forward_pe,
    plain_skip,
    session_return,
    spark_closes,
    stock_oneliner,
)

pytestmark = pytest.mark.phase1_blocking

DAY = date(2038, 4, 15)
while not trading_day(DAY):
    DAY += timedelta(days=1)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
SEEN = cutoff(DAY) - timedelta(hours=6)
LATE = cutoff(DAY) + timedelta(hours=2)
PORTFOLIO = "b058-paper"
FAIR = 101.01
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG_DECIMAL = re.compile(r"\d+\.\d{4,}")
_RULE = re.compile(r"M-\d+")
ENGLISH_HEADLINE = "Supplier adds capacity"


def _sessions(day, count):
    found = []
    cursor = day
    while len(found) < count:
        if trading_day(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
    found.reverse()
    return found


NVDA_DAYS = _sessions(DAY, 61)
LITE_DAYS = _sessions(DAY, 21)
COHR_DAYS = _sessions(DAY, 8)


def _visible(html):
    return unescape(_TAG.sub(" ", _STYLE.sub(" ", html)))


def _points(svg):
    # B-074: chart rows are embedded JSON for lightweight-charts (no inline SVG points).
    match = re.search(r"data-rows='([^']*)'", svg)
    assert match and match.group(1)
    return json.loads(unescape(match.group(1)))


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b058_web') THEN "
        "CREATE ROLE b058_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b058_web")


def _clear(admin):
    admin.execute("ALTER TABLE valuation_v1.consensus_snapshots DISABLE TRIGGER consensus_snapshots_append_only")
    admin.execute("DELETE FROM valuation_v1.consensus_snapshots WHERE raw->>'tag' = 'b058'")
    admin.execute("ALTER TABLE valuation_v1.consensus_snapshots ENABLE TRIGGER consensus_snapshots_append_only")
    admin.execute("DELETE FROM perception.ticker_status WHERE anomaly_id LIKE 'b058-%'")
    admin.execute("DELETE FROM perception.linkage_events WHERE event_id LIKE 'b058-%'")
    admin.execute("DELETE FROM perception.reports WHERE anomaly_id LIKE 'b058-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b058-%'")
    admin.execute("DELETE FROM graph.baskets WHERE basket_id LIKE 'b058-%'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b058-%'")
    admin.execute("DELETE FROM ingest.short_interest WHERE observation_id LIKE 'b058-%'")
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b058'")
    admin.execute("DELETE FROM marketstate.daily WHERE factor_set = 'b058'")
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM trading.orders WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    names = ["NVDA", "LITE", "COHR"]
    admin.execute(
        "DELETE FROM trading.daily_scores WHERE signal_date = %s AND ticker = ANY(%s)",
        (DAY, names),
    )
    admin.execute(
        "DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND ticker = ANY(%s)",
        (DAY, names),
    )


def _bars(admin, ticker, days, today_volume, prior_volume):
    closes = []
    for index, session in enumerate(days):
        close = 100 + index
        volume = today_volume if session == days[-1] else prior_volume
        closes.append(close)
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, %s, %s, 'b058')
            """,
            (ticker, session, close, volume),
        )
    return closes


def _score(admin, ticker, price, rsi, entry, quality):
    admin.execute(
        """
        INSERT INTO trading.daily_scores (
            signal_date, ticker, extractor, rule_set, params_version, tech, derived,
            quality, growth, valuation, timing, timing_subitems, rank_score, red_lines,
            tier, certainty, certainty_points, hold_score, hold_ok, fund_bad, runway_ok,
            m32_ok, gate_pass, entry_pass, consec_pass, tradable
        ) VALUES (
            %s, %s, 'fixed', 'A', 'p-2026.10', %s, %s,
            %s, 80, 80, 80, '{}', 1, '{}',
            'normal', 'medium', 1, 70, true, false, true,
            true, %s, %s, 1, true
        )
        """,
        (
            DAY,
            ticker,
            Jsonb({"price": price, "rsi": rsi, "dev50": -5, "price_vs_ma200": -10, "drawdown252": -20}),
            Jsonb({"pe": 32.4}),
            quality,
            entry,
            entry,
        ),
    )


def _range(admin, ticker):
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (
            %s, %s, 'b058', 'v1', 'v1', 'base', 'ok',
            90, %s, 180, false, %s, %s
        )
        """,
        (
            DAY,
            ticker,
            FAIR,
            Jsonb(
                {
                    "label": VALUATION_LABEL,
                    "implied_growth": 18.4,
                    "inputs": {"pe_p25": 20, "pe_p50": 28, "pe_p75": 40, "rev_cagr_3y": 22.5, "eps_growth": 15.2},
                }
            ),
            SEEN,
        ),
    )


def _news(admin, info_id, published, seen, ticker, headline, card=None):
    admin.execute(
        """
        INSERT INTO ingest.info_items (
            info_id, kind, published_at, first_seen_at, source, source_level, headline,
            tickers, entities, extraction_status, flags, payload, extraction_source
        ) VALUES (%s, 'news', %s, %s, '路透', 1, %s, %s, '{}', 'ok', '{}', '{}', %s)
        """,
        (
            info_id,
            published,
            seen,
            headline,
            [ticker],
            Jsonb({} if card is None else {"news_card": card}),
        ),
    )


def _consensus(admin, ticker, fetched, fy1, fy2, count1, count2):
    request_id = str(uuid.uuid4())
    raw = Jsonb({"tag": "b058"})
    admin.execute(
        """
        INSERT INTO valuation_v1.consensus_snapshots
            (id, request_id, kind, ticker, fetched_at, status, raw)
        VALUES (%s, %s, 'response', %s, %s, 'ok', %s)
        """,
        (str(uuid.uuid4()), request_id, ticker, fetched, raw),
    )
    for horizon, eps, count in (("FY1", fy1, count1), ("FY2", fy2, count2)):
        admin.execute(
            """
            INSERT INTO valuation_v1.consensus_snapshots (
                id, request_id, kind, ticker, fetched_at, status, fiscal_end, horizon,
                eps_avg, eps_count, raw
            ) VALUES (%s, %s, 'estimate', %s, %s, 'ok', %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), request_id, ticker, fetched, date(2039, 1, 31), horizon, eps, count, raw),
        )


def _seed(admin):
    assert trading_day(DAY)
    _clear(admin)
    nvda = _bars(admin, "NVDA", NVDA_DAYS, 1300, 1000)
    lite = _bars(admin, "LITE", LITE_DAYS, 200, 100)
    cohr = _bars(admin, "COHR", COHR_DAYS, 50, 100)
    assert nvda[-1] == 160 and len(nvda) == 61
    _score(admin, "NVDA", nvda[-1], 29, True, 80)
    _score(admin, "LITE", lite[-1], 55, True, 80)
    _score(admin, "COHR", cohr[-1], 72, False, 40)
    for ticker in ("NVDA", "LITE", "COHR"):
        _range(admin, ticker)
    for ticker, ret, post, resid in (
        ("NVDA", -0.044, 0.012, -1.2),
        ("AVGO", -0.02, None, None),
        ("LITE", -0.012, None, 0.4),
        ("COHR", -0.008, -0.004, None),
    ):
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, resid_z, factor_set, health_codes)
            VALUES (%s, %s, 'close', %s, %s, 'b058', '{}')
            """,
            (DAY, ticker, ret, resid),
        )
        if post is not None:
            admin.execute(
                """
                INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
                VALUES (%s, %s, 'post', %s, 'b058', '{}')
                """,
                (DAY, ticker, post),
            )
    admin.execute(
        """
        INSERT INTO marketstate.market (trade_date, shock_flag, l1_state, style_spread_z)
        VALUES (%s, false, '正常', '{}')
        """,
        (DAY,),
    )
    admin.execute(
        """
        INSERT INTO ingest.short_interest (
            observation_id, ticker, settlement_date, short_interest, avg_daily_volume,
            days_to_cover, si_pct_shares_outstanding, source, raw
        ) VALUES ('b058-nvda', 'NVDA', %s, 1000, 100, 3.2, 12.34, 'b058', %s)
        """,
        (DAY - timedelta(days=10), Jsonb({"changePercent": -4.75})),
    )
    names = ["NVDA", "AMD", "AVGO"]
    admin.execute(
        """
        INSERT INTO graph.baskets (basket_id, level, name, benchmark, members, factor_basis)
        VALUES ('b058-ai', 'L2', 'AI 产业链', 'SMH', %s, '{}')
        """,
        (Jsonb([{"ticker": name} for name in names]),),
    )
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
            direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
            status, universe, params_version, generated_at
        ) VALUES (
            'b058-ai', %s, 'close', ARRAY['A'], 'L3', 'alert', ARRAY['b058-ai'], %s,
            'down', 4.7, '{}', '{}', '{}', ARRAY[]::text[],
            '已发现·原因未明', 'pool', 'b058', %s
        )
        """,
        (DAY, Jsonb([{"ticker": name} for name in names]), SEEN),
    )
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, unknowns)
        VALUES ('b058-e1', 'b058-ai', '市场确认', %s, '[]')
        """,
        (Jsonb([{"at": SEEN.isoformat(), "new": "市场确认"}]),),
    )
    stale = datetime.combine(DAY - timedelta(days=10), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    fresh = datetime.combine(DAY, datetime.min.time(), tzinfo=timezone.utc).replace(hour=14).isoformat()
    admin.execute(
        "INSERT INTO perception.reports (anomaly_id, report) VALUES ('b058-ai', %s)",
        (
            Jsonb(
                {
                    "move_card": {
                        "解释": [
                            {"怎么影响": "供给增加", "发布时间": fresh},
                            {"怎么影响": "需求放缓", "发布时间": stale},
                            {"怎么影响": "第三条不应出现", "发布时间": fresh},
                        ]
                    }
                }
            ),
        ),
    )
    admin.execute(
        """
        INSERT INTO perception.ticker_status (anomaly_id, ticker, exposure, n_code)
        VALUES ('b058-ai', 'NVDA', '高', 'N1')
        """
    )
    start = datetime.combine(DAY, datetime.min.time(), tzinfo=NY).replace(hour=10)
    for index in range(11):
        moment = start + timedelta(minutes=index)
        if index == 0:
            headline, card = "最旧一条不应出现", {"说了什么": "最旧一条不应出现"}
        elif index == 10:
            headline, card = "NVDA order", {"说了什么": "英伟达获得大单"}
        else:
            headline, card = f"新闻{index}", {"说了什么": f"新闻{index}"}
        _news(admin, f"b058-n{index}", moment, SEEN, "NVDA", headline, card)
    _news(admin, "b058-en", start + timedelta(hours=2), SEEN, "NVDA", ENGLISH_HEADLINE, None)
    _news(admin, "b058-late", start, LATE, "NVDA", "截点之后不应出现", {"说了什么": "截点之后不应出现"})
    _news(admin, "b058-future", LATE, SEEN, "NVDA", "发布时间在截点后", {"说了什么": "发布时间在截点后"})
    state = {"positions": {"NVDA": {"shares": 731, "avg_cost": 80, "peak_price": 200, "tier_now": "normal"}}}
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 100000, 200000, 220000, %s, %s)
        """,
        (PORTFOLIO, DAY, Jsonb(state), SEEN),
    )
    previous = NVDA_DAYS[-2]
    admin.execute(
        """
        INSERT INTO trading.plan (
            portfolio_id, trade_date, signal_date, extractor, rule_set, params_version,
            published, generated_at, payload
        ) VALUES (%s, %s, %s, 'fixed', 'A', 'p-2026.10', true, %s, %s)
        """,
        (
            PORTFOLIO,
            DAY,
            previous,
            SEEN,
            Jsonb(
                {
                    "skips": [
                        {
                            "ticker": "LITE",
                            "reason_zh": "M-34 规则A开仓名额已满12只（当前计数12）",
                            "rule_ids": ["M-34"],
                        }
                    ]
                }
            ),
        ),
    )
    admin.execute(
        """
        INSERT INTO trading.orders (
            portfolio_id, order_id, signal_date, trade_date, ticker, side, kind,
            rule_ids, reason_zh, rule_set, params_version, status, intent
        ) VALUES (
            %s, 'b058-order', %s, %s, 'NVDA', 'buy', 'add',
            ARRAY['M-34'], 'M-34 试仓买入', 'A', 'p-2026.10', 'pending', '{}'
        )
        """,
        (PORTFOLIO, previous, DAY),
    )
    _consensus(admin, "NVDA", SEEN, 5.5, 6.25, 40, 38)
    _consensus(admin, "NVDA", LATE, 99.99, 88.88, 1, 1)
    return {"NVDA": nvda, "LITE": lite, "COHR": cohr}


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
    closes = _seed(admin)
    bundle = {"admin": admin, "dsn": f"postgresql://b058_web@{host}/inves_cog", "closes": closes}
    yield bundle
    _clear(admin)
    admin.close()


def _get(pages, path):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params={"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _json(pages, symbol):
    return _get(pages, f"/api/pages/brief/stock/{symbol}").json()


def test_d7_gate_map_covers_production_reasons():
    assert set(BLOCKING) <= set(_HEALTH_REASON)
    for code in BLOCKING | {"split_suspect", "insufficient_history"}:
        text = buy_blocker({"entry_pass": False, "null_reason": code, "books": {}, "red_lines": [], "m32_ok": True})
        assert text == _HEALTH_REASON[code]
        assert not _LOWER.search(text) and not _RULE.search(text)
    assert buy_blocker({"entry_pass": False, "null_reason": "missing_book:quality,growth", "books": {}}) == (
        f"{_BOOK_MISSING['quality']}、{_BOOK_MISSING['growth']}"
    )
    assert buy_blocker({"entry_pass": False, "null_reason": "not_a_real_gate", "books": {}}) == "暂缺"
    for line in EXCLUDED:
        text = buy_blocker({"entry_pass": False, "red_lines": [line], "m32_ok": True, "tier": "normal", "books": {}})
        assert text == line and not _RULE.search(text)
    for tier, bounds in ENTRY.items():
        for index, key in enumerate(BOOK_KEYS):
            books = {name: bound for name, bound in zip(BOOK_KEYS, bounds, strict=True)}
            books[key] = bounds[index] - 1
            row = {
                "entry_pass": False,
                "red_lines": [],
                "m32_ok": True,
                "tier": tier,
                "books": books,
                "null_reason": None,
            }
            text = buy_blocker(row)
            assert text == _BOOK_BELOW[key]
    attack = {key: 80 for key in BOOK_KEYS}
    assert (
        buy_blocker({"entry_pass": False, "red_lines": [], "m32_ok": False, "tier": "attack", "books": attack})
        == "进攻仓现金与增长不足"
    )
    assert buy_blocker({"entry_pass": True, "null_reason": "insufficient_history"}) is None
    samples = [
        "M-58 核心卖出后冷却期，暂不加仓",
        "M-40 回撤 −12% 闸门生效，暂停非防守层加仓",
        "M-18 短线过热，不追高",
        "M-58 核心卖出后冷却期，暂不开仓",
        "M-35 层买入额度不足，暂不开仓",
        "M-34 规则A开仓名额已满12只（当前计数12）",
    ]
    for tier in ("defense", "normal", "attack"):
        samples.append(f"M-40 {tier}层买入额度已满，暂不加仓")
        samples.append(
            "M-34 "
            + "；".join(
                [
                    f"{tier}层持仓已达4只",
                    "规则A开仓名额已满12只（当前计数12）",
                    "回撤 −12% 闸门生效，暂停非防守层新开仓",
                    "防守层持有评分低于55分",
                ]
            )
        )
    for sample in samples:
        text = plain_skip(sample)
        assert text and text != "暂缺"
        assert not _LOWER.search(text) and not _RULE.search(text)


def test_d1_path_links_and_old_detail(pages):
    for symbol in ("NVDA", "LITE", "COHR"):
        page = _get(pages, f"/s/{symbol}")
        assert page.headers["content-type"].startswith("text/html")
        assert "纸面跟踪，非投资建议" in page.text
    stocks = _get(pages, "/stocks").text
    account = _get(pages, "/account").text
    for symbol in ("NVDA", "LITE", "COHR"):
        assert f"/s/{symbol}?date={DAY.isoformat()}" in stocks
    assert f"/s/NVDA?date={DAY.isoformat()}" in account
    assert f"/s/LITE?date={DAY.isoformat()}" in account
    assert 'href="/stock/' not in stocks and 'href="/paper/stock/' not in stocks
    assert 'href="/stock/' not in account and 'href="/paper/stock/' not in account
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        assert client.get("/nope").status_code == 404
        assert client.get("/s/NVDA/extra").status_code == 404
        assert client.post("/s/NVDA").status_code == 405
        old = client.get("/stock/NVDA", params={"date": DAY.isoformat()})
        assert old.status_code == 200


def test_d2_oneliners_match_the_template(pages):
    nvda = _json(pages, "NVDA")
    lite = _json(pages, "LITE")
    cohr = _json(pages, "COHR")
    assert nvda["oneliner"] == stock_oneliner(
        "NVDA",
        -0.044,
        "随 AI 产业链集体下跌",
        1.3,
        29,
        held=True,
        shares=731,
        buyable=False,
        blocker=None,
        kind="标准层核心",
    )
    assert "接近超卖" in nvda["oneliner"] and "纸面持有 731 股" in nvda["oneliner"]
    assert lite["oneliner"] == stock_oneliner(
        "LITE",
        -0.012,
        "未见联动事件",
        2.0,
        55,
        held=False,
        shares=None,
        buyable=True,
        blocker=None,
    )
    assert "尚未持有，可买" in lite["oneliner"]
    assert cohr["oneliner"] == stock_oneliner(
        "COHR",
        -0.008,
        "未见联动事件",
        None,
        72,
        held=False,
        shares=None,
        buyable=False,
        blocker="质量分低于门槛",
    )
    assert "不可买，质量分低于门槛" in cohr["oneliner"]
    html = _visible(_get(pages, "/s/NVDA").text)
    assert nvda["oneliner"] in html


def test_d3_window_returns_and_sparkline(pages):
    for symbol, series in pages["closes"].items():
        payload = _json(pages, symbol)
        trend = payload["trend"]
        assert trend["closes"] == spark_closes(series)
        assert trend["ret_5"] == session_return(series, 5)
        assert trend["ret_20"] == session_return(series, 20)
        assert trend["ret_60"] == session_return(series, 60)
        html = _get(pages, f"/s/{symbol}").text
        assert len(trend["closes"]) == min(60, len(series))
        # B-073: the page chart is the 1-year daily-close series (range toggle in JS)
        assert len(_points(html)) == len(payload["chart"]) == min(260, len(series))
        assert 'src="/investor.js"' in html and 'src="/lightweight-charts.js"' in html
        assert "<script>" not in html and "http://" not in html and "https://" not in html
    nvda = _json(pages, "NVDA")["trend"]
    assert nvda["ret"] == -0.044 and nvda["post"] == 0.012
    price = pages["closes"]["NVDA"][-1]
    assert nvda["ma50"] == level(price, -5)
    assert nvda["ma200"] == level(price, -10)
    assert nvda["year_high"] == level(price, -20)
    assert volume_multiple(1300, [1000] * 20) == nvda["volume_multiple"] == 1.3


def test_d4_short_residual_and_theme(pages):
    nvda = _json(pages, "NVDA")
    assert nvda["short_text"] is None
    assert nvda["resid_text"] == "弱于板块 1.2σ"
    assert nvda["theme_ret"] == (-0.044 + -0.02) / 2
    stocks = _json_page(pages, "/api/pages/brief/stocks")
    chip = next(row for row in stocks["themes"] if row["sector"] == "AI 算力芯片")
    assert nvda["theme_ret"] == chip["average"]
    lite = _json(pages, "LITE")
    assert lite["resid_text"] == "强于板块 0.4σ"
    assert lite["theme_ret"] == (-0.012 + -0.008) / 2
    assert _json(pages, "COHR")["resid_text"] == "相对板块暂缺"
    assert _json(pages, "LITE")["short_text"] is None


def _json_page(pages, path):
    return _get(pages, path).json()


def test_d5_news_and_events(pages):
    nvda = _json(pages, "NVDA")
    summaries = [item["summary"] for item in nvda["news"]]
    assert len(summaries) == 10
    assert "最旧一条不应出现" not in summaries
    assert "截点之后不应出现" not in summaries
    assert "发布时间在截点后" not in summaries
    assert "英伟达获得大单" in summaries
    assert "NVDA order" not in summaries
    assert ENGLISH_HEADLINE in summaries
    assert all(item["source"] == "路透" for item in nvda["news"])
    assert nvda["events"][0]["status"] == "市场确认"
    assert nvda["events"][0]["exposure"] == "高"
    reasons = nvda["events"][0]["reasons"]
    assert [item["text"] for item in reasons] == ["供给增加", "需求放缓"]
    assert reasons[0]["stale_note"] is None
    assert reasons[1]["stale_note"] == citation_stale_note(reasons[1]["cited_at"], DAY)
    assert "天前的新闻" in reasons[1]["stale_note"]
    html = _visible(_get(pages, "/s/NVDA").text)
    # B-063: the 7-day news feed keeps published-in-window items; late ingestion is flagged 事后补采.
    assert "截点之后不应出现" in html and "事后补采" in html
    assert _json(pages, "COHR")["news"] == []
    assert "截点内没有该股新闻" in _get(pages, "/s/COHR").text


def test_d6_valuation_and_consensus(pages):
    nvda = _json(pages, "NVDA")
    card = nvda["valuation"]
    assert card["pe"] == 32.4
    assert card["pe_p25"] == 20 and card["pe_p50"] == 28 and card["pe_p75"] == 40
    assert card["implied_growth"] == 18.4 and card["rev_cagr_3y"] == 22.5
    assert "neutral" not in card and "bear" not in card and "bull" not in card
    price = pages["closes"]["NVDA"][-1]
    assert nvda["consensus"]["fy1"]["eps"] == 5.5
    assert nvda["consensus"]["fy1"]["count"] == 40
    assert nvda["consensus"]["fy2"]["eps"] == 6.25
    assert nvda["consensus"]["fy2"]["count"] == 38
    assert nvda["consensus"]["fy1"]["forward_pe"] == forward_pe(price, 5.5)
    assert nvda["consensus"]["fy2"]["forward_pe"] == forward_pe(price, 6.25)
    assert nvda["consensus"]["fy1"]["forward_pe"] != forward_pe(price, 99.99)
    blob = _get(pages, "/s/NVDA").text + _get(pages, "/s/LITE").text + _get(pages, "/s/COHR").text
    assert "合理价" not in blob and "101.01" not in blob and "99.99" not in blob
    for symbol in ("LITE", "COHR"):
        payload = _json(pages, symbol)
        assert payload["consensus"] is None
        assert "暂无一致预期（轮询中）" in _get(pages, f"/s/{symbol}").text


def test_d7_position_blocks(pages):
    nvda = _json(pages, "NVDA")["position"]
    price = pages["closes"]["NVDA"][-1]
    assert nvda["kind"] == "held" and nvda["shares"] == 731
    assert nvda["holding_kind"] == "标准层核心"
    assert nvda["pnl"] == price / 80 - 1
    names = [item["name"] for item in nvda["levels"]]
    assert names == ["破位减仓", "警戒减仓", "基本面清仓"]
    assert next(item["trigger"] for item in nvda["levels"] if item["name"] == "破位减仓") == 3
    assert any("试仓买入" in item for item in nvda["pending"])
    assert "试仓买入" in nvda["next_step"]
    lite = _json(pages, "LITE")["position"]
    assert lite["kind"] == "buyable"
    assert lite["ma50"] == level(pages["closes"]["LITE"][-1], -5)
    assert lite["year_high"] == level(pages["closes"]["LITE"][-1], -20)
    assert lite["why_not"] == "规则A开仓名额已满12只（当前计数12）"
    cohr = _json(pages, "COHR")["position"]
    assert cohr["kind"] == "blocked" and cohr["blocker"] == "质量分低于门槛"
    html = _visible(_get(pages, "/s/NVDA").text + _get(pages, "/s/LITE").text + _get(pages, "/s/COHR").text)
    assert not _RULE.search(html)
    assert "N1" not in html


def test_d8_visible_text_stays_plain(pages):
    blob = ""
    for symbol in ("NVDA", "LITE", "COHR"):
        blob += _visible(_get(pages, f"/s/{symbol}").text)
    scrubbed = blob.replace(ENGLISH_HEADLINE, "").replace("NVDA order", "")
    assert not _LOWER.search(scrubbed)
    assert not _LONG_DECIMAL.search(blob)
    assert not _RULE.search(blob)
