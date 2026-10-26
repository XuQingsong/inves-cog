"""B-065: market ticker strip + sector strip on the 今日 page."""

from datetime import date, datetime, time, timedelta

import pytest
from psycopg.types.json import Jsonb
from starlette.testclient import TestClient

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import NY, trading_day
from inves_cog.web.public import create_app

pytestmark = pytest.mark.phase1_blocking

PORTFOLIO = "b065-paper"
HELD = ["NVDA"]
DAY = date(2036, 10, 23)
PREV = date(2036, 10, 22)
while not trading_day(DAY):
    DAY += timedelta(days=1)
while not trading_day(PREV) or PREV >= DAY:
    PREV += timedelta(days=1)
CLOCK = FrozenClock(datetime.combine(DAY, time(10, 0), tzinfo=NY))
SEEN = datetime.combine(DAY, time(8, 0), tzinfo=NY)
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
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b065_web') THEN "
        "CREATE ROLE b065_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b065_web")


def _clear(admin):
    admin.execute("DELETE FROM ingest.intraday_snapshots WHERE source = 'b065'")
    admin.execute("DELETE FROM ingest.macro_observations WHERE series_id = 'DGS2' AND source = 'b065'")
    admin.execute("DELETE FROM trading.ledger WHERE portfolio_id = %s", (PORTFOLIO,))
    admin.execute("DELETE FROM marketstate.daily WHERE trade_date IN (%s, %s)", (DAY, PREV))
    admin.execute("DELETE FROM marketstate.rotation WHERE trade_date IN (%s, %s)", (DAY, PREV))
    admin.execute("DELETE FROM marketstate.market WHERE trade_date IN (%s, %s)", (DAY, PREV))


def _snap(admin, ticker, last, prev_close, session="pre", minutes=30):
    admin.execute(
        "INSERT INTO ingest.intraday_snapshots (ticker, as_of, session, last, prev_close, delay_minutes, source, fetched_at)"
        " VALUES (%s, %s, %s, %s, %s, 15, 'b065', %s)",
        (ticker, SEEN + timedelta(minutes=minutes), session, last, prev_close, SEEN + timedelta(minutes=minutes)),
    )


def _seed(admin):
    _clear(admin)
    admin.execute(INTRADAY_DDL)
    for kind, name, ret in [("index", "SPY", -0.01), ("index", "QQQ", -0.02), ("index", "IWM", 0.01)]:
        admin.execute(
            "INSERT INTO marketstate.rotation (trade_date, session, group_kind, group_id, ret, health_codes)"
            " VALUES (%s, 'close', %s, %s, %s, '{}')",
            (PREV, kind, name, ret),
        )
    admin.execute(
        "INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)"
        " VALUES (%s, 'NVDA', 'close', -0.06, 'b065', '{}')",
        (PREV,),
    )
    admin.execute(
        "INSERT INTO ingest.bars_daily (ticker, trade_date, close, volume, source)"
        " VALUES ('NVDA', %s, 100, 1000000, 'b065')",
        (PREV,),
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
    _snap(admin, "ES=F", 6050.0, 6000.0)  # +0.83%
    _snap(admin, "SPY", 604.2, 600.0)  # +0.70%
    _snap(admin, "^TNX", 4.40, 4.408)  # -0.8bp
    _snap(admin, "NVDA", 200.4, 200.0)  # sector avg uses snapshot
    admin.execute(
        "INSERT INTO ingest.macro_observations (series_id, observation_date, value, source, fetched_at)"
        " VALUES ('DGS2', %s, 3.85, 'b065', %s)",
        (PREV, SEEN),
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
    yield {"admin": admin, "dsn": f"postgresql://b065_web@{host}/inves_cog"}
    _clear(admin)
    admin.close()


def _get(pages, path, params=None):
    with TestClient(create_app(dsn=pages["dsn"], clock=CLOCK)) as client:
        response = client.get(path, params=params or {"date": DAY.isoformat()})
    assert response.status_code == 200, response.text
    return response


def test_strip_renders_and_bp(pages):
    html = _get(pages, "/").text
    assert 'id="mstrip"' in html and 'id="sstrip"' in html
    assert "标普期货" in html and "美债 10 年" in html
    # ^TNX 4.40 vs 4.408 -> -0.8bp
    assert "-0.8bp" in html


def test_dgs2_prior_day_label(pages):
    html = _get(pages, "/").text
    assert "美债 2 年" in html and "前一日" in html


def test_sector_strip_uses_snapshots(pages):
    market = _get(pages, "/api/pages/brief/market").json()
    strip = market.get("sector_strip") or []
    assert strip, "sector strip empty"
    # NVDA snapshot ret = 200.4/200 - 1 = +0.2%, not close -6%
    card = [c for c in strip if c["leader"] and c["leader"][0] == "NVDA"]
    assert card and abs(card[0]["average"] - 0.002) < 1e-6


def test_no_snapshot_falls_back_to_close(pages):
    # QQQ/IWM have no snapshot -> show close ret value with 收盘 marker
    html = _get(pages, "/").text
    assert "收盘" in html


def test_strip_tail_and_rule_a_note(pages):
    html = _get(pages, "/").text
    assert "美东" in html and "不进入规则 A" in html


def test_theme_anchor_on_stocks(pages):
    html = _get(pages, "/stocks").text
    assert 'id="theme-' in html
    market = _get(pages, "/api/pages/brief/market").json()
    for card in market.get("sector_strip") or []:
        assert card["slug"].startswith("theme-") and card["slug"] in html
