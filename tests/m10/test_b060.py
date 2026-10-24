"""B-060: 200-day copy follows the ledger score, and distances drop the plus sign."""

import re
from datetime import date, timedelta
from html import unescape

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.brief import sell_params
from inves_cog.web.public import create_app
from inves_cog.web.risk_brief import below_clause, format_plain_percent

pytestmark = pytest.mark.phase1_blocking

DAY = date(2040, 2, 16)
while not trading_day(DAY):
    DAY += timedelta(days=1)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
SEEN = cutoff(DAY) - timedelta(hours=1)
PORTFOLIO = "b060-paper"
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG = re.compile(r"\d+\.\d{4,}")
_CONTRA = re.compile(r"已连续 (\d+) 天低于 200 日线[^。]*第 (\d+) 天")
_PLUS = re.compile(r"\+\d")
HOLDINGS = {
    "NFLX": {"tier": "normal", "days": 130, "stage": 2, "entry": 0, "ret": -0.063},
    "HD": {"tier": "defense", "days": 50, "stage": 2, "entry": 0},
    "AVGO": {"tier": "attack", "days": 10, "stage": 0, "entry": 0},
    "GOOGL": {"tier": "normal", "days": 2, "stage": 0, "entry": 0},
    "INTC": {"tier": "normal", "days": 3, "stage": 0, "entry": 95},
}


def _visible(html):
    return unescape(_TAG.sub(" ", _STYLE.sub(" ", html)))


def test_f2_four_copies_and_plain_percents():
    sell = sell_params("p-2026.10")
    below = sell["below_days"]
    fraction = sell["broken_fraction"]
    age = sell["minimum_age"]
    done = below_clause(130, below["normal"], 2, 40, age, False, fraction["normal"])
    assert done == ("orange", "已连续 130 天低于 200 日线；规则 A 已执行破位减仓，不再重复减仓")
    ready = below_clause(10, below["attack"], 0, age, age, False, fraction["attack"])
    assert ready[0] == "red"
    assert ready[1].endswith(f"下一次计划将减仓 {format_plain_percent(fraction['attack'])}")
    assert format_plain_percent(fraction["attack"]) == "33.3%"
    young = below_clause(3, below["normal"], 0, 5, age, False, fraction["normal"])
    assert young == ("orange", f"已连续 3 天低于 200 日线，持有不足 {int(age)} 个交易日，暂不减仓")
    paused = below_clause(10, below["attack"], 0, 40, age, True, fraction["attack"])
    assert paused == ("orange", "已连续 10 天低于 200 日线，恐慌模式下暂停破位减仓")
    early = below_clause(2, below["normal"], 0, 40, age, False, fraction["normal"])
    assert early == ("red", "已连续 2 天低于 200 日线，规则 A 在第 3 天触发减仓")
    assert format_plain_percent(0.1061) == "10.6%"
    assert format_plain_percent(0.2023) == "20.2%"
    assert format_plain_percent(-0.02) == "2.0%"
    assert "+" not in format_plain_percent(0.1061)


def test_f1_source_does_not_count_bars():
    from pathlib import Path

    text = Path("src/inves_cog/web/risk_brief.py").read_text()
    assert "consecutive_below_ma200" not in text
    assert "bars_daily" not in text


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b060_web') THEN "
        "CREATE ROLE b060_web LOGIN; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b060_web")


def _clear(admin):
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b060'")
    admin.execute("DELETE FROM marketstate.daily WHERE factor_set = 'b060'")
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))


def _seed(admin):
    _clear(admin)
    positions = {}
    scores = {}
    for ticker, spec in HOLDINGS.items():
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, 100, 1000, 'b060')
            """,
            (ticker, DAY),
        )
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
            VALUES (%s, %s, 'close', %s, 'b060', '{}')
            """,
            (DAY, ticker, spec.get("ret", 0.0)),
        )
        positions[ticker] = {
            "shares": 100,
            "avg_cost": 80,
            "peak_price": 100,
            "tier_now": spec["tier"],
            "stage": spec["stage"],
            "entry_index": spec["entry"],
        }
        scores[ticker] = {"consec_below200": spec["days"]}
    equity = 1_050_000
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 1000000, %s, %s, %s, %s)
        """,
        (
            PORTFOLIO,
            DAY,
            equity,
            equity / 0.967,
            Jsonb({"positions": positions, "scores": scores, "index": 100, "panic": False}),
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
    bundle = {"admin": admin, "dsn": f"postgresql://b060_web@{host}/inves_cog"}
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


def test_f1_page_uses_the_ledger_score_not_the_bars(pages):
    nflx = _line(_account(pages), "NFLX")
    assert nflx["level"] == "orange"
    assert "已连续 130 天低于 200 日线" in nflx["text"]
    assert "235" not in nflx["text"]
    assert "第 3 天" not in nflx["text"]


def test_f3_visible_copy_is_not_self_contradictory(pages):
    visible = _visible(_get(pages, "/account").text)
    matches = _CONTRA.findall(visible)
    assert matches
    assert all(int(days) < int(rule) for days, rule in matches)


def test_f4_signs_and_one_decimal(pages):
    account = _account(pages)
    nflx = _line(account, "NFLX")["text"]
    assert "今日 −6.30%" in nflx
    avgo = _line(account, "AVGO")["text"]
    assert avgo.endswith("下一次计划将减仓 33.3%。")
    assert _PLUS.search(avgo) is None
    html = _visible(_get(pages, "/account").text)
    assert "现金比例 95.2%" in html
    assert "现金比例 +" not in html
    assert not _LONG.search(html)
    card = html.split("组合风险", 1)[1].split("持仓与关键价位", 1)[0]
    assert _PLUS.search(card) is None


def test_f5_three_pages(pages):
    account = _account(pages)
    assert _line(account, "AVGO")["level"] == "red"
    assert _line(account, "GOOGL")["text"] == "GOOGL 已连续 2 天低于 200 日线，规则 A 在第 3 天触发减仓。"
    assert _line(account, "HD")["text"].startswith("HD 已连续 50 天低于 200 日线；规则 A 已执行破位减仓")
    assert _line(account, "INTC")["text"].endswith("持有不足 10 个交易日，暂不减仓。")
    market = _get(pages, "/").text
    assert "红色 2 项，橙色 3 项" in market
    assert "第一条红色：AVGO 已连续 10 天低于 200 日线，达到规则 A 破位减仓条件" in market
    stock = _visible(_get(pages, "/s/NFLX").text)
    assert "已连续 130 天低于 200 日线；规则 A 已执行破位减仓，不再重复减仓" in stock
    assert "我的仓位" in stock
    blob = _visible(market + _get(pages, "/account").text + _get(pages, "/s/NFLX").text)
    assert not _LOWER.search(blob)


def test_f2_panic_follows_the_ledger_flag(pages):
    admin = pages["admin"]
    row = admin.execute("SELECT state FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,)).fetchone()
    state = row["state"]
    state["panic"] = True
    try:
        admin.execute(
            "UPDATE trading.ledger SET state = %s WHERE portfolio_id = %s",
            (Jsonb(state), PORTFOLIO),
        )
        avgo = _line(_account(pages), "AVGO")
        assert avgo["level"] == "orange"
        assert avgo["text"].endswith("恐慌模式下暂停破位减仓。")
    finally:
        state["panic"] = False
        admin.execute(
            "UPDATE trading.ledger SET state = %s WHERE portfolio_id = %s",
            (Jsonb(state), PORTFOLIO),
        )
