"""B-050: page date is the US trade date, and visibility ends at ET D+1 01:00."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.web import pages as page_module
from inves_cog.web.api import create_app
from inves_cog.web.pages import CLOSED, _highlighted
from inves_cog.web.public import create_app as public_app

pytestmark = pytest.mark.phase1_blocking

SHANGHAI = ZoneInfo("Asia/Shanghai")
NEW_YORK = ZoneInfo("America/New_York")
SUMMER = date(2026, 10, 22)
WINTER = date(2026, 1, 15)
CLOSED_DAY = date(2026, 10, 24)
PATHS = (
    "/api/pages/home",
    "/api/pages/market",
    "/api/pages/linkage/b050-missing",
    "/api/pages/stock/NVDA",
    "/api/pages/graph",
    "/api/pages/settings/data",
    "/api/pages/paper/plan",
    "/api/pages/paper/portfolio",
    "/api/pages/paper/universe",
    "/api/pages/paper/stock/NVDA",
    "/api/pages/paper/health",
    "/api/pages/paper/ledger",
)


def _shanghai(day, hour, minute):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=SHANGHAI)


def _new_york(day, hour, minute):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=NEW_YORK)


def _clock(moment):
    return FrozenClock(moment)


def _dsn(host):
    return f"postgresql://b050_web@{host}/inves_cog"


def _clear(admin):
    admin.execute("DELETE FROM perception.reports WHERE anomaly_id LIKE 'b050-%'")
    admin.execute("DELETE FROM perception.linkage_events WHERE event_id LIKE 'b050-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b050-%'")
    admin.execute("DELETE FROM overlay.versions WHERE params_version = 'b050'")
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = 'b050-paper'")


def _anomaly(admin, anomaly_id, generated):
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction,
            max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe,
            params_version, generated_at
        ) VALUES (
            %s, %s, 'close', ARRAY['A'], 'L3', 'alert', %s, %s, 'up',
            1.1, '{}', '{}', '{}', ARRAY[]::text[], '已发现·原因未明', 'pool', 'b050', %s
        )
        """,
        (anomaly_id, SUMMER, ["SMH"], Jsonb([{"ticker": "NVDA"}]), generated),
    )


