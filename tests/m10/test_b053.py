"""B-053 investor brief pages follow the mockup sections and the derived-value formulas."""

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web import brief
from inves_cog.web.brief import (
    BREADTH_RATIO,
    BROAD_DROP,
    JUDGMENT_BROAD,
    JUDGMENT_MIXED,
    JUDGMENT_ROTATION,
    ROTATION_GAP,
    disaster_line,
    judge,
    level,
    near_disaster,
    sell_params,
    session_gap,
    take_profit,
    theme_average,
    valuation_view,
    volume_multiple,
)
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO = "b053-paper"
HELD = ["NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AVGO", "MU", "TSLA", "COST", "WMT", "HD", "JPM"]
CANDIDATES = ["AMD", "MRVL", "PLTR", "CRM", "NOW", "ORCL", "NFLX", "ADBE", "LLY", "UNH", "JNJ", "MA"]
NETWORK = ["LITE", "ANET", "CIEN", "COHR", "NOK"]
MEDICAL = ["LLY", "UNH", "JNJ"]
DETAIL_PATHS = (
    "/log",
    "/market",
    "/graph",
    "/settings/data",
    "/paper/plan",
    "/paper/portfolio",
    "/paper/universe",
    "/paper/health",
    "/paper/ledger",
    "/review",
)
_HEADING = re.compile(r"<h([12])>(.*?)</h\1>")


def _back(day, count):
    cursor = day
    for _ in range(count):
        cursor -= timedelta(days=1)
        while not trading_day(cursor):
            cursor -= timedelta(days=1)
    return cursor


def _day():
    cursor = date(2034, 11, 15)
    while not trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


DAY = _day()
PREV = _back(DAY, 1)
STALE = _back(DAY, 4)
SEEN = cutoff(DAY) - timedelta(hours=6)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
PRIOR = [_back(DAY, offset) for offset in range(1, 21)]


def test_v2_judgment_boundaries():
    assert ROTATION_GAP == 0.02 and BROAD_DROP == -0.02 and BREADTH_RATIO == 0.5
    assert judge(-0.012, -0.04, -0.02, 6, 4) == JUDGMENT_MIXED
    assert judge(-0.012, -0.04, -0.0199, 6, 4) == JUDGMENT_ROTATION
    assert judge(-0.012, -0.04, -0.0199, 6, 6) == JUDGMENT_MIXED
    assert judge(-0.02, 0.0, 0.0, 4, 9) == JUDGMENT_BROAD
    assert judge(-0.02, 0.0, 0.0, 5, 10) == JUDGMENT_MIXED
    assert judge(-0.0199, 0.0, 0.0, 4, 9) == JUDGMENT_MIXED
    assert judge(None, None, None, None, None) == JUDGMENT_MIXED
    assert session_gap(STALE, DAY) > 2
    assert session_gap(PREV, DAY) == 1


def test_v3_formulas_follow_the_parameter_file(tmp_path, monkeypatch):
    sell = sell_params("p-2026.10")
    assert take_profit(50, sell) == 50 * sell["double_price"]
    assert disaster_line(100, 70, sell) == max(100, 70) * sell["disaster_peak_fraction"]
    assert level(70, -5) == 70 / (1 + -5 / 100)
    assert level(40, 4) == 40 / 1.04
    assert level(40, -8) == 40 / (1 + -8 / 100)
    assert volume_multiple(200, [100] * 20) == 2
    assert volume_multiple(200, [100] * 19) is None
    assert theme_average([-0.09, -0.09, None]) == -0.09
    assert near_disaster(70, 60) is True
    assert near_disaster(100, 60) is False
    assert valuation_view(70, 0) == {"status": "模型不适用", "neutral": None}
    assert valuation_view(40, 4321)["neutral"] is None
    assert valuation_view(70, 140)["status"] == "可用"
    assert valuation_view(70, 140.01)["neutral"] is None
    folder = tmp_path / "p-2026.10"
    folder.mkdir()
    text = (ROOT / "config/params/p-2026.10/m4.yaml").read_text()
    text = text.replace("double_price: 2\n", "double_price: 3\n", 1)
    text = text.replace("disaster_peak_fraction: 0.60\n", "disaster_peak_fraction: 0.50\n", 1)
    text = text.replace(
        "below_days: {defense: 10, normal: 3, attack: 7}",
        "below_days: {defense: 10, normal: 9, attack: 7}",
        1,
    )
    (folder / "m4.yaml").write_text(text)
    monkeypatch.setattr(brief, "PARAMS_ROOT", tmp_path)
    changed = sell_params("p-2026.10")
    assert changed["double_price"] == 3
    assert take_profit(50, changed) == 150
    assert disaster_line(100, 70, changed) == 50
    assert changed["below_days"]["normal"] == 9


