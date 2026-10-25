"""B-061: holding levels follow the rule A exits that actually apply."""

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
from inves_cog.trading.execution.state import clamp
from inves_cog.web import brief
from inves_cog.web.brief import sell_params, swing_params
from inves_cog.web.exit_levels import (
    PRICE_RED,
    SCORE_RED,
    build_levels,
    holding_kind,
    price_band,
    score_band,
)
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2041, 3, 18)
while not trading_day(DAY):
    DAY += timedelta(days=1)
CLOCK = FrozenClock(cutoff(DAY) + timedelta(hours=1))
SEEN = cutoff(DAY) - timedelta(hours=1)
PORTFOLIO = "b061-paper"
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_LONG = re.compile(r"\d+\.\d{4,}")
_RULE = re.compile(r"M-\d+")
_FORBIDDEN = ("破位", "灾难", "持有不足 10 个交易日")


def _sell():
    return sell_params("p-2026.10")


def _swing():
    return swing_params("p-2026.10")


def _names(position, score, price, **extra):
    rows = build_levels(position, score, _sell(), _swing(), price=price, index=100, panic=False)
    return [row["name"] for row in rows], rows


def test_e1_kind_follows_swing_and_tier():
    assert holding_kind({"swing_only": True, "tier_now": "defense"}) == "观察波段仓"
    assert holding_kind({"swing_only": False, "tier_now": "attack"}) == "进攻层核心"
    assert holding_kind({"tier_now": "normal"}) == "标准层核心"
    assert holding_kind({"tier_now": "defense"}) == "防守层核心"
    assert holding_kind({"tier_now": None}) == "类型暂缺"


def test_e2_each_type_lists_only_its_rules():
    tech = {"vol20": 40, "dev50": 0, "price_vs_ma200": -1}
    books = {"quality": 80, "growth": 80, "timing": 60}
    score = {"tech": tech, "books": books, "consec_below200": 1}
    swing_names, _rows = _names({"swing_only": True, "tier_now": "defense", "avg_cost": 80}, score, 100)
    assert swing_names == ["波段止盈价", "波段止损价"]
    attack_names, _rows = _names(
        {"tier_now": "attack", "avg_cost": 80, "peak_price": 100, "stage": 0, "swing_shares": 0},
        score,
        100,
    )
    assert attack_names == ["灾难止损价", "翻倍止盈价", "破位减仓", "基本面清仓"]
    normal_names, _rows = _names(
        {"tier_now": "normal", "avg_cost": 80, "peak_price": 100, "stage": 0, "swing_shares": 4},
        score,
        100,
    )
    assert normal_names == ["破位减仓", "警戒减仓", "基本面清仓", "波段部分止盈价"]
    defense_names, _rows = _names(
        {"tier_now": "defense", "avg_cost": 80, "peak_price": 100, "stage": 0, "swing_shares": 0},
        score,
        100,
    )
    assert defense_names == ["破位减仓", "基本面清仓"]


