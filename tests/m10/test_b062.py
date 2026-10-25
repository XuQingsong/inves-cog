"""B-062: investor pages follow the final prototype, including the fixed data rules."""

import re
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.public import create_app
from inves_cog.web.ruler import boxes_overlap, ruler

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2026, 10, 22)
NEXT = date(2026, 10, 23)
CLOCK = FrozenClock(cutoff(NEXT) + timedelta(hours=1))
SEEN = cutoff(DAY) - timedelta(hours=1)
PORTFOLIO = "b062-paper"
CASH = 125_598
PLAIN = "按现价反推的增速超出可解释范围"
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_LOWER = re.compile(r"[a-z_]+")
_RULE = re.compile(r"M-\d+")
JNJ_MA = (100 / 91.6 - 1) * 100
NFLX_COST = 0.875 / 0.82 * 100
ADBE_VOL = 11 / 0.32

HOLDINGS = {
    "GOOGL": {"tier": "normal", "price": 100, "cost": 80, "days": 2, "ma": -5, "dev": 2, "ret": 0},
    "JNJ": {
        "tier": "normal",
        "price": 100,
        "cost": 80,
        "days": 0,
        "ma": JNJ_MA,
        "dev": -3,
        "growth": 41.5,
        "quality": 70,
        "version": "b",
        "ret": 0,
    },
    "AVGO": {"tier": "attack", "price": 100, "cost": 80, "stage": 2, "days": 10, "ma": 5, "dev": 1, "ret": 0},
    "MRVL": {"tier": "attack", "price": 110, "cost": 90, "days": 0, "ma": 5, "ret": -0.06},
    "MU": {"tier": "attack", "price": 100, "cost": 80, "days": 0, "ma": 5, "ret": -0.06},
    "NFLX": {"swing": True, "tier": "normal", "price": 100, "cost": NFLX_COST, "vol": 40, "dev": -10, "ret": 0},
    "AMD": {
        "tier": "attack",
        "price": 120,
        "cost": 50,
        "days": 0,
        "dev": 10,
        "timing": 70,
        "last": 90,
        "ma": 5,
        "ret": -0.06,
    },
    "NVDA": {"tier": "attack", "price": 100, "cost": 80, "days": 0, "ma": 5, "ret": -0.06},
    "HD": {"swing": True, "tier": "defense", "price": 100, "cost": 80, "vol": 40, "dev": 0, "ret": None},
    "ADBE": {
        "tier": "normal",
        "price": 100,
        "cost": 80,
        "vol": ADBE_VOL,
        "swing_shares": 10,
        "days": 0,
        "dev": 0,
        "ret": 0,
    },
    "AAPL": {"tier": "normal", "price": 100, "cost": 80, "days": 0, "dev": 2, "ret": 0.01},
    "LLY": {"tier": "defense", "price": 100, "cost": 80, "days": 0, "dev": 2, "ret": 0.01},
    "V": {"tier": "defense", "price": 100, "cost": 80, "days": 0, "dev": 2, "ret": 0.01},
}


def _prior(day):
    cursor = day - timedelta(days=1)
    while not trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor


def _visible(html):
    return unescape(_TAG.sub(" ", _STYLE.sub(" ", html)))


def _position(spec):
    return {
        "shares": 100,
        "avg_cost": spec["cost"],
        "peak_price": spec.get("peak", spec["price"]),
        "tier_now": spec["tier"],
        "stage": spec.get("stage", 0),
        "entry_index": 0,
        "entry_state": "a",
        "last_sell_index": spec.get("last", 0),
        "swing_only": spec.get("swing", False),
        "swing_shares": spec.get("swing_shares", 0),
    }


def _ledger_score(spec):
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
            "price_vs_ma200": spec.get("ma", 5),
        },
    }


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b062_web') THEN "
        "CREATE ROLE b062_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b062_web")


def _clear(admin):
    admin.execute("DELETE FROM trading.orders WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute(
        "DELETE FROM trading.daily_scores WHERE signal_date = %s AND ticker = ANY(%s)", (DAY, ["LITE", "CRWD", "PANW"])
    )
    admin.execute("DELETE FROM valuation_v1.ranges WHERE trade_date = %s AND ticker = ANY(%s)", (DAY, ["CRWD", "PANW"]))
    admin.execute("DELETE FROM ingest.short_interest WHERE observation_id LIKE 'b062-%'")
    admin.execute("DELETE FROM ingest.bars_daily WHERE source = 'b062'")
    admin.execute("DELETE FROM marketstate.daily WHERE factor_set = 'b062'")


