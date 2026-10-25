"""B-059 holding-risk highlights on the account, market, and stock pages."""

import re
from datetime import date, timedelta
from html import unescape

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.brief import format_fraction, sell_params
from inves_cog.web.public import create_app
from inves_cog.web.risk_brief import (
    DAY_DROP,
    DD_APPROACH_POINTS,
    DISASTER_ORANGE,
    DISASTER_RED,
    THEME_ORANGE,
    THEME_RED,
    day_level,
    disaster_level,
    drawdown_level,
    format_plain_percent,
    gate_gaps,
    ma_level,
    risk_params,
    theme_level,
)

pytestmark = pytest.mark.phase1_blocking

DAY = date(2039, 8, 16)
while not trading_day(DAY):
    DAY += timedelta(days=1)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
SEEN = cutoff(DAY) - timedelta(hours=1)
LATE = cutoff(DAY) + timedelta(hours=2)
PORTFOLIO = "b059-paper"
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG = re.compile(r"\d+\.\d{4,}")
_RULE = re.compile(r"M-\d+")
HOLDINGS = {
    "NVDA": {"shares": 500, "tier": "normal"},
    "AMD": {"shares": 500, "tier": "normal"},
    "AVGO": {"shares": 500, "tier": "normal"},
    "MRVL": {"shares": 1100, "tier": "normal", "gap": 0.18},
    "MU": {"shares": 100, "tier": "normal", "gap": 0.098, "ret": -0.063},
    "GOOGL": {"shares": 100, "tier": "normal", "close": 99, "streak": 2},
    "HD": {"shares": 100, "tier": "defense", "close": 99, "streak": 1},
    "INTC": {"shares": 100, "tier": "normal", "cooling": True},
    "MSFT": {"shares": 1200, "tier": "normal"},
    "AAPL": {"shares": 1200, "tier": "normal"},
    "JPM": {"shares": 1200, "tier": "normal"},
    "XOM": {"shares": 1200, "tier": "normal"},
    "COST": {"shares": 1202, "tier": "normal"},
}


def _sessions(day, count):
    found = []
    cursor = day
    while len(found) < count:
        if trading_day(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
    found.reverse()
    return found


def _visible(html):
    return unescape(_TAG.sub(" ", _STYLE.sub(" ", html)))


def _peak(price, gap):
    return price * (1 - gap) / 0.60


def test_k1_disaster_edges():
    assert disaster_level(DISASTER_RED - 0.001) == "red"
    assert disaster_level(DISASTER_RED) == "orange"
    assert disaster_level(DISASTER_ORANGE - 0.001) == "orange"
    assert disaster_level(DISASTER_ORANGE) is None
    assert disaster_level(-0.01) == "red"


def test_k4_theme_and_drop_edges():
    assert theme_level(THEME_ORANGE) is None
    assert theme_level(THEME_ORANGE + 0.0001) == "orange"
    assert theme_level(THEME_RED) == "orange"
    assert theme_level(THEME_RED + 0.0001) == "red"
    assert day_level(DAY_DROP) == "orange"
    assert day_level(DAY_DROP + 0.001) is None


def test_k2_streak_and_k5_drawdown_edges():
    assert ma_level(2, 3) == "red"
    assert ma_level(1, 10) == "orange"
    assert ma_level(0, 3) is None
    risk = risk_params("p-2026.10")
    assert drawdown_level(-0.033, risk["dd8_trigger"]) is None
    assert drawdown_level(-0.07, risk["dd8_trigger"]) == "orange"
    assert drawdown_level(-0.085, risk["dd8_trigger"]) == "red"
    assert drawdown_level(risk["dd8_trigger"] / 100, risk["dd8_trigger"]) == "red"


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b059_web') THEN "
        "CREATE ROLE b059_web LOGIN; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b059_web")


def _clear(admin):
    admin.execute("DELETE FROM perception.ticker_status WHERE anomaly_id = 'b059-ai'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id = 'b059-ai'")
    admin.execute("DELETE FROM graph.baskets WHERE basket_id = 'b059-ai'")
    admin.execute("DELETE FROM overlay.versions WHERE payload->>'tag' = 'b059'")
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b059'")
    admin.execute("DELETE FROM marketstate.daily WHERE factor_set = 'b059'")
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))


