"""B-064: news slimming, translations, Beijing time, carry-over, intraday."""

import re
from datetime import date, datetime, time, timedelta

import pytest
from psycopg.types.json import Jsonb
from starlette.testclient import TestClient

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import NY, trading_day
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

PORTFOLIO = "b064-paper"
HELD = ["NVDA", "AAPL"]
POOL_EXTRA = ["MSFT", "JNJ", "LITE"]
DAY = date(2036, 10, 23)
PREV = date(2036, 10, 22)
while not trading_day(DAY):
    DAY += timedelta(days=1)
while not trading_day(PREV) or PREV >= DAY:
    PREV += timedelta(days=1)
# Frozen mid-morning ET on DAY: today_trade_date() == DAY, pre-close -> carry-over.
CLOCK = FrozenClock(datetime.combine(DAY, time(10, 0), tzinfo=NY))
SEEN = datetime.combine(DAY, time(8, 0), tzinfo=NY)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
TRANSLATE_DDL = """
CREATE TABLE IF NOT EXISTS perception.news_translations (
    info_id text PRIMARY KEY, title_zh text NOT NULL, model text NOT NULL, translated_at timestamptz NOT NULL
)
"""
_CALENDAR_DDL = """
CREATE TABLE IF NOT EXISTS ingest.earnings_calendar (
    ticker text NOT NULL, report_date date NOT NULL,
    time text NOT NULL CHECK (time IN ('pre','post','unknown')),
    eps_forecast numeric, n_estimates int, market_cap numeric,
    company text, source text NOT NULL, fetched_at timestamptz NOT NULL,
    PRIMARY KEY (ticker,report_date,source)
);
CREATE TABLE IF NOT EXISTS ingest.econ_calendar (
    event_date date NOT NULL, event_time_et text, country text NOT NULL, name text NOT NULL,
    actual text, consensus text, previous text,
    source text NOT NULL, fetched_at timestamptz NOT NULL,
    PRIMARY KEY (event_date,country,name,source)
)
"""
INTRADAY_DDL = """
CREATE TABLE IF NOT EXISTS ingest.intraday_snapshots (
    ticker text, as_of timestamptz, session text CHECK (session IN ('pre','regular','post')),
    last numeric NOT NULL, prev_close numeric, delay_minutes int NOT NULL,
    source text NOT NULL, fetched_at timestamptz NOT NULL,
    PRIMARY KEY (ticker, as_of, source)
)
"""


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b064_web') THEN "
        "CREATE ROLE b064_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b064_web")


def _clear(admin):
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b064-%'")
    admin.execute("DELETE FROM ingest.intraday_snapshots WHERE source = 'b064'")
    admin.execute("DELETE FROM perception.news_translations WHERE info_id LIKE 'b064-%'")
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date IN (%s, %s)", (DAY, PREV))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date IN (%s, %s)", (DAY, PREV))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date IN (%s, %s)", (DAY, PREV))