def _score_row(admin, ticker, tech, derived, entry):
    admin.execute(
        """
        INSERT INTO trading.daily_scores (
            signal_date, ticker, extractor, rule_set, params_version, tech, derived,
            quality, growth, valuation, timing, timing_subitems, rank_score, red_lines,
            tier, certainty, certainty_points, hold_score, hold_ok, fund_bad, runway_ok,
            m32_ok, gate_pass, entry_pass, consec_pass, tradable
        ) VALUES (
            %s, %s, 'fixed', 'A', 'p-2026.10', %s, %s,
            60, 60, 60, 60, '{}', 1, '{}',
            'normal', 'medium', 1, 50, true, false, true,
            true, true, %s, 1, true
        )
        """,
        (DAY, ticker, Jsonb(tech), Jsonb(derived), entry),
    )


def _range_row(admin, ticker, payload):
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (
            %s, %s, 'p-2026.10', 'v1', 'v1', 'base', 'ok',
            80, 100, 120, false, %s, %s
        )
        """,
        (DAY, ticker, Jsonb(payload), SEEN),
    )


def _short(admin, name, ticker, settlement, pct, raw):
    admin.execute(
        """
        INSERT INTO ingest.short_interest (
            observation_id, ticker, settlement_date, publish_date, short_interest,
            avg_daily_volume, days_to_cover, si_pct_shares_outstanding, source, raw
        ) VALUES (%s, %s, %s, NULL, 1000, 100, 1, %s, 'b062', %s)
        """,
        (f"b062-{name}", ticker, settlement, pct, Jsonb(raw)),
    )


def _seed(admin):
    _clear(admin)
    assert trading_day(DAY) and trading_day(NEXT)
    prior = _prior(DAY)
    positions = {}
    scores = {}
    for ticker, spec in HOLDINGS.items():
        admin.execute(
            """
            INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
            VALUES (%s, %s, %s, 1000, 'b062')
            """,
            (ticker, DAY, spec["price"]),
        )
        if spec["ret"] is not None:
            admin.execute(
                """
                INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
                VALUES (%s, %s, 'close', %s, 'b062', '{}')
                """,
                (DAY, ticker, spec["ret"]),
            )
        positions[ticker] = _position(spec)
        scores[ticker] = _ledger_score(spec)
    admin.execute(
        """
        INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)
        VALUES ('HD', %s, %s, 1000, 'b062')
        """,
        (prior, 100 / 0.98),
    )
    market = 100 * sum(spec["price"] for spec in HOLDINGS.values())
    equity = CASH + market
    peak = equity / (1 - 0.0365)
    admin.execute(
        """
        INSERT INTO trading.ledger (
            portfolio_id, trade_date, phase, extractor, rule_set, params_version,
            cash, equity, peak_equity, state, observed_at
        ) VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', %s, %s, %s, %s, %s)
        """,
        (
            PORTFOLIO,
            DAY,
            CASH,
            equity,
            peak,
            Jsonb({"positions": positions, "scores": scores, "index": 100, "panic": False}),
            SEEN,
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
            DAY,
            prior,
            SEEN,
            Jsonb(
                {
                    "orders": [
                        {"ticker": "AAPL", "side": "sell", "kind": "reduce", "reason_zh": "止盈", "qty": 10},
                        {"ticker": "AAPL", "side": "sell", "kind": "reduce", "reason_zh": "止盈", "qty": 10},
                        {"ticker": "HD", "side": "sell", "kind": "reduce", "reason_zh": "波段止盈", "qty": 8},
                    ]
                }
            ),
        ),
    )
    admin.execute(
        """
        INSERT INTO trading.orders (
            portfolio_id, order_id, signal_date, trade_date, ticker, side, kind,
            qty, rule_ids, reason_zh, rule_set, params_version, status, intent
        ) VALUES (%s, 'b062-jnj', %s, %s, 'JNJ', 'sell', 'reduce', NULL, ARRAY['M-59'],
                  '警戒减仓', 'A', 'p-2026.10', 'pending', '{}')
        """,
        (PORTFOLIO, prior, DAY),
    )
    admin.execute(
        """
        INSERT INTO trading.orders (
            portfolio_id, order_id, signal_date, trade_date, ticker, side, kind,
            qty, fill_price, rule_ids, reason_zh, rule_set, params_version, status, intent
        ) VALUES (%s, 'b062-hd', %s, %s, 'HD', 'sell', 'reduce', 8, 95.5, ARRAY['M-59'],
                  '波段止盈', 'A', 'p-2026.10', 'filled', '{}')
        """,
        (PORTFOLIO, prior, DAY),
    )
    _score_row(admin, "LITE", {"price": 55, "dev50": 0, "drawdown252": -10, "rsi": 48}, {"pe": 22}, True)
    _score_row(admin, "CRWD", {"price": 100, "rsi": 40}, {"pe": 420}, False)
    _score_row(admin, "PANW", {"price": 100, "rsi": 40}, {"pe": 18}, False)
    _range_row(
        admin,
        "CRWD",
        {
            "implied_reason": "无法反解：价格不在[-50,200]内",
            "inputs": {"eps": 1.2, "pe_p25": 40, "pe_p50": 50, "pe_p75": 60},
        },
    )
    _range_row(admin, "PANW", {"inputs": {"eps": 0.01, "pe_p25": 20, "pe_p50": 30, "pe_p75": 40}})
    _short(admin, "pltr-old", "PLTR", date(2026, 9, 30), 4.2, {"changePercent": 0, "settlementDate": "2026-09-30"})
    _short(admin, "pltr-new", "PLTR", date(2026, 11, 15), 40, {"changePercent": 1, "settlementDate": "2026-11-15"})
    _short(admin, "wmt-old", "WMT", date(2026, 8, 1), 3.1, {"changePercent": 0})
    _short(admin, "wmt-new", "WMT", date(2026, 11, 28), 30, {"changePercent": 1, "settlementDate": "11/28/2026"})


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
    bundle = {"admin": admin, "dsn": f"postgresql://b062_web@{host}/inves_cog"}
    yield bundle
    _clear(admin)
    admin.close()


def _get(pages, path, day=DAY):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params={"date": day.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _account(pages, day=DAY):
    return _get(pages, "/api/pages/brief/account", day).json()


def _names(rows):
    return {row.get("ticker") for row in rows}


def _stock_attrs(html):
    found = []
    for part in html.split("<tr"):
        if "data-ticker=" not in part:
            continue
        found.append(dict(re.findall(r'data-([a-z0-9_]+)="([^"]*)"', part)))
    return found


def _keep(row, kind, theme, query):
    ok = (
        kind == "all"
        or (kind == "held" and row.get("held") == "1")
        or (kind == "buy" and row.get("buy") == "1")
        or (kind == "move" and row.get("move") == "1")
        or (kind == "crowd" and row.get("crowd") == "1")
    )
    if theme and row.get("theme") != theme:
        return False
    if query and query not in (row.get("ticker") or ""):
        return False
    return ok


def test_g3_downside_and_take_profit_groups(pages):
    account = _account(pages)
    reds = _names(row for row in account["risk_lines"] if row.get("ticker") and row["level"] == "red")
    oranges = _names(row for row in account["risk_lines"] if row.get("ticker") and row["level"] == "orange")
    takes = _names(account["take_profits"])
    assert reds == {"GOOGL", "JNJ"}
    assert oranges == {"AVGO", "MRVL", "AMD", "MU", "NFLX", "NVDA"}
    assert takes == {"AMD", "HD", "ADBE"}
    assert account["down_red"] == 2 and account["down_orange"] == 6
    html = _get(pages, "/account").text
    assert "2 项重点下行风险" in html
    assert "重点 2 / 关注 6 · 止盈提示 3" in html
    assert '<span class="dot hi">2</span>' in html and '<span class="dot mid">6</span>' in html


def test_g2_risk_chips_do_not_use_up_down_colors(pages):
    html = _get(pages, "/account").text
    for classes in re.findall(r'class="([^"]*\bchip\b[^"]*)"', html):
        names = classes.split()
        assert "up" not in names and "down" not in names
    assert 'class="chip hi"' in html and 'class="chip mid"' in html and 'class="chip tp"' in html
    assert html.count('<span class="dot hi">') == html.count("2 项重点下行风险")


def test_g7_drawdown_matches_the_brake_gap(pages):
    account = _account(pages)
    html = _get(pages, "/account").text
    assert "−3.65%" in html
    assert account["risk_card"]["dd8_gap"] == "还有 4.35 个百分点"
    assert account["risk_card"]["dd12_gap"] == "还有 8.35 个百分点"
    assert "还有 4.35 个百分点" in html and "还有 8.35 个百分点" in html
    assert "距历史高点" in html and "与回撤刹车同一口径" in html


def test_g8_missing_plan_keeps_the_carried_book(pages):
    account = _account(pages, NEXT)
    assert account["plan_missing"] is True
    assert account["carried_from"] == DAY.isoformat()
    assert len(account["holdings"]) == 13
    html = _get(pages, "/account", NEXT).text
    assert html.count('data-row="') == 13
    assert f"{NEXT.isoformat()} 计划缺失，以下沿用 {DAY.isoformat()} 日持仓" in html
    assert 'class="banner warn"' in html


def test_g4_ruler_labels_and_boxes(pages):
    holdings = {row["ticker"]: row for row in _account(pages)["holdings"]}
    for ticker, row in holdings.items():
        drawn = ruler(row["ruler"], 470)
        boxes = drawn["boxes"]
        for index, left in enumerate(boxes):
            for right in boxes[index + 1 :]:
                assert not boxes_overlap(left, right), (ticker, left["text"], right["text"])
    googl = ruler(holdings["GOOGL"]["ruler"], 470)["svg"]
    jnj = ruler(holdings["JNJ"]["ruler"], 470)["svg"]
    amd = ruler(holdings["AMD"]["ruler"], 470)["svg"]
    assert "已低于 200 日线 5.0%" in googl
    assert "再跌 8.4% 跌破 200 日线" in jnj
    assert "翻倍止盈 $100.00 ✓" in amd and 'fill="#fff"' in amd
    for ticker in ("HD", "NFLX"):
        svg = ruler(holdings[ticker]["ruler"], 470)["svg"]
        assert "200 日线" not in svg and "灾难" not in svg
        assert holdings[ticker]["ruler"]["ma200"] is None


def test_g5_rule_states_and_conditions(pages):
    holdings = {row["ticker"]: row for row in _account(pages)["holdings"]}
    avgo = next(row for row in holdings["AVGO"]["levels"] if row["name"] == "破位减仓")
    jnj = next(row for row in holdings["JNJ"]["levels"] if row["name"] == "警戒减仓")
    amd = next(row for row in holdings["AMD"]["levels"] if row["name"] == "翻倍止盈价")
    assert avgo["status"] == "done"
    assert jnj["status"] == "pending"
    assert amd["status"] == "hold"
    assert any(cond["ok"] for cond in amd["conds"]) and any(not cond["ok"] for cond in amd["conds"])
    for row in holdings["AAPL"]["levels"]:
        assert row["status"] == "none"
    html = _get(pages, "/account").text
    assert "已执行 · 不再重复" in html
    assert "已到门槛 · 待执行" in html
    assert "已到门槛 · 暂不执行" in html
    assert "未到门槛" in html
    assert "✓" in html and "✗" in html


def test_g6_interactions_are_in_the_page_and_the_script(pages):
    account = _get(pages, "/account").text
    assert 'id="row-AVGO"' in account and 'id="det-AVGO"' in account
    assert 'class="detail show"' not in account
    assert 'data-go="AVGO"' in account and 'data-close="AVGO"' in account
    stocks = _get(pages, "/stocks").text
    rows = _stock_attrs(stocks)
    assert _names(row for row in rows if _keep(row, "held", "", "")) == set(HOLDINGS)
    assert [row["ticker"] for row in rows if _keep(row, "all", "", "AVGO")] == ["AVGO"]
    medical = {row["ticker"] for row in rows if _keep(row, "all", "医疗", "")}
    assert {"JNJ", "LLY"} <= medical
    for key in ("all", "held", "buy", "move", "crowd"):
        assert f'data-sf="{key}"' in stocks
    assert 'id="sth"' in stocks and 'id="sq"' in stocks and 'data-sc="chg"' in stocks
    assert "data-th=" in stocks and "data-only=" in stocks
    trust = _get(pages, "/trust").text
    assert "data-stat" in trust
    script = (ROOT / "src/inves_cog/web/investor.js").read_text()
    assert "location.hash" in script and ".toUpperCase()" in script
    assert 'getElementById("row-" + hash)' in script and "toggleRow(hash, true)" in script
    assert "data-sf" in script and "data-sc" in script and "data-only" in script
    assert "data-ev" in script and "data-stat" in script and "data-go" in script
    assert "@media (max-width:760px)" in account


def test_g9_orders_fills_and_candidate_price(pages):
    account = _account(pages)
    pending = next(row for row in account["pending_orders"] if row["ticker"] == "JNJ")
    assert pending["qty"] is None
    assert str(pending["since"]) == _prior(DAY).isoformat()
    closed = account["closed_records"]
    apple = next(row for row in closed if row["ticker"] == "AAPL")
    hd = next(row for row in closed if row["ticker"] == "HD")
    assert apple["repeat"] == 2 and apple["fill_state"] == "计划"
    assert hd["fill_state"] == "已成交" and hd["qty"] == 8 and hd["fill_price"] == pytest.approx(95.5)
    lite = next(row for row in account["candidates"] if row["ticker"] == "LITE")
    assert lite["price"] == 55
    html = _get(pages, "/account").text
    assert "暂缺" in html and "计划 ×2" in html and "已成交 · $95.50 · 8 股" in html
    assert "$55.00" in html
    hd_row = html.split('data-row="HD"', 1)[1].split('data-row="', 1)[0]
    assert "−2.00%" in hd_row
    privilege = (
        pages["admin"].execute("SELECT has_table_privilege('role_web', 'trading.orders', 'SELECT') AS ok").fetchone()
    )
    assert privilege["ok"] is True
    assert account["fills_readable"] is True


def test_g10_future_shorts_and_extreme_pe_become_anomalies(pages):
    stocks = _get(pages, "/stocks").text
    trust = _get(pages, "/trust").text
    visible = _visible(stocks + trust)
    assert "9/30 结算" in stocks and "8/1 结算" in stocks
    assert "11/15" not in visible and "11/28" not in visible
    assert "[-50,200]" not in visible and "无法反解" not in visible
    assert "市盈率不适用（盈利过低）" in visible
    assert PLAIN in visible
    payload = _get(pages, "/api/pages/brief/trust").json()
    titles = " ".join(row["title"] + row["detail"] for row in payload["anomalies"])
    assert "PLTR 2026-11-15" in titles and "WMT 2026-11-28" in titles
    assert "CRWD 市盈率不适用（盈利过低）" in titles
    assert "PANW 市盈率不适用（盈利过低）" in titles
    assert "CRWD 隐含增速超出可解释范围" in titles


def test_g11_pages_stay_local_and_read_only(pages):
    paths = ("/", "/stocks", "/account", "/trust", "/s/AVGO", "/s/LITE")
    blob = "".join(_get(pages, path).text for path in paths)
    assert "http://" not in blob and "https://" not in blob
    assert blob.count("<script") == len(paths)
    assert 'src="/investor.js"' in blob and "<script>" not in blob
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        script = client.get("/investor.js")
        assert script.status_code == 200
        assert script.headers["content-type"].startswith("text/javascript")
        assert "function ruler" in script.text
        assert client.post("/account").status_code == 405
    for name in ("api.py", "brief.py", "investor_html.py", "risk_brief.py", "stock_brief.py"):
        assert "GRANT " not in (ROOT / "src/inves_cog/web" / name).read_text()


def test_g12_forbidden_words_stay_off_the_pages(pages):
    paths = ("/", "/stocks", "/account", "/trust", "/s/AVGO", "/s/LITE")
    blob = _visible("".join(_get(pages, path).text for path in paths) + _get(pages, "/account", NEXT).text)
    for word in ("下单", "实时", "目标价", "合理价", "N1"):
        assert word not in blob
    assert _RULE.search(blob) is None
    assert _LOWER.findall(blob) == []