def _bars(admin, ticker, closes):
    days = _sessions(DAY, len(closes))
    with admin.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, %s, 1000, 'b059')
            """,
            [(ticker, day, close) for day, close in zip(days, closes, strict=True)],
        )


def _seed(admin):
    _clear(admin)
    positions = {}
    for ticker, spec in HOLDINGS.items():
        close = spec.get("close", 100)
        closes = [close, close]
        _bars(admin, ticker, closes)
        price = closes[-1]
        gap = spec.get("gap")
        peak = price if gap is None else _peak(price, gap)
        positions[ticker] = {
            "shares": spec["shares"],
            "avg_cost": 80,
            "peak_price": peak,
            "tier_now": spec["tier"],
            "stage": 0,
            "entry_index": 0,
        }
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
            VALUES (%s, %s, 'close', %s, 'b059', '{}')
            """,
            (DAY, ticker, spec.get("ret", 0.0)),
        )
    equity = 1_000_000
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 100000, %s, %s, %s, %s)
        """,
        (
            PORTFOLIO,
            DAY,
            equity,
            equity / 0.967,
            Jsonb(
                {
                    "positions": positions,
                    "index": 40,
                    "panic": False,
                    "scores": {
                        ticker: {"consec_below200": spec["streak"]}
                        for ticker, spec in HOLDINGS.items()
                        if spec.get("streak")
                    },
                }
            ),
            SEEN,
        ),
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
        INSERT INTO graph.baskets (basket_id, level, name, benchmark, members, factor_basis)
        VALUES ('b059-ai', 'L2', 'AI 产业链', 'SMH', %s, '{}')
        """,
        (Jsonb([{"ticker": "MU"}, {"ticker": "AMD"}]),),
    )
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
            direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
            status, universe, params_version, generated_at
        ) VALUES (
            'b059-ai', %s, 'close', ARRAY['A'], 'L3', 'alert', ARRAY['b059-ai'], %s,
            'down', 4.2, '{}', '{}', '{}', ARRAY[]::text[],
            '已发现·原因未明', 'pool', 'b059', %s
        )
        """,
        (DAY, Jsonb([{"ticker": "MU"}, {"ticker": "AMD"}]), SEEN),
    )
    admin.execute(
        """
        INSERT INTO perception.ticker_status (anomaly_id, ticker, exposure, n_code)
        VALUES ('b059-ai', 'MU', '直接', 'N1'), ('b059-ai', 'AMD', '间接', 'N2')
        """
    )
    cooling = {"tickers": {"INTC": {"cooling_off": True, "cooling_status": "on"}}, "tag": "b059"}
    future = {"tickers": {"COST": {"cooling_off": True, "cooling_status": "on"}}, "tag": "b059"}
    admin.execute(
        """
        INSERT INTO overlay.versions (date, generated_at, source_events_asof, params_version, payload, published)
        VALUES (%s, %s, %s, 'p-2026.10', %s, true)
        """,
        (DAY, SEEN, SEEN, Jsonb(cooling)),
    )
    admin.execute(
        """
        INSERT INTO overlay.versions (date, generated_at, source_events_asof, params_version, payload, published)
        VALUES (%s, %s, %s, 'p-2026.10', %s, true)
        """,
        (DAY, LATE, LATE, Jsonb(future)),
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
    bundle = {"admin": admin, "dsn": f"postgresql://b059_web@{host}/inves_cog"}
    yield bundle
    _clear(admin)
    admin.close()


def _get(pages, path):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params={"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _account(pages):
    return _get(pages, "/api/pages/brief/account").json()


def _line(payload, ticker):
    return next(row for row in payload["risk_lines"] if row.get("ticker") == ticker)


def test_k6_pages_sort_color_and_plain_text(pages):
    account = _account(pages)
    levels = [(row["level"], row.get("ticker")) for row in account["risk_lines"]]
    assert levels[0] == ("red", "GOOGL")
    assert ("red", "MU") in levels
    assert [row["level"] for row in account["risk_lines"]].index("orange") > levels.index(("red", "MU"))
    mu = _line(account, "MU")
    assert mu["level"] == "red"
    assert "灾难止损" not in mu["text"] and "距灾难" not in mu["text"]
    assert f"今日 {format_fraction(-0.063)}" in mu["text"]
    assert "卷入 AI 产业链下跌" in mu["text"]
    assert all(row.get("ticker") != "MRVL" for row in account["risk_lines"])
    assert _line(account, "GOOGL")["text"].startswith("GOOGL 已连续 2 天低于 200 日线，规则 A 在第 3 天触发减仓")
    assert _line(account, "HD")["level"] == "orange"
    assert "第 10 天" in _line(account, "HD")["text"]
    assert _line(account, "AMD")["level"] == "orange" and "卷入 AI 产业链下跌" in _line(account, "AMD")["text"]
    assert _line(account, "INTC")["text"].endswith("冷静期内不加仓。")
    assert all(row.get("ticker") != "COST" for row in account["risk_lines"])
    assert all(row.get("ticker") != "MSFT" for row in account["risk_lines"])
    theme = next(row for row in account["risk_lines"] if row["text"].startswith("AI 算力芯片"))
    assert theme["level"] == "orange" and "26.0%" in theme["text"]
    assert not any(row["text"].startswith("组合距峰值") for row in account["risk_lines"])
    card = account["risk_card"]
    assert card["themes"][0]["sector"] == "AI 算力芯片"
    assert card["themes"][0]["share"] == pytest.approx(0.26)
    assert card["themes"][1]["sector"] == "零售"
    assert card["holdings"] == 13 and card["slots"] == 12
    assert card["cash_ratio"] == pytest.approx(0.10)
    assert card["dd8_gap"] == gate_gaps(card["drawdown"], risk_params("p-2026.10"))["dd8"]
    html = _visible(_get(pages, "/account").text)
    assert "今天先看这些" in html and "组合边界" in html
    raw = _get(pages, "/account").text
    assert 'class="chip hi"' in raw and 'class="chip mid"' in raw
    share = card["themes"][0]["share"]
    width = max(0, min(100, float(share) / 0.40 * 100))
    assert f'style="width:{width:.1f}%"' in raw
    market = _get(pages, "/").text
    assert "对我意味着什么" in market and "红色 2 项，橙色 4 项" in market
    assert market.index("对我意味着什么") < market.index("红色 2 项")
    assert "第一条红色：" in market and "GOOGL 已连续 2 天" in market
    stock = _visible(_get(pages, "/s/MU").text)
    assert mu["text"] in stock and "我的仓位" in stock
    blob = _visible(_get(pages, "/").text + raw + _get(pages, "/s/MU").text)
    assert not _LOWER.search(blob)
    assert not _LONG.search(blob)
    assert not _RULE.search(blob)
    assert "N1" not in blob and "N2" not in blob


def test_k2_rule_days_follow_the_parameter_file(pages, monkeypatch):
    original = sell_params

    def wrapped(version):
        loaded = original(version)
        loaded["below_days"] = {**loaded["below_days"], "normal": 10}
        return loaded

    monkeypatch.setattr("inves_cog.web.brief.sell_params", wrapped)
    googl = _line(_account(pages), "GOOGL")
    assert googl["level"] == "orange"
    assert "第 10 天" in googl["text"]


def test_k5_drawdown_follows_the_parameter_file(pages, monkeypatch):
    admin = pages["admin"]
    original = admin.execute("SELECT peak_equity FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,)).fetchone()[
        "peak_equity"
    ]
    equity = 1_000_000
    try:
        admin.execute(
            "UPDATE trading.ledger SET peak_equity = %s WHERE portfolio_id = %s",
            (equity / 0.93, PORTFOLIO),
        )
        orange = next(row for row in _account(pages)["risk_lines"] if row["text"].startswith("组合距峰值"))
        assert orange["level"] == "orange" and "接近回撤刹车" in orange["text"]
        assert "已触发回撤刹车" not in orange["text"]
        admin.execute(
            "UPDATE trading.ledger SET peak_equity = %s WHERE portfolio_id = %s",
            (equity / 0.915, PORTFOLIO),
        )
        red = next(row for row in _account(pages)["risk_lines"] if row["text"].startswith("组合距峰值"))
        assert red["level"] == "red"
        assert "已触发回撤刹车" in red["text"] and "暂停非防守层新开仓" in red["text"]
        fraction = format_plain_percent(risk_params("p-2026.10")["dd8_sell_fraction"])
        assert fraction in red["text"]

        def shifted(version):
            loaded = risk_params(version)
            loaded["dd8_trigger"] = -10
            return loaded

        monkeypatch.setattr("inves_cog.web.risk_brief.risk_params", shifted)
        moved = next(row for row in _account(pages)["risk_lines"] if row["text"].startswith("组合距峰值"))
        assert moved["level"] == "orange" and "接近回撤刹车" in moved["text"]
        assert "已触发回撤刹车" not in moved["text"] and "−10.00%" in moved["text"]
    finally:
        admin.execute(
            "UPDATE trading.ledger SET peak_equity = %s WHERE portfolio_id = %s",
            (original, PORTFOLIO),
        )


def test_k7_formulas_stay_plain():
    from inves_cog.web.risk_brief import RISK_FORMULAS

    text = "\n".join(RISK_FORMULAS)
    assert not _LOWER.search(text)
    assert "不改规则 A 的订单" in text
    assert f"{DD_APPROACH_POINTS} 个百分点" in text