def _headings(html):
    return [(level, re.sub(r"<[^>]+>", "", text)) for level, text in _HEADING.findall(html)]


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b053_web') THEN "
        "CREATE ROLE b053_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b053_web")


def _clear(admin):
    admin.execute("DELETE FROM perception.case_labels WHERE case_id LIKE 'b053-%'")
    admin.execute("DELETE FROM perception.cases WHERE case_id LIKE 'b053-%'")
    admin.execute("DELETE FROM perception.reports WHERE anomaly_id LIKE 'b053-%'")
    admin.execute("DELETE FROM perception.linkage_events WHERE event_id LIKE 'b053-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b053-%'")
    admin.execute("DELETE FROM trading.orders WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.daily_scores WHERE signal_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM overlay.versions WHERE date = %s", (DAY,))
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b053-%'")
    admin.execute("DELETE FROM ingest.bars_daily WHERE ticker = 'LITE' AND source = 'b053'")
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date IN (%s, %s)", (DAY, PREV))


def _score(admin, ticker, *, tech, entry, books=(None, None, None, None)):
    quality, growth, valuation, timing = books
    admin.execute(
        """
        INSERT INTO trading.daily_scores (
            signal_date, ticker, extractor, rule_set, params_version, tech, derived,
            quality, growth, valuation, timing, timing_subitems, rank_score, red_lines,
            tier, certainty, certainty_points, hold_score, hold_ok, fund_bad, runway_ok,
            m32_ok, gate_pass, entry_pass, consec_pass, tradable
        ) VALUES (
            %s, %s, 'fixed', 'A', 'p-2026.10', %s, '{}',
            %s, %s, %s, %s, '{}', 1, '{}',
            'normal', 'medium', 1, 50, true, false, true,
            true, true, %s, 1, true
        )
        """,
        (DAY, ticker, Jsonb(tech), quality, growth, valuation, timing, entry),
    )


