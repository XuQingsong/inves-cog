"""B-054 presentation: close session, Chinese names, and mockup number formats."""

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
    AI_SECTORS,
    half_up,
    human_reason,
    short_unvalued_text,
    theme_sentence,
)
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
PORTFOLIO = "b054-paper"
EQUIP = ["AMAT", "LRCX", "KLAC", "ASML"]
INTERNET = ["META", "GOOGL", "AMZN", "NFLX"]
MEDICAL = ["LLY", "UNH", "JNJ"]
ENERGY = ["XOM", "CVX"]
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
BASKETS = ("b054-ai", "semi_equipment", "b054-memory", "b054-net")
UNVALUED = {
    "AVGO": "缺少输入：eps; annual_eps_reason: missing",
    "MU": "不估值：亏损且无增长",
    "JPM": "缺少周期子行业PE参数：银行",
    "GOOGL": "方法异常：三档已升序重排",
    "META": "M2未提供金融估值字段：book_value, roe",
}
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG_DECIMAL = re.compile(r"\d+\.\d{4,}")
_RULE = re.compile(r"M-\d+")


def _back(day, count):
    cursor = day
    for _ in range(count):
        cursor -= timedelta(days=1)
        while not trading_day(cursor):
            cursor -= timedelta(days=1)
    return cursor


def _day():
    cursor = date(2035, 6, 12)
    while not trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


DAY = _day()
PREV = _back(DAY, 1)
SEEN = cutoff(DAY) - timedelta(hours=6)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
PRIOR = [_back(DAY, offset) for offset in range(1, 21)]
EQUITY = 1462351
CASH = 125598
SHARES = 180
NVDA_PRICE = 100


def _universe():
    loaded = yaml.safe_load((ROOT / "config/universe.yaml").read_text())
    return loaded["stocks"], loaded["etfs"]


def test_theme_and_reason_rules():
    assert theme_sentence(-0.05, 1.31, [20, 22]) == "被集中抛售，放量；RSI 均值 21，已超卖"
    assert theme_sentence(-0.05, 1.3, [40]) == "被集中抛售；RSI 均值 40"
    assert "已超卖" not in theme_sentence(-0.05, 2, [35])
    assert theme_sentence(-0.049, None, []) == "跟随下跌"
    assert theme_sentence(-0.01, None, []) == "跟随下跌"
    assert theme_sentence(0.0101, None, []) == "资金流入，走强"
    assert theme_sentence(0.01, None, []) == "平稳"
    assert human_reason("M-40 normal层买入额度已满，暂不加仓") == "该档买入额度已满，暂不加仓"
    assert human_reason("M-58 核心卖出后冷却期，暂不加仓") == "卖出后冷却期，暂不加仓"
    assert _RULE.search(human_reason("M-59 确认加仓")) is None
    assert short_unvalued_text("未估值（缺少输入：eps）") == "未估值（缺少每股收益数据）"
    assert short_unvalued_text("未估值（缺少周期子行业PE参数：银行）") == "未估值（周期股行业参数缺失）"
    assert short_unvalued_text("未估值（不估值：亏损且无增长）") == "未估值（亏损且无增长）"
    assert short_unvalued_text("未估值（方法异常：三档已升序重排）") == "未估值（估值方法异常）"
    assert short_unvalued_text("未估值（M2未提供金融估值字段：book_value）") == "未估值（金融股不适用）"
    assert short_unvalued_text("未估值（金融）") == "未估值（金融股不适用）"


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b054_web') THEN "
        "CREATE ROLE b054_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b054_web")


def _clear(admin):
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b054-%'")
    admin.execute("DELETE FROM trading.orders WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.daily_scores WHERE signal_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND params_version = 'p-2026.10'", (DAY,))
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b054'")
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM graph.baskets WHERE basket_id = ANY(%s)", (list(BASKETS),))