def test_e3_prices_follow_the_parameter_file(tmp_path, monkeypatch):
    sell, swing = _sell(), _swing()
    score = {"tech": {"vol20": 40, "dev50": 0}, "consec_below200": 0}
    position = {"swing_only": True, "tier_now": "defense", "avg_cost": 80, "peak_price": 100}
    rows = build_levels(position, score, sell, swing, price=100, index=100, panic=False)
    threshold = clamp(40, swing["take_profit"])
    assert threshold == 12.8
    assert rows[0]["trigger"] == pytest.approx(100 * (1 + threshold / 100))
    assert rows[1]["trigger"] == pytest.approx(80 * swing["stop_fraction"])
    attack = {"tier_now": "attack", "avg_cost": 90, "peak_price": 220, "stage": 0}
    priced = build_levels(
        attack,
        {"tech": {"price_vs_ma200": 1}, "books": {}, "consec_below200": 0},
        sell,
        swing,
        price=200,
        index=100,
        panic=False,
    )
    assert priced[0]["trigger"] == pytest.approx(220 * sell["disaster_peak_fraction"])
    assert priced[1]["trigger"] == pytest.approx(90 * sell["double_price"])
    folder = tmp_path / "p-2026.10"
    folder.mkdir()
    text = (ROOT / "config/params/p-2026.10/m4.yaml").read_text()
    text = text.replace("stop_fraction: 0.82\n", "stop_fraction: 0.70\n", 1)
    text = text.replace("take_profit: [0.32, 8, 14]\n", "take_profit: [1, 8, 14]\n", 1)
    text = text.replace("disaster_peak_fraction: 0.60\n", "disaster_peak_fraction: 0.50\n", 1)
    (folder / "m4.yaml").write_text(text)
    monkeypatch.setattr(brief, "PARAMS_ROOT", tmp_path)
    changed_sell, changed_swing = sell_params("p-2026.10"), swing_params("p-2026.10")
    moved = build_levels(position, score, changed_sell, changed_swing, price=100, index=100, panic=False)
    assert moved[1]["trigger"] == pytest.approx(56)
    assert moved[0]["trigger"] == pytest.approx(114)
    original = yaml.safe_load((ROOT / "config/params/p-2026.10/m4.yaml").read_text())
    assert original["m4"]["swing"]["stop_fraction"] == 0.82


def test_e4_double_alert_and_disaster_notes():
    sell, swing = _sell(), _swing()
    amd = {
        "tier_now": "attack",
        "stage": 0,
        "avg_cost": 90,
        "peak_price": 220,
        "last_sell_index": 70,
        "swing_shares": 0,
    }
    score = {
        "books": {"quality": 80, "growth": 80, "timing": 40},
        "tech": {"dev50": 10, "price_vs_ma200": 2},
        "consec_below200": 2,
    }
    rows = build_levels(amd, score, sell, swing, price=200, index=100, panic=False)
    double = next(row for row in rows if row["name"] == "翻倍止盈价")
    assert "距 50 日线当前 10" in double["text"]
    assert "择时分当前 40" in double["text"]
    assert "距上次卖出 30 天" in double["text"]
    assert "尚未减仓，满足" in double["text"]
    assert "附加条件当前满足" in double["text"]
    assert double["risk_level"] == "red"
    stored = dict(amd)
    build_levels(amd, score, sell, swing, price=200, index=100, panic=False)
    assert amd == stored
    avgo = build_levels(
        {"tier_now": "attack", "stage": 2, "avg_cost": 80, "peak_price": 100, "last_sell_index": 0},
        {"books": {"timing": 70}, "tech": {"dev50": 1, "price_vs_ma200": -4}, "consec_below200": 10},
        sell,
        swing,
        price=100,
        index=100,
        panic=False,
    )
    disaster = next(row for row in avgo if row["name"] == "灾难止损价")
    assert "同时需低于 200 日线，当前低于 200 日线" in disaster["text"]
    broken = next(row for row in avgo if row["name"] == "破位减仓")
    assert "已经执行过，不再重复" in broken["text"]
    weak = build_levels(
        {"tier_now": "defense", "stage": 0, "avg_cost": 80, "peak_price": 100, "entry_index": 0},
        {"books": {"quality": 40, "growth": 80}, "tech": {}, "consec_below200": 0},
        sell,
        swing,
        price=100,
        index=100,
        panic=False,
    )
    death = next(row for row in weak if row["name"] == "基本面清仓")
    assert "质量分 40 < 50" in death["text"] and death["text"].endswith("已触发")
    assert death["risk_level"] == "red"
    jnj = {
        "tier_now": "normal",
        "stage": 0,
        "entry_state": "a",
        "avg_cost": 80,
        "peak_price": 110,
        "swing_shares": 0,
    }
    alert_score = {
        "books": {"quality": 70, "growth": 41.5, "timing": 60},
        "tech": {"dev50": -3},
        "state_version": "b",
        "consec_below200": 0,
    }
    alert = next(
        row
        for row in build_levels(jnj, alert_score, sell, swing, price=100, index=100, panic=False)
        if row["name"] == "警戒减仓"
    )
    assert "成长分 41.5 < 50" in alert["text"]
    assert "距 50 日线为负" in alert["text"]
    assert alert["text"].endswith("已触发")
    assert alert["risk_level"] == "red"
    paused = next(
        row
        for row in build_levels(jnj, alert_score, sell, swing, price=100, index=100, panic=True)
        if row["name"] == "警戒减仓"
    )
    assert "恐慌模式下暂停警戒减仓" in paused["text"]
    assert "已触发" not in paused["text"]