def _range(admin, ticker, bear, neutral, bull):
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (
            %s, %s, 'p-2026.10', 'v1', 'v1', 'base', 'ok',
            %s, %s, %s, false, %s, %s
        )
        """,
        (DAY, ticker, bear, neutral, bull, Jsonb({"label": "估值参考 v1，不参与仓位"}), SEEN),
    )


def _seed(admin):
    _clear(admin)
    leaders = [
        ("l3", "光通信", -0.09),
        ("l3", "半导体设备", -0.08),
        ("l3", "存储", -0.07),
        ("l3", "电力", -0.06),
        ("sector", "XLP", 0.033),
        ("sector", "KRE", 0.025),
        ("sector", "XLU", 0.020),
        ("sector", "XLV", 0.013),
        ("index", "SPY", -0.012),
        ("index", "QQQ", -0.04),
        ("index", "IWM", -0.01),
        ("style", "mtum_vlue", -0.033),
        ("style", "rsp_spy", 0.019),
        ("style", "iwm_qqq", 0.029),
    ]
    for kind, name, ret in leaders:
        admin.execute(
            """
            INSERT INTO marketstate.rotation (
                trade_date, session, group_kind, group_id, ret, health_codes
            ) VALUES (%s, 'close', %s, %s, %s, '{}')
            """,
            (DAY, kind, name, ret),
        )
    returns = {ticker: -0.09 for ticker in NETWORK}
    returns.update({ticker: 0.02 for ticker in MEDICAL})
    for name in ("B053U1", "B053U2", "B053U3", "B053U4", "B053U5", "B053U6"):
        returns[name] = 0.01
    for ticker, ret in returns.items():
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
            VALUES (%s, %s, 'close', %s, 'b053', '{}')
            """,
            (DAY, ticker, ret),
        )
    admin.execute(
        """
        INSERT INTO marketstate.market (
            trade_date, shock_flag, l1_state, style_spread_z, vix, vix3m,
            down_share_5d_pct, spy_drawdown_252_pct, sector_spread_z
        ) VALUES (%s, false, '正常', '{}', NULL, 20.12, 37.9, -1.9, 5.4)
        """,
        (DAY,),
    )
    admin.execute(
        """
        INSERT INTO marketstate.market (
            trade_date, shock_flag, l1_state, style_spread_z, vix3m
        ) VALUES (%s, false, '正常', '{}', 18.72)
        """,
        (PREV,),
    )
    for past in PRIOR:
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES ('LITE', %s, 10, 100, 'b053')
            """,
            (past,),
        )
    admin.execute(
        """
        INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
        VALUES ('LITE', %s, 9, 200, 'b053')
        """,
        (DAY,),
    )
    positions = {}
    for ticker in HELD:
        positions[ticker] = {"shares": 10, "avg_cost": 80, "peak_price": 100, "tier_now": "normal"}
    positions["NVDA"].update(avg_cost=50, peak_price=100)
    positions["AAPL"].update(avg_cost=80, peak_price=100)
    state = {
        "positions": positions,
        "exits": [{"ticker": "NOK", "reason": "止损", "day": "2034-10-01", "kind": "exit"}],
    }
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 400000, 1000000, 1100000, %s, %s)
        """,
        (PORTFOLIO, DAY, Jsonb(state), SEEN),
    )
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 420000, 1020000, 1100000, '{}', %s)
        """,
        (PORTFOLIO, PREV, SEEN - timedelta(days=1)),
    )
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
            PREV,
            SEEN,
            Jsonb({"orders": [], "skips": [{"ticker": "AAPL", "reason_zh": "继续观察"}]}),
        ),
    )
    admin.execute(
        """
        INSERT INTO trading.plan (
            portfolio_id, trade_date, signal_date, extractor, rule_set, params_version,
            published, generated_at, payload
        ) VALUES (%s, %s, %s, 'fixed', 'A', 'p-2026.10', true, %s, %s)
        """,
        (
            PORTFOLIO,
            PREV,
            _back(PREV, 1),
            SEEN - timedelta(days=1),
            Jsonb({"orders": [{"ticker": "INTC", "side": "sell", "kind": "exit", "reason_zh": "止盈"}]}),
        ),
    )
    for index, ticker in enumerate(HELD[:5]):
        reason = '待成交<script>alert("x")</script>' if ticker == "NVDA" else f"待成交{ticker}"
        admin.execute(
            """
            INSERT INTO trading.orders (
                portfolio_id, order_id, signal_date, trade_date, ticker, side, kind,
                rule_ids, reason_zh, rule_set, params_version, status, intent
            ) VALUES (%s, %s, %s, %s, %s, 'sell', 'reduce', ARRAY['M-59'], %s, 'A', 'p-2026.10', 'pending', '{}')
            """,
            (PORTFOLIO, f"b053-p{index}", _back(STALE, 1), STALE, ticker, reason),
        )
    _score(
        admin,
        "NVDA",
        tech={"price": 70, "rsi": 44.4, "price_vs_ma200": -5, "dev50": -2, "drawdown252": -10},
        entry=False,
        books=(61, 62, 63, 64),
    )
    _score(
        admin,
        "AAPL",
        tech={"price": 100, "rsi": 55, "price_vs_ma200": 5, "dev50": 1, "drawdown252": -3},
        entry=False,
        books=(70, 71, 72, 73),
    )
    for ticker in CANDIDATES:
        tech = {"price": 40, "rsi": 12.5, "dev50": 4, "drawdown252": -8, "price_vs_ma200": 1}
        books = (80, 70, 60, 55) if ticker == "AMD" else (11, 12, 13, 14)
        _score(admin, ticker, tech=tech, entry=True, books=books)
    _range(admin, "NVDA", 80, 90, 100)
    _range(admin, "AAPL", 0, 0, 0)
    _range(admin, "AMD", 4000, 4321, 5000)
    anomalies = [
        ("b053-a1", "光通信", ["LITE", "ANET", "CIEN", "COHR"], 5.5, "pool"),
        ("b053-a2", "半导体设备", ["AMAT", "LRCX"], 4.4, "pool"),
        ("b053-a3", "存储", ["MU", "WDC"], 3.3, "pool"),
        ("b053-a4", "零售", ["COST"], 1.1, "pool"),
        ("b053-wide", "宽池", ["BIG"], 9.9, "wide"),
    ]
    for anomaly_id, basket, members, score, universe in anomalies:
        admin.execute(
            """
            INSERT INTO perception.anomalies (
                anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
                direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
                status, universe, params_version, generated_at
            ) VALUES (
                %s, %s, 'close', ARRAY['A'], 'L3', 'alert', %s, %s,
                'down', %s, '{}', '{}', '{}', ARRAY[]::text[],
                '已发现·原因未明', %s, 'p-2026.10', %s
            )
            """,
            (anomaly_id, DAY, [basket], Jsonb([{"ticker": name} for name in members]), score, universe, SEEN),
        )
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, unknowns)
        VALUES ('b053-e1', 'b053-a1', '已发现', %s, '[]')
        """,
        (Jsonb([{"at": SEEN.isoformat(), "old": None, "new": "已发现", "trigger": "证据", "evidence_ids": []}]),),
    )
    admin.execute(
        """
        INSERT INTO perception.reports (anomaly_id, report) VALUES ('b053-a1', %s)
        """,
        (
            Jsonb(
                {
                    "move_card": {
                        "解释": [
                            {
                                "怎么影响": "存储供给增加",
                                "发布时间": "2034-11-15T14:00:00+00:00",
                                "编号": "b053-news",
                            }
                        ]
                    }
                }
            ),
        ),
    )
    admin.execute(
        """
        INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, reason, updated_at)
        VALUES ('b053-case', 'b053-a1', %s, '未完成', '待打标', %s)
        """,
        (DAY, SEEN),
    )
    admin.execute(
        """
        INSERT INTO perception.case_labels (
            case_id, horizon, as_of, drafted, labels, reason, visible_until, written_at
        ) VALUES ('b053-case', 'T+1', %s, false, %s, '方向对', %s, %s)
        """,
        (DAY, Jsonb({"result": "方向对"}), cutoff(DAY) + timedelta(days=3), SEEN),
    )
    admin.execute(
        """
        INSERT INTO overlay.versions (
            date, generated_at, source_events_asof, params_version, payload, published
        ) VALUES (%s, %s, %s, 'p-2026.10', '{}', false)
        """,
        (DAY, SEEN, SEEN),
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
    yield {"admin": admin, "dsn": f"postgresql://b053_web@{host}/inves_cog"}
    _clear(admin)
    admin.close()


def _get(pages, path):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params={"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _json(pages, path):
    return _get(pages, path).json()


def test_v1_structure_and_detail_links(pages):
    market = _get(pages, "/")
    stocks = _get(pages, "/stocks")
    account = _get(pages, "/account")
    trust = _get(pages, "/trust")
    assert market.headers["content-type"].startswith("text/html")
    found = {
        "/": _headings(market.text),
        "/stocks": _headings(stocks.text),
        "/account": _headings(account.text),
        "/trust": _headings(trust.text),
    }
    assert [text for level, text in found["/"] if level == "1"] == ["市场总览"]
    funds, mood, events = [text for level, text in found["/"] if level == "2"]
    assert funds.startswith("资金：") and mood.startswith("情绪：") and events == "今天的大事"
    assert [text for _level, text in found["/stocks"]] == ["我的标的", "主题一览（按今日表现排序）", "逐只明细"]
    assert [text for _level, text in found["/account"]] == [
        "纸面账户",
        "持仓与关键价位",
        "已止盈 / 止损 / 清仓",
        "待选：符合买入条件但还没买的",
    ]
    assert [text for _level, text in found["/trust"]] == ["复盘与数据", "数据状态", "系统之前说的对不对（复盘）"]
    for page in (market.text, stocks.text, account.text, trust.text):
        nav = page.split("<nav>", 1)[1].split("</nav>", 1)[0]
        assert nav.index("市场总览") < nav.index("我的标的") < nav.index("纸面账户") < nav.index("复盘与数据")
        assert "大环境怎么样" in nav and "仓位怎么处理" in nav and "系统靠不靠谱" in nav
    opened = stocks.text.split("<details", 1)[1]
    assert opened.startswith(' class="theme" open>')
    assert "AI 网络与光通信" in opened.split("</details>", 1)[0]
    blob = market.text + stocks.text + account.text + trust.text
    hrefs = re.findall(r'href="([^"?#]+)', blob)
    for path in DETAIL_PATHS:
        assert path in hrefs
    assert any(item.startswith("/stock/") for item in hrefs)
    assert any(item.startswith("/paper/stock/") for item in hrefs)
    assert "/linkage/b053-e1" in hrefs
    events = _json(pages, "/api/pages/brief/market")["events"]
    assert [row["anomaly_id"] for row in events] == ["b053-a1", "b053-a2", "b053-a3"]
    closed_day = DAY + timedelta(days=1)
    while trading_day(closed_day):
        closed_day += timedelta(days=1)
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        for path in DETAIL_PATHS:
            assert client.get(path, params={"date": DAY.isoformat()}).status_code == 200
        closed = client.get("/", params={"date": closed_day.isoformat()})
        assert closed.status_code == 200 and "非交易日" in closed.text
        assert client.post("/stocks").status_code == 405


def test_v3_page_values_match_the_formulas(pages, tmp_path, monkeypatch):
    market = _json(pages, "/api/pages/brief/market")
    stocks = _json(pages, "/api/pages/brief/stocks")
    account = _json(pages, "/api/pages/brief/account")
    assert market["judgment"] == JUDGMENT_ROTATION
    assert "板块轮动而非全面恐慌" in market["oneliner"]
    theme = next(row for row in stocks["themes"] if row["sector"] == "AI 网络与光通信")
    returns = [row["ret"] for row in theme["members"] if row["ret"] is not None]
    assert theme["average"] == sum(returns) / len(returns) == -0.09
    lite = next(row for row in theme["members"] if row["ticker"] == "LITE")
    assert lite["volume_multiple"] == 2
    multiples = [row["volume_multiple"] for row in theme["members"] if row["volume_multiple"] is not None]
    assert theme["volume_multiple"] == sum(multiples) / len(multiples)
    nvda = next(row for row in account["holdings"] if row["ticker"] == "NVDA")
    sell = account["sell"]
    assert nvda["below_days"] == 3
    assert nvda["take_profit"] == nvda["avg_cost"] * sell["double_price"]
    assert nvda["disaster"] == max(nvda["peak_price"], nvda["price"]) * sell["disaster_peak_fraction"]
    flat = [row for theme_row in stocks["themes"] for row in theme_row["members"] if row["ticker"] == "NVDA"][0]
    assert nvda["ma200"] == nvda["price"] / (1 + flat["price_vs_ma200"] / 100)
    amd = next(row for row in account["candidates"] if row["ticker"] == "AMD")
    assert amd["ma50"] == amd["price"] / (1 + amd["dev50"] / 100)
    assert amd["year_high"] == amd["price"] / (1 + amd["drawdown252"] / 100)
    folder = tmp_path / "p-2026.10"
    folder.mkdir()
    text = (ROOT / "config/params/p-2026.10/m4.yaml").read_text()
    text = text.replace("double_price: 2\n", "double_price: 3\n", 1)
    text = text.replace("disaster_peak_fraction: 0.60\n", "disaster_peak_fraction: 0.50\n", 1)
    text = text.replace(
        "below_days: {defense: 10, normal: 3, attack: 7}",
        "below_days: {defense: 10, normal: 9, attack: 7}",
        1,
    )
    (folder / "m4.yaml").write_text(text)
    monkeypatch.setattr(brief, "PARAMS_ROOT", tmp_path)
    changed = _json(pages, "/api/pages/brief/account")
    row = next(item for item in changed["holdings"] if item["ticker"] == "NVDA")
    assert row["take_profit"] == 150
    assert row["disaster"] == 50
    assert row["below_days"] == 9
    assert yaml.safe_load((ROOT / "config/params/p-2026.10/m4.yaml").read_text())["m4"]["sell"]["double_price"] == 2


def test_v4_scores_and_valuation_are_copied(pages):
    account = _json(pages, "/api/pages/brief/account")
    amd = next(row for row in account["candidates"] if row["ticker"] == "AMD")
    assert amd["books"] == {"quality": 80, "growth": 70, "valuation": 60, "timing": 55}
    assert amd["entry_pass"] is True
    stocks = _json(pages, "/api/pages/brief/stocks")
    copied = [row for theme in stocks["themes"] for row in theme["members"] if row["ticker"] == "AMD"][0]
    assert copied["rsi"] == 12.5
    assert amd["valuation"]["status"] == "模型不适用" and amd["valuation"]["neutral"] is None
    html = _get(pages, "/account").text
    assert "模型不适用" in html and "4321" not in html
    nvda = next(row for row in account["holdings"] if row["ticker"] == "NVDA")
    assert nvda["valuation"]["neutral"] == 90
    assert "90" in html


def test_v5_status_follows_queries(pages):
    admin = pages["admin"]
    trust = _json(pages, "/api/pages/brief/trust")
    states = {row["item"]: row["state"] for row in trust["statuses"]}
    assert states == {
        "新闻": "缺失",
        "VIX": "暂缺",
        "M9": "已上线",
        "估值": "模型不适用",
        "订单": "警示",
        "计划": "已有",
    }
    try:
        admin.execute(
            """
            INSERT INTO ingest.info_items (
                info_id, kind, published_at, first_seen_at, source, source_level, headline,
                tickers, entities, extraction_status, flags, payload, extraction_source
            ) VALUES (
                'b053-news', 'news', %s, %s, 'fixture', 1, 'b053', '{}', '{}', 'ok', '{}', '{}', '{}'
            )
            """,
            (SEEN, SEEN),
        )
        admin.execute("UPDATE marketstate.market SET vix = 31 WHERE trade_date = %s", (DAY,))
        admin.execute("DELETE FROM overlay.versions WHERE date = %s", (DAY,))
        admin.execute(
            "UPDATE trading.orders SET signal_date = %s, trade_date = %s WHERE portfolio_id = %s",
            (PREV, DAY, PORTFOLIO),
        )
        admin.execute("DELETE FROM trading.plan WHERE portfolio_id = %s AND trade_date = %s", (PORTFOLIO, DAY))
        changed = {row["item"]: row["state"] for row in _json(pages, "/api/pages/brief/trust")["statuses"]}
        assert changed["新闻"] == "新鲜"
        assert changed["VIX"] == "已有"
        assert changed["M9"] == "未上线/缺失"
        assert changed["订单"] == "正常"
        assert changed["计划"] == "警示"
        assert _json(pages, "/api/pages/brief/market")["headings"][2] == "情绪：恐慌"
    finally:
        _seed(admin)


def test_v6_reason_line_follows_news(pages):
    quiet = _get(pages, "/").text
    assert "原因暂不可信" in quiet
    assert "存储供给增加" not in quiet
    admin = pages["admin"]
    try:
        admin.execute(
            """
            INSERT INTO ingest.info_items (
                info_id, kind, published_at, first_seen_at, source, source_level, headline,
                tickers, entities, extraction_status, flags, payload, extraction_source
            ) VALUES (
                'b053-news', 'news', %s, %s, 'fixture', 1, 'b053', '{}', '{}', 'ok', '{}', '{}', '{}'
            )
            """,
            (SEEN, SEEN),
        )
        fresh = _get(pages, "/").text
        assert "原因暂不可信" not in fresh
        assert "存储供给增加" in fresh
        assert "2034-11-15T14:00:00+00:00" in fresh
    finally:
        admin.execute("DELETE FROM ingest.info_items WHERE info_id = 'b053-news'")


def test_v7_account_table(pages):
    account = _json(pages, "/api/pages/brief/account")
    html = _get(pages, "/account").text
    assert len(account["holdings"]) == 13
    assert len(account["candidates"]) == 12
    assert sum(len(row["pending"]) for row in account["holdings"]) == 5
    nvda = next(row for row in account["holdings"] if row["ticker"] == "NVDA")
    apple = next(row for row in account["holdings"] if row["ticker"] == "AAPL")
    assert nvda["near_disaster"] is True and apple["near_disaster"] is False
    assert "止盈线" in html and "200日线" in html and "灾难止损线" in html
    assert html.count("距灾难线过近") == 2
    assert html.count('class="warn"') == 1
    sources = {row["source"] for row in account["closed_records"]}
    assert sources == {"plan", "exits"}
    assert any(row["reason_zh"] == "止盈" and row["ticker"] == "INTC" for row in account["closed_records"])
    assert any(row["reason_zh"] == "止损" and row["ticker"] == "NOK" for row in account["closed_records"])
    assert {row["ticker"] for row in account["candidates"]} == set(CANDIDATES)
    assert account["day_change"] == 1000000 / 1020000 - 1
    assert account["drawdown"] == 1000000 / 1100000 - 1
    assert "纸面跟踪，非投资建议" in html


def test_v8_market_pages_hide_the_book(pages):
    market = _json(pages, "/api/pages/brief/market")
    stocks = _json(pages, "/api/pages/brief/stocks")
    forbidden = {
        "orders",
        "order",
        "order_id",
        "cash",
        "equity",
        "positions",
        "qty",
        "shares",
        "fill_price",
        "cost",
        "notional",
    }

    def keys(value, found):
        if isinstance(value, dict):
            found.update(value)
            for item in value.values():
                keys(item, found)
        elif isinstance(value, list):
            for item in value:
                keys(item, found)

    for payload in (market, stocks):
        found = set()
        keys(payload, found)
        assert not (found & forbidden)
    market_html = _get(pages, "/").text
    stocks_html = _get(pages, "/stocks").text
    assert "b053-p0" not in market_html and "400000" not in market_html
    assert "b053-p0" not in stocks_html and "400000" not in stocks_html
    account = _get(pages, "/account").text
    assert "纸面跟踪，非投资建议" in account
    assert "<script>" not in account
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in account
    assert _get(pages, "/trust").text.count("纸面跟踪，非投资建议") >= 1


def test_review_gap_when_labels_are_absent(pages):
    admin = pages["admin"]
    admin.execute("DELETE FROM perception.case_labels WHERE case_id = 'b053-case'")
    try:
        trust = _json(pages, "/api/pages/brief/trust")
        assert trust["labels"] == []
        assert "尚无 T+1/T+5/T+20 打标记录" in _get(pages, "/trust").text
    finally:
        admin.execute(
            """
            INSERT INTO perception.case_labels (
                case_id, horizon, as_of, drafted, labels, reason, visible_until, written_at
            ) VALUES ('b053-case', 'T+1', %s, false, %s, '方向对', %s, %s)
            """,
            (DAY, Jsonb({"result": "方向对"}), cutoff(DAY) + timedelta(days=3), SEEN),
        )