def _score(admin, ticker, *, tech, entry):
    admin.execute(
        """
        INSERT INTO trading.daily_scores (
            signal_date, ticker, extractor, rule_set, params_version, tech, derived,
            quality, growth, valuation, timing, timing_subitems, rank_score, red_lines,
            tier, certainty, certainty_points, hold_score, hold_ok, fund_bad, runway_ok,
            m32_ok, gate_pass, entry_pass, consec_pass, tradable
        ) VALUES (
            %s, %s, 'fixed', 'A', 'p-2026.10', %s, '{}',
            60, 60, 60, 60, '{}', 1, '{}',
            'normal', 'medium', 1, 50, true, false, true,
            true, true, %s, 1, true
        )
        """,
        (DAY, ticker, Jsonb(tech), entry),
    )


def _seed(admin):
    _clear(admin)
    stocks, _etfs = _universe()
    returns = {row["ticker"]: 0.004 for row in stocks}
    for ticker in EQUIP:
        returns[ticker] = -0.08
    for ticker in INTERNET:
        returns[ticker] = -0.03
    for ticker in MEDICAL:
        returns[ticker] = 0.02
    for ticker in ENERGY:
        returns[ticker] = 0.005
    returns["NVDA"] = -0.044
    for ticker, ret in returns.items():
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
            VALUES (%s, %s, 'close', %s, 'b054', '{}')
            """,
            (DAY, ticker, ret),
        )
    admin.execute(
        """
        INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
        VALUES (%s, 'NVDA', 'post', 0.05, 'b054', '{}'), (%s, 'AMAT', 'post', 0.05, 'b054', '{}')
        """,
        (DAY, DAY),
    )
    rotation = [
        ("index", "SPY", "close", -0.0118),
        ("index", "QQQ", "close", -0.0286),
        ("index", "IWM", "close", 0.0007),
        ("index", "SPY", "post", 0.0002),
        ("index", "QQQ", "post", -0.0019),
        ("index", "IWM", "post", -0.0004),
        ("l3", "semi_equipment", "close", -0.091),
        ("sector", "XLP", "close", 0.0331),
        ("style", "mtum_vlue", "close", -0.0332),
        ("style", "rsp_spy", "close", 0.0191),
        ("style", "iwm_qqq", "close", 0.0293),
    ]
    for kind, name, session, ret in rotation:
        admin.execute(
            """
            INSERT INTO marketstate.rotation (
                trade_date, session, group_kind, group_id, ret, health_codes
            ) VALUES (%s, %s, %s, %s, %s, '{}')
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
    members = {
        "b054-ai": (CHAIN, "L2", "AI 产业链"),
        "semi_equipment": (EQUIP, "L3", "半导体设备"),
        "b054-memory": (["MU", "WDC", "STX", "SNDK"], "L3", "存储"),
        "b054-net": (["ANET", "CIEN", "COHR", "LITE"], "L3", "AI 网络与光"),
    }
    for basket_id, (names, level, label) in members.items():
        payload = [{"ticker": name, "weight": 1 / len(names)} for name in names]
        admin.execute(
            """
            INSERT INTO graph.baskets (basket_id, level, name, benchmark, members, factor_basis)
            VALUES (%s, %s, %s, 'SMH', %s, '{}')
            """,
            (basket_id, level, label, Jsonb(payload)),
        )
    anomalies = [
        ("b054-multi", ["b054-memory", "b054-net", "semi_equipment"], CHAIN, 4.7, "down"),
        ("b054-single", ["semi_equipment"], EQUIP, 3.2, "down"),
        ("b054-style", ["iwm_qqq"], ["NVDA", "AMD"], 9.9, "down"),
    ]
    for anomaly_id, baskets, names, score, direction in anomalies:
        admin.execute(
            """
            INSERT INTO perception.anomalies (
                anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
                direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
                status, universe, params_version, generated_at
            ) VALUES (
                %s, %s, 'close', ARRAY['A'], 'L3', 'alert', %s, %s,
                %s, %s, '{}', '{}', '{}', ARRAY[]::text[],
                '已发现·原因未明', 'pool', 'p-2026.10', %s
            )
            """,
            (
                anomaly_id,
                DAY,
                baskets,
                Jsonb([{"ticker": name} for name in names]),
                direction,
                score,
                SEEN,
            ),
        )
    for past in PRIOR:
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES ('AMAT', %s, 50, 100, 'b054')
            """,
            (past,),
        )
    admin.execute(
        """
        INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
        VALUES ('AMAT', %s, 46, 184, 'b054')
        """,
        (DAY,),
    )
    _score(admin, "NVDA", tech={"price": NVDA_PRICE, "rsi": 44.4, "price_vs_ma200": 5}, entry=True)
    _score(admin, "AAPL", tech={"price": 70, "rsi": 55, "price_vs_ma200": -5}, entry=False)
    _score(admin, "LITE", tech={"price": 40, "rsi": 30}, entry=True)
    for ticker in EQUIP:
        _score(admin, ticker, tech={"price": 50, "rsi": 20, "price_vs_ma200": -8}, entry=False)
    admin.execute(
        "UPDATE trading.daily_scores SET derived = %s WHERE signal_date = %s AND ticker = 'NVDA'",
        (Jsonb({"pe": 22.84}), DAY),
    )
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (
            %s, 'NVDA', 'p-2026.10', 'v1', 'v1', 'base', 'ok',
            80, 150, 200, false, %s, %s
        )
        """,
        (
            DAY,
            Jsonb({"inputs": {"pe_p25": 18.2, "pe_p50": 30.4, "pe_p75": 45}, "implied_growth": 12.5}),
            SEEN,
        ),
    )
    for ticker, reason in UNVALUED.items():
        admin.execute(
            """
            INSERT INTO valuation_v1.ranges (
                trade_date, ticker, params_version, method_version, version, type, status,
                bear, neutral, bull, pending_review, payload, observed_at
            ) VALUES (
                %s, %s, 'p-2026.10', 'v1', 'v1', 'base', 'unvalued',
                NULL, NULL, NULL, false, %s, %s
            )
            """,
            (DAY, ticker, Jsonb({"reason": reason}), SEEN),
        )
    state = {
        "positions": {
            "NVDA": {"shares": SHARES, "avg_cost": 80.55, "peak_price": 140, "tier_now": "normal"},
            "AAPL": {"shares": 10, "avg_cost": 367, "peak_price": 400, "tier_now": "normal"},
            "MSFT": {"shares": 10, "avg_cost": 50, "peak_price": 80, "tier_now": "normal"},
        }
    }
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', %s, %s, 1600000, %s, %s)
        """,
        (PORTFOLIO, DAY, CASH, EQUITY, Jsonb(state), SEEN),
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
            Jsonb(
                {
                    "orders": [],
                    "skips": [
                        {"ticker": "AAPL", "reason_zh": "M-40 normal层买入额度已满，暂不加仓"},
                        {"ticker": "MSFT", "reason_zh": "M-58 核心卖出后冷却期，暂不加仓"},
                    ],
                }
            ),
        ),
    )
    for index in range(2):
        admin.execute(
            """
            INSERT INTO trading.orders (
                portfolio_id, order_id, signal_date, trade_date, ticker, side, kind,
                rule_ids, reason_zh, rule_set, params_version, status, intent
            ) VALUES (%s, %s, %s, %s, 'NVDA', 'buy', 'add', ARRAY['M-59'], %s, 'A', 'p-2026.10', 'pending', '{}')
            """,
            (PORTFOLIO, f"b054-p{index}", PREV, DAY, "M-59 确认加仓"),
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
    bundle = {"admin": admin, "dsn": f"postgresql://b054_web@{host}/inves_cog"}
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


def _visible(html):
    text = _STYLE.sub(" ", html)
    text = _TAG.sub(" ", text)
    return unescape(text)


def _row(html, ticker):
    return next(part for part in html.split("<tr") if f">{ticker}<" in part)


def _cells(row):
    values = []
    for part in row.split("<td")[1:]:
        inner = part.split(">", 1)[1].split("</td>", 1)[0]
        values.append(_TAG.sub("", inner))
    return values


def test_f1_close_session_drives_judgment(pages):
    market = _json(pages, "/api/pages/brief/market")
    html = _get(pages, "/").text
    spy = next(row for row in market["indexes"] if row["id"] == "SPY")
    assert spy["ret"] == pytest.approx(-0.0118)
    assert spy["post"] == pytest.approx(0.0002)
    assert market["judgment"] == "板块轮动而非全面恐慌"
    assert "判断：板块轮动而非全面恐慌" in market["oneliner"]
    assert "判断：分化" not in market["oneliner"]
    block = html.split("标普 500", 1)[1].split("</div>", 1)[0]
    assert "−1.18%" in block
    assert "盘后" in block and "+0.02%" in block.split("盘后", 1)[1]
    assert "+0.02%" not in block.split("盘后", 1)[0]
    stocks = _get(pages, "/stocks").text
    amat = _cells(_row(stocks, "AMAT"))
    assert "−8.00%" in amat[1]
    assert "+5.00%" not in amat[1]
    nvda = _cells(_row(stocks, "NVDA"))
    assert "−4.40%" in nvda[1]
    assert "+5.00%" not in nvda[1]


def test_f2_visible_text_has_no_basket_codes(pages):
    stocks, etfs = _universe()
    allowed = {row["ticker"].lower() for row in stocks}
    allowed.update(item.lower() for item in etfs)
    allowed.update({"xlp", "kre", "xlu", "xlv", "xle", "xlf", "xli", "xlk", "xly", "xlc", "smh", "soxx", "igv"})
    pages_html = {path: _get(pages, path).text for path in ("/", "/stocks", "/account", "/trust")}
    for path, html in pages_html.items():
        leaked = [token for token in _LOWER.findall(_visible(html)) if token not in allowed]
        assert leaked == [], path
    events = pages_html["/"].split("今天的大事", 1)[1].split("<footer", 1)[0]
    assert "iwm_qqq" not in events
    assert "mtum_vlue" not in events
    assert "rsp_spy" not in events
    assert "小盘相对纳指" not in events
    assert "必需消费 XLP" in pages_html["/"]
    assert "semi_equipment" not in _visible(pages_html["/"])


def test_f3_event_titles_use_covering_theme(pages):
    market = _json(pages, "/api/pages/brief/market")
    titles = [row["title"] for row in market["events"]]
    assert "AI 产业链 23 只同日下跌" in titles
    assert "半导体设备 4 只集体下跌" in titles
    assert all("iwm_qqq" not in title for title in titles)
    assert len(CHAIN) == 23


def test_f4_visible_numbers_follow_the_mockup(pages):
    account = _get(pages, "/account").text
    stocks = _get(pages, "/stocks").text
    market = _get(pages, "/").text
    visible = "\n".join(_visible(html) for html in (market, stocks, account, _get(pages, "/trust").text))
    assert "$1,462,351" in account
    assert "$125,598" in account
    assert "−1.18%" in market and "+0.07%" in market and "−2.86%" in market
    assert "1.8倍" in stocks
    assert "1.8×" in _row(stocks, "AMAT")
    nvda = _cells(_row(stocks, "NVDA"))
    assert nvda[3] == "44"
    assert "44.4" not in visible
    assert "22.8" in account
    assert "22.84" not in visible
    assert "73.6842" not in visible
    assert "$80.55" in account
    assert "$367" in account
    assert _LONG_DECIMAL.search(visible) is None
    card = next(row for row in _json(pages, "/api/pages/brief/account")["holdings"] if row["ticker"] == "NVDA")
    assert card["valuation"]["pe"] == pytest.approx(22.84)
    amat = next(
        row
        for theme in _json(pages, "/api/pages/brief/stocks")["themes"]
        if theme["sector"] == "半导体设备"
        for row in theme["members"]
        if row["ticker"] == "AMAT"
    )
    assert amat["volume_multiple"] == pytest.approx(1.84)


def test_f5_theme_lines_cover_four_cases(pages):
    stocks = _json(pages, "/api/pages/brief/stocks")
    html = _get(pages, "/stocks").text
    lines = {row["sector"]: row["line"] for row in stocks["themes"]}
    assert lines["半导体设备"] == "被集中抛售，放量；RSI 均值 20，已超卖"
    assert lines["互联网"] == "跟随下跌"
    assert lines["医疗"] == "资金流入，走强"
    assert lines["能源"] == "平稳"
    assert lines["半导体设备"] in html


def test_f6_next_step_is_plain_chinese(pages):
    account = _json(pages, "/api/pages/brief/account")
    html = _get(pages, "/account").text
    steps = {row["ticker"]: row["next_step"] for row in account["holdings"]}
    assert steps["NVDA"] == f"待成交：确认加仓（{PREV.isoformat()} 起）"
    assert steps["AAPL"] == "该档买入额度已满，暂不加仓"
    assert steps["MSFT"] == "卖出后冷却期，暂不加仓"
    assert _RULE.search(html) is None
    assert _RULE.search(_visible(html)) is None
    assert "待成交：确认加仓" in html
    assert "该档买入额度已满，暂不加仓" in html
    nvda = next(row for row in account["holdings"] if row["ticker"] == "NVDA")
    assert len(nvda["pending"]) == 2


def test_f7_unvalued_reasons_are_short_chinese(pages):
    html = _get(pages, "/stocks").text + _get(pages, "/account").text
    visible = _visible(html)
    for phrase in ("缺少每股收益数据", "周期股行业参数缺失", "亏损且无增长", "金融股不适用", "估值方法异常"):
        assert phrase in visible
    assert "book_value" not in visible
    assert "annual_eps_reason" not in visible
    assert "三档已升序重排" not in visible
    assert ";" not in visible
    for raw in UNVALUED.values():
        assert raw not in visible


def test_f8_pending_count_nav_and_buyable_cell(pages):
    account = _json(pages, "/api/pages/brief/account")
    counted = int(re.search(r"待成交(\d+)笔", account["oneliner"]).group(1))
    marked = [row for row in account["holdings"] if str(row["next_step"]).startswith("待成交")]
    assert counted == len(marked) == 1
    assert sum(len(row["pending"]) for row in account["holdings"]) == 2
    for path in ("/", "/stocks", "/account", "/trust"):
        page = _get(pages, path).text
        nav = page.split("<nav>", 1)[1].split("</nav>", 1)[0]
        assert "暂缺" not in nav
        assert "59 只各自怎样" in nav
        assert "大环境怎么样" in nav and "仓位怎么处理" in nav and "系统靠不靠谱" in nav
    stocks = _get(pages, "/stocks").text
    held = _cells(_row(stocks, "NVDA"))
    assert held[6] == "持有" and held[7] == ""
    buyable = _cells(_row(stocks, "LITE"))
    assert buyable[6] == "未持有" and buyable[7] == "可买"
    assert "可买" not in held[7]


def test_f9_vix_and_holdings_clause(pages):
    market = _json(pages, "/api/pages/brief/market")
    html = _get(pages, "/").text
    assert market["vix"] == pytest.approx(18.72)
    assert "18.72" in html
    stocks, _etfs = _universe()
    ai = [row["ticker"] for row in stocks if row["sector"] in AI_SECTORS]
    assert len(ai) >= len(stocks) / 3
    weight = int(half_up(SHARES * NVDA_PRICE / EQUITY * 100, 0))
    assert f"纸面账户 AI 持仓占 {weight}%" in market["implication"]
    assert "我的标的池偏重 AI 链" in market["implication"]
    assert "持仓" in market["implication"]
    text = []
    for path, title in (("/", "市场总览"), ("/stocks", "我的标的"), ("/account", "纸面账户"), ("/trust", "复盘与数据")):
        text.append(f"## {title}\n{_visible(_get(pages, path).text)}")
    Path("/tmp/b054-digest.txt").write_text("\n\n".join(text), encoding="utf-8")