def test_e5_distance_bands():
    assert price_band(PRICE_RED - 0.001) == "red"
    assert price_band(PRICE_RED) == "orange"
    assert price_band(0.20 - 0.001) == "orange"
    assert price_band(0.20) is None
    assert score_band(SCORE_RED - 0.1) == "red"
    assert score_band(SCORE_RED) == "orange"
    assert score_band(10 - 0.1) == "orange"
    assert score_band(10) is None


def _visible(html):
    return unescape(_TAG.sub(" ", _STYLE.sub(" ", html)))


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b061_web') THEN "
        "CREATE ROLE b061_web LOGIN; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b061_web")


def _clear(admin):
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b061'")
    admin.execute("DELETE FROM marketstate.daily WHERE factor_set = 'b061'")
    admin.execute("DELETE FROM marketstate.market WHERE trade_date = %s", (DAY,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))


def _position(spec):
    return {
        "shares": 100,
        "avg_cost": spec["cost"],
        "peak_price": spec.get("peak", spec["price"]),
        "tier_now": spec["tier"],
        "stage": spec.get("stage", 0),
        "entry_index": 0,
        "entry_state": spec.get("entry_state", "a"),
        "last_sell_index": spec.get("last", 0),
        "swing_only": spec.get("swing", False),
        "swing_shares": spec.get("swing_shares", 0),
    }


def _score(spec):
    return {
        "consec_below200": spec.get("days", 0),
        "state_version": spec.get("version", "a"),
        "books": {
            "quality": spec.get("quality", 80),
            "growth": spec.get("growth", 80),
            "timing": spec.get("timing", 60),
        },
        "tech": {
            "price": spec["price"],
            "vol20": spec.get("vol", 20),
            "dev50": spec.get("dev", 0),
            "price_vs_ma200": spec.get("ma", 1),
        },
    }


HOLDINGS = {
    "HD": {"swing": True, "tier": "defense", "price": 100, "cost": 80, "vol": 40, "dev": 0, "days": 4},
    "NFLX": {"swing": True, "tier": "normal", "price": 100, "cost": 80, "vol": 40, "dev": 0, "days": 8},
    "AVGO": {
        "tier": "attack",
        "price": 100,
        "cost": 80,
        "peak": 100,
        "stage": 2,
        "days": 10,
        "dev": 1,
        "ma": -4,
        "timing": 70,
        "last": 0,
    },
    "MU": {"tier": "attack", "price": 100, "cost": 80, "peak": 140, "days": 2, "ma": -1},
    "MRVL": {"tier": "attack", "price": 110, "cost": 80, "peak": 150, "days": 1, "ma": 2},
    "AMD": {
        "tier": "attack",
        "price": 200,
        "cost": 90,
        "peak": 220,
        "days": 2,
        "dev": 10,
        "ma": 2,
        "timing": 40,
        "last": 70,
    },
    "GOOGL": {"tier": "normal", "price": 100, "cost": 80, "peak": 110, "days": 1, "dev": 2, "growth": 70},
    "JNJ": {
        "tier": "normal",
        "price": 100,
        "cost": 80,
        "peak": 110,
        "days": 0,
        "dev": -3,
        "growth": 41.5,
        "quality": 70,
        "version": "b",
    },
    "V": {"tier": "defense", "price": 100, "cost": 80, "peak": 110, "days": 2, "growth": 60},
}