def _seed(admin):
    _clear(admin)
    morning = _shanghai(SUMMER + timedelta(days=1), 8, 57)
    later = _shanghai(SUMMER + timedelta(days=1), 9, 15)
    snapshot = _shanghai(SUMMER + timedelta(days=1), 12, 30)
    too_late = _shanghai(SUMMER + timedelta(days=1), 13, 30)
    m9 = _new_york(SUMMER, 8, 0)
    plan_at = _new_york(SUMMER, 8, 35)
    _anomaly(admin, "b050-a-m7", morning)
    _anomaly(admin, "b050-a-m8", later)
    _anomaly(admin, "b050-a-after", too_late)
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, unknowns)
        VALUES ('b050-e1', 'b050-a-m7', '已发现', %s, '[]')
        """,
        (Jsonb([{"at": morning.isoformat(), "old": None, "new": "已发现", "trigger": "证据", "evidence_ids": []}]),),
    )
    admin.execute(
        "INSERT INTO perception.reports (anomaly_id, report) VALUES ('b050-a-m7', %s)",
        (Jsonb({"magnitude_channels": [{"channel": "价格", "value": 8.57}]}),),
    )
    for generated, mark in ((m9, "m9-et-0800"), (snapshot, "m8-bj-1230")):
        admin.execute(
            """
            INSERT INTO overlay.versions (date, generated_at, source_events_asof, params_version, payload, published)
            VALUES (%s, %s, %s, 'b050', %s, true)
            """,
            (
                SUMMER,
                generated,
                generated,
                Jsonb(
                    {
                        "m8_completeness": {"mark": mark},
                        "tickers": {
                            "NVDA": {
                                "cooling_status": "off",
                                "m8_gaps": [],
                                "linkage_events": [{"event_id": "b050-e1", "exposure": "直接"}],
                            }
                        },
                    }
                ),
            ),
        )
    admin.execute(
        """
        INSERT INTO trading.plan (
            portfolio_id, trade_date, signal_date, extractor, rule_set, params_version, published, generated_at, payload
        ) VALUES ('b050-paper', %s, %s, 'fixed', 'A', 'b050', true, %s, %s)
        """,
        (
            SUMMER,
            SUMMER - timedelta(days=1),
            plan_at,
            Jsonb({"mark": "m4-et-0835", "input_completeness": {"bars": "ok"}, "skips": []}),
        ),
    )


def _open_db():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    admin.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b050_web') THEN "
        "CREATE ROLE b050_web LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_web TO b050_web")
    _seed(admin)
    return admin, _dsn(host)


@pytest.fixture(scope="module")
def pages():
    admin, dsn = _open_db()
    yield {"admin": admin, "dsn": dsn}
    _clear(admin)
    admin.close()


def _get(pages, path, moment, day=SUMMER, *, public=False):
    app = public_app if public else create_app
    with TestClient(app(dsn=pages["dsn"], clock=_clock(moment))) as client:
        response = client.get(path, params={"date": day.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def test_trade_date_rows_are_visible_at_beijing_1305(pages):
    moment = _shanghai(SUMMER + timedelta(days=1), 13, 5)
    home = _get(pages, "/api/pages/", moment, public=True)
    visible = {row["anomaly_id"] for row in home["unhandled"]}
    assert home["counts"]["anomaly_count"] == 2
    assert visible == {"b050-a-m7", "b050-a-m8"}
    assert all(row["highlighted"] for row in home["unhandled"])
    linkage = _get(pages, "/api/pages/linkage/b050-e1", moment)
    assert linkage["m8_completeness"] == {"mark": "m8-bj-1230"}
    assert linkage["magnitude_channels"] == [{"channel": "价格", "value": 8.57}]
    plan = _get(pages, "/api/pages/paper/plan", moment)
    assert plan["plan"]["mark"] == "m4-et-0835"


def test_cutoff_hides_rows_after_the_request_or_the_deadline(pages):
    early = _shanghai(SUMMER + timedelta(days=1), 9, 0)
    home = _get(pages, "/api/pages/home", early)
    assert {row["anomaly_id"] for row in home["unhandled"]} == {"b050-a-m7"}
    assert home["unhandled"][0]["highlighted"] is False
    linkage = _get(pages, "/api/pages/linkage/b050-e1", early)
    assert linkage["m8_completeness"] == {"mark": "m9-et-0800"}
    late = _get(pages, "/api/pages/home", _shanghai(SUMMER + timedelta(days=1), 13, 5))
    assert "b050-a-after" not in {row["anomaly_id"] for row in late["unhandled"]}


def test_highlight_follows_daylight_and_standard_time():
    summer_before = _clock(_shanghai(SUMMER + timedelta(days=1), 12, 59))
    summer_at = _clock(_shanghai(SUMMER + timedelta(days=1), 13, 0))
    assert _highlighted(summer_before, SUMMER) is False
    assert _highlighted(summer_at, SUMMER) is True
    winter_before = _clock(_shanghai(WINTER + timedelta(days=1), 13, 59))
    winter_at = _clock(_shanghai(WINTER + timedelta(days=1), 14, 0))
    assert _highlighted(winter_before, WINTER) is False
    assert _highlighted(winter_at, WINTER) is True


def test_pages_share_one_cutoff_and_closed_days_say_so(pages, monkeypatch):
    seen = []
    real = page_module._cutoff

    def wrapped(clock, day):
        value = real(clock, day)
        seen.append(value)
        return value

    monkeypatch.setattr(page_module, "_cutoff", wrapped)
    moment = _shanghai(SUMMER + timedelta(days=1), 13, 5)
    with TestClient(create_app(dsn=pages["dsn"], clock=_clock(moment))) as client:
        for path in PATHS:
            response = client.get(path, params={"date": SUMMER.isoformat()})
            assert response.status_code == 200, path
        assert len(seen) == len(PATHS)
        assert len(set(seen)) == 1
        seen.clear()
        for path in PATHS:
            response = client.get(path, params={"date": CLOSED_DAY.isoformat()})
            assert response.status_code == 200, path
            assert response.json() == {"message": CLOSED}
        assert seen == []