def _seed(admin):
    admin.execute(TRANSLATE_DDL)
    admin.execute(INTRADAY_DDL)
    admin.execute(_CALENDAR_DDL)
    _clear(admin)
    for kind, name, ret in [("index", "SPY", -0.01), ("index", "QQQ", -0.02), ("index", "IWM", 0.01)]:
        admin.execute(
            "INSERT INTO marketstate.rotation (trade_date, session, group_kind, group_id, ret, health_codes)"
            " VALUES (%s, 'close', %s, %s, %s, '{}')",
            (PREV, kind, name, ret),
        )
    for ticker, ret in {"NVDA": -0.06, "AAPL": 0.03, "MSFT": 0.01, "JNJ": -0.02, "LITE": -0.08}.items():
        admin.execute(
            "INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)"
            " VALUES (%s, %s, 'close', %s, 'b064', '{}')",
            (PREV, ticker, ret),
        )
        admin.execute(
            "INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)"
            " VALUES (%s, %s, 100, 1000000, 'b064')",
            (ticker, PREV),
        )
    admin.execute(
        "INSERT INTO marketstate.market (trade_date, shock_flag, l1_state, style_spread_z, vix3m)"
        " VALUES (%s, false, '正常', '{}', 20.5)",
        (PREV,),
    )
    state = {"positions": {t: {"shares": 10, "avg_cost": 90, "peak_price": 110, "tier_now": "normal"} for t in HELD}}
    admin.execute(
        "INSERT INTO trading.ledger (portfolio_id, trade_date, phase, extractor, rule_set, params_version,"
        " cash, equity, peak_equity, state, observed_at)"
        " VALUES (%s, %s, 'close', 'fixed', 'A', 'p-2026.10', 400000, 1000000, 1100000, %s, %s)",
        (PORTFOLIO, PREV, Jsonb(state), SEEN - timedelta(days=1)),
    )
    news = [
        ("b064-n1", "NVIDIA Posts Strong Q3, Guidance Raises FY Outlook", ["NVDA"]),
        ("b064-n2", "Apple Launches First Foldable Smartphone, the iPhone Duo", ["AAPL"]),
        ("b064-n3", "UBS Maintains Buy on NVIDIA, Lowers Price Target to $200", ["NVDA"]),
        ("b064-n4", "Mizuho Maintains Buy on NVIDIA, Adjusts PT to $210", ["NVDA"]),
        ("b064-n5", "Bernstein Upgrades Bloom Energy to Outperform", ["BE"]),
    ]
    # weak ratings for grouping
    for i, (iid, headline, tickers) in enumerate(news):
        admin.execute(
            """
            INSERT INTO ingest.info_items (
                info_id, kind, published_at, first_seen_at, source, source_level, headline,
                tickers, entities, url, extraction_status, flags, payload, extraction_source
            ) VALUES (%s, 'news', %s, %s, 'fixture', 1, %s, %s, '{}',
                'https://example.com/x', 'ok', '{}', '{}', '{}')
            """,
            (iid, SEEN + timedelta(minutes=i), SEEN + timedelta(minutes=i), headline, tickers),
        )
    for i in range(6, 20):
        admin.execute(
            """
            INSERT INTO ingest.info_items (
                info_id, kind, published_at, first_seen_at, source, source_level, headline,
                tickers, entities, url, extraction_status, flags, payload, extraction_source
            ) VALUES (%s, 'news', %s, %s, 'fixture', 1, %s, '{NVDA}', '{}',
                'https://example.com/x', 'ok', '{}', '{}', '{}')
            """,
            (f"b064-f{i}", SEEN + timedelta(minutes=i), SEEN + timedelta(minutes=i), f"NVIDIA earnings beat #{i}"),
        )
    admin.execute(
        "INSERT INTO perception.news_translations (info_id, title_zh, model, translated_at)"
        " VALUES ('b064-n1', '英伟达三季度业绩强劲，上调全年指引', 'deepseek-v4.1-flash', %s)",
        (SEEN,),
    )
    for ticker, last in (("SPY", 604.2), ("NVDA", 200.4)):
        admin.execute(
            """
            INSERT INTO ingest.intraday_snapshots (
                ticker, as_of, session, last, prev_close, delay_minutes, source, fetched_at
            ) VALUES (%s, %s, 'pre', %s, 600.0, 15, 'b064', %s)
            """,
            (ticker, SEEN + timedelta(minutes=30), last, SEEN + timedelta(minutes=30)),
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
    yield {"admin": admin, "dsn": f"postgresql://b064_web@{host}/inves_cog"}
    _clear(admin)
    admin.close()


def _get(pages, path, params=None):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params=params or {"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def _visible(html):
    return _TAG.sub(" ", _STYLE.sub(" ", html))


def test_carry_over_labels_and_banner(pages):
    html = _get(pages, "/").text
    assert "沿用" in html and "收盘" in html
    # fixture clock is 10:00 ET -> intraday session banner
    assert "盘中" in html


def test_feed_default_10_and_grouped_ratings(pages):
    market = _get(pages, "/api/pages/brief/market").json()
    feed = market["news_modules"]["feed"]
    assert len(feed) <= 40
    grouped = [n for n in feed if n.get("grouped")]
    assert len(grouped) == 1 and grouped[0]["group_count"] == 2
    html = _get(pages, "/").text
    assert "家机构调整目标价" in html
    assert "展开剩余" in html or len(feed) <= 10


def test_title_zh_and_fallback(pages):
    html = _get(pages, "/").text
    assert "英伟达三季度业绩强劲" in html and 'class="nen"' in html
    # untranslated items fall back to English
    assert "Bernstein Upgrades Bloom Energy" in html


def test_beijing_time_suffix(pages):
    html = _get(pages, "/").text
    assert "北京" in _visible(html)


def test_intraday_line(pages):
    html = _get(pages, "/").text
    assert "盘前" in _visible(html) and "延迟约" in _visible(html)
    assert "不进入规则 A" in _visible(html)


def test_hot_themes_cap(pages):
    market = _get(pages, "/api/pages/brief/market").json()
    themes = market["news_modules"]["theme_news"]
    assert len(themes) <= 8
    assert len({n["theme"] for n in themes}) == len(themes)


def test_movers_single_news(pages):
    market = _get(pages, "/api/pages/brief/market").json()
    for m in market["news_modules"]["movers"]:
        assert len(m.get("news") or []) <= 1


def test_lang_toggle_and_refresh_meta(pages):
    html = _get(pages, "/").text
    assert 'id="lang-toggle"' in html and "refresh-today" in html


# ---------- translate_day unit tests (stubbed DB, counting fake client) ----------


class _StubConn:
    """Minimal connection stand-in: returns canned rows per SQL fragment."""

    def __init__(self, tables):
        self.tables = tables

    def execute(self, sql, params=None):
        for key, rows in self.tables.items():
            if key in sql:
                return _Cur(rows)
        return _Cur([])


class _Cur:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _FakeClient:
    def __init__(self, results=None, fail=False):
        self.calls = []
        self.results = results or []
        self.fail = fail

    def call(self, task, payload):
        self.calls.append((task, payload))
        if self.fail:
            raise RuntimeError("boom")
        index = len(self.calls) - 1
        if index < len(self.results):
            return self.results[index]
        return {"titles": ["中文标题"] * payload.get("count", 0)}


def _items(n):
    return [
        {"info_id": f"b064-t{i}", "headline": f"Headline {i}", "published_at": None, "tickers": ["NVDA"]}
        for i in range(n)
    ]


def _patch_candidates(monkeypatch, items):
    from inves_cog.perception.news import translate

    monkeypatch.setattr(translate, "page_candidates", lambda *a, **k: items)
    monkeypatch.setattr(translate, "_usage", lambda *a, **k: {"calls": 0, "tokens": 0})
    return translate


def test_translate_batches_and_cap(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(120))
    writer = _StubConn({})
    client = _FakeClient()
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    # 120 items -> batches of 50/50/20 but day cap is 6 calls; only 3 needed
    assert client.calls[0][1]["count"] == 50
    assert client.calls[2][1]["count"] == 20
    assert len(client.calls) == 3
    assert result["translated"] == 120


def test_translate_discards_count_mismatch(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(3))
    writer = _StubConn({})
    client = _FakeClient(results=[{"titles": ["一", "二"]}])  # 2 != 3
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    assert result["translated"] == 0


def test_translate_skips_already_translated(monkeypatch):
    items = _items(2)
    translate = _patch_candidates(monkeypatch, items)
    writer = _StubConn({"news_translations": [{"info_id": "b064-t0"}]})
    client = _FakeClient()
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    assert len(client.calls) == 1 and client.calls[0][1]["count"] == 1
    assert result["translated"] == 1


def test_translate_cap_from_usage(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(3))
    monkeypatch.setattr(translate, "_usage", lambda *a, **k: {"calls": 6, "tokens": 100})
    result = translate.translate_day(_StubConn({}), _StubConn({}), _FakeClient(), DAY, clock=CLOCK)
    assert result["status"] == "capped"


def test_translate_call_failure(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(3))
    result = translate.translate_day(_StubConn({}), _StubConn({}), _FakeClient(fail=True), DAY, clock=CLOCK)
    assert result["translated"] == 0


def test_prompt_verbatim():
    from inves_cog.perception.news.translate import _prompt

    system, user = _prompt()
    assert "你是美股财经新闻的标题翻译" in system
    assert "{headlines_json_array}" in user
    assert "只翻译，不补充" in system


def test_feed_rules_unit():
    from inves_cog.perception.news.rules import classify, feed_keep, group_weak_ratings

    weak = classify("UBS Maintains Buy on NVIDIA, Lowers PT to $200", ["NVDA"], {"NVDA"}, set())
    strong = classify("Bernstein Upgrades Bloom Energy", ["BE"], {"BE"}, set())
    assert not feed_keep(weak, set()) and feed_keep(strong, set())
    held_weak = classify("UBS Maintains Buy on NVIDIA", ["NVDA"], {"NVDA"}, {"NVDA"})
    assert feed_keep(held_weak, {"NVDA"})
    items = [
        {"rule": weak, "published": None},
        {"rule": classify("Truist Maintains Buy on NVDA", ["NVDA"], {"NVDA"}, set()), "published": None},
        {"rule": strong, "published": None},
    ]
    rows = group_weak_ratings(items)
    grouped = [r for r in rows if r.get("grouped")]
    assert len(grouped) == 1 and grouped[0]["group_count"] == 2


def test_signal_dedupe_keeps_latest():
    from inves_cog.perception.technical import technicals

    # Falling closes trigger 跌破 20 日新低 on several days in the window.
    closes = list(range(300, 220, -1))
    sig = technicals(closes)["signals"]
    assert sig.count("跌破 20 日新低") == 1


def test_date_picker_and_today_link(pages):
    html = _get(pages, "/").text
    assert 'type="date"' in html and ">今天</a>" in html


def test_carryover_requires_close_session(pages):
    admin = pages["admin"]
    admin.execute(
        "INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)"
        " VALUES (%s, 'NVDA', 'post', 0.05, 'b064', '{}')",
        (DAY,),
    )
    try:
        market = _get(pages, "/api/pages/brief/market").json()
        # post-only rows do NOT count as close data: carry-over still applies.
        assert market["carry_from"] == str(PREV)
    finally:
        admin.execute("DELETE FROM marketstate.daily WHERE trade_date = %s AND session = 'post'", (DAY,))


def test_translate_estimate_blocks_crossing_batch(monkeypatch):
    # usage 49,990 tokens + estimated batch cost > 50,000 -> batch skipped
    translate = _patch_candidates(monkeypatch, _items(2))
    monkeypatch.setattr(translate, "_usage", lambda *a, **k: {"calls": 0, "tokens": 49990})
    result = translate.translate_day(_StubConn({}), _StubConn({}), _FakeClient(), DAY, clock=CLOCK)
    assert result["translated"] == 0


def test_translate_failures_count_toward_cap(monkeypatch):
    # llm_calls already has 6 rows (incl. failures) -> no request attempted
    translate = _patch_candidates(monkeypatch, _items(2))
    monkeypatch.setattr(translate, "_usage", lambda *a, **k: {"calls": 6, "tokens": 100})
    client = _FakeClient()
    translate.translate_day(_StubConn({}), _StubConn({}), client, DAY, clock=CLOCK)
    assert client.calls == []


def test_translate_payload_headlines_only(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(2))
    client = _FakeClient()
    translate.translate_day(_StubConn({}), _StubConn({}), client, DAY, clock=CLOCK)
    payload = client.calls[0][1]
    assert set(payload) == {"system", "user", "count"}
    # user payload is the prompt + a JSON array of headline strings, nothing else
    import json as _json
    import re as _re

    # the last JSON array in the prompt is the input headlines block
    titles = _json.loads(_re.findall(r"\[.*?\]", payload["user"], _re.S)[-1])
    assert titles == [f"Headline {i}" for i in range(2)]


def test_translate_titles_contract_success(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(2))
    writer = _StubConn({})
    client = _FakeClient(results=[{"titles": ["一", "二"]}])
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    assert result["translated"] == 2


def test_translate_rejects_non_titles_shape(monkeypatch):
    translate = _patch_candidates(monkeypatch, _items(2))
    writer = _StubConn({})
    # bare array (old contract) and wrong-key object must both be discarded
    client = _FakeClient(results=[["一", "二"]])
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    assert result["translated"] == 0 and len(client.calls) == 1


def test_translate_real_client_json_object_path(monkeypatch):
    """End-to-end: real Client with injected transport returning {"titles": [...]}."""
    from inves_cog.llm.client import Client
    from inves_cog.llm.registry import Registry

    registry = Registry(__import__("pathlib").Path(__file__).resolve().parents[2] / "config/llm_tasks.yaml")
    sent = []

    def transport(spec, payload):
        sent.append(payload)
        # real transport enforces response_format=json_object and returns a dict
        assert isinstance(payload, dict)
        return {"titles": ["标题一", "标题二"], "_usage": {"input_tokens": 10, "output_tokens": 20}}

    client = Client(registry=registry, transport=transport, clock=CLOCK)
    translate = _patch_candidates(monkeypatch, _items(2))
    writer = _StubConn({})
    result = translate.translate_day(_StubConn({}), writer, client, DAY, clock=CLOCK)
    assert result["translated"] == 2 and len(sent) == 1


def test_prompt_titles_wording_no_note():
    from inves_cog.perception.news.translate import _prompt

    _, user = _prompt()
    assert '{"titles"' in user and "修订" not in user and not user.rstrip().endswith(">")