def _seed(admin):
    _clear(admin)
    positions = {}
    scores = {}
    for ticker, spec in HOLDINGS.items():
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, %s, 1000, 'b061')
            """,
            (ticker, DAY, spec["price"]),
        )
        admin.execute(
            """
            INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
            VALUES (%s, %s, 'close', 0, 'b061', '{}')
            """,
            (DAY, ticker),
        )
        positions[ticker] = _position(spec)
        scores[ticker] = _score(spec)
    equity = 1_101_000
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
            equity,
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
    bundle = {"admin": admin, "dsn": f"postgresql://b061_web@{host}/inves_cog"}
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


def test_e1_pages_show_the_holding_type(pages):
    holdings = {row["ticker"]: row for row in _account(pages)["holdings"]}
    assert holdings["HD"]["kind_label"] == "观察波段仓"
    assert holdings["NFLX"]["kind_label"] == "观察波段仓"
    assert holdings["AVGO"]["kind_label"] == "进攻层核心"
    assert holdings["JNJ"]["kind_label"] == "标准层核心"
    assert holdings["V"]["kind_label"] == "防守层核心"


def _take(payload, ticker):
    return next(row for row in payload["take_profits"] if row.get("ticker") == ticker)


def test_e5_swing_pages_skip_breakout_and_disaster(pages):
    account = _account(pages)
    for ticker in ("HD", "NFLX"):
        text = _take(account, ticker)["text"]
        for word in _FORBIDDEN:
            assert word not in text
        assert "波段止盈价还需上涨 12.8%" in text
    hd = _visible(_get(pages, "/s/HD").text)
    assert "观察波段仓" in hd
    body = hd.split("观察波段仓只看", 1)[0]
    for word in ("破位减仓", "灾难止损", "持有不足 10 个交易日"):
        assert word not in body


def test_e4_pages_quote_avgo_and_jnj(pages):
    account = _account(pages)
    jnj = next(row for row in account["holdings"] if row["ticker"] == "JNJ")
    alert = next(row for row in jnj["levels"] if row["name"] == "警戒减仓")
    assert "成长分 41.5 < 50" in alert["text"]
    assert "距 50 日线为负" in alert["text"] and alert["text"].endswith("已触发")
    avgo = _visible(_get(pages, "/s/AVGO").text)
    assert "进攻层核心" in avgo
    assert "同时需低于 200 日线，当前低于 200 日线" in avgo
    assert "已连续 10 天低于 200 日线；规则 A 已执行破位减仓，不再重复减仓" in avgo
    assert "附加条件当前未满足" in avgo


def test_e6_distance_wording_and_footer(pages):
    blob = _visible(_get(pages, "/account").text + _get(pages, "/s/HD").text + _get(pages, "/s/AVGO").text)
    assert "还需上涨 12.8%" in blob
    assert "还需下跌" in blob
    assert "观察波段仓只看波段止盈价" in blob
    assert "参数来自当前版本的卖出参数与波段参数" in blob
    assert not _LOWER.search(blob)
    assert not _LONG.search(blob)
    assert not _RULE.search(blob)
    assert "止盈线距离" not in blob and "−113" not in blob


def test_e3_page_follows_a_replaced_parameter_file(pages, tmp_path, monkeypatch):
    folder = tmp_path / "p-2026.10"
    folder.mkdir()
    text = (ROOT / "config/params/p-2026.10/m4.yaml").read_text()
    text = text.replace("stop_fraction: 0.82\n", "stop_fraction: 0.70\n", 1)
    text = text.replace(
        "below_days: {defense: 10, normal: 3, attack: 7}",
        "below_days: {defense: 10, normal: 3, attack: 12}",
        1,
    )
    (folder / "m4.yaml").write_text(text)
    monkeypatch.setattr(brief, "PARAMS_ROOT", tmp_path)
    holdings = {row["ticker"]: row for row in _account(pages)["holdings"]}
    stop = next(row for row in holdings["HD"]["levels"] if row["name"] == "波段止损价")
    assert stop["trigger"] == pytest.approx(56)
    days = next(row for row in holdings["AVGO"]["levels"] if row["name"] == "破位减仓")
    assert days["trigger"] == 12
