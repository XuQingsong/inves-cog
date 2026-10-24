"""Durable quota, PIT and privilege checks on the harness database only."""

from datetime import timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.valuation_v1.consensus import Repository, parse_estimates
from tests.m5.test_a020 import NOW, sample
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking


@pytest.fixture
def database():
    host = _disposable_database()
    db = psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", autocommit=True, row_factory=dict_row)
    db.execute("TRUNCATE valuation_v1.consensus_snapshots")
    db.execute("SET ROLE role_valuation")
    try:
        yield host, db
    finally:
        db.execute("RESET ROLE")
        db.execute("TRUNCATE valuation_v1.consensus_snapshots")
        db.close()


def test_a020_durable_quota_survives_connection_restart_and_stops_on_note(database):
    host, db = database
    repo = Repository(db)
    for i in range(24):
        ticker = "A" + str(i)
        request = repo.reserve(ticker, NOW)
        assert request
        repo.finish(request, ticker, NOW, {"no_estimates": True}, [], "error")
    with psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", autocommit=True, row_factory=dict_row
    ) as restarted:
        restarted.execute("SET ROLE role_valuation")
        other = Repository(restarted)
        assert other.reserve("EXTRA", NOW) is None
        assert not other.available(NOW)
        tomorrow = NOW + timedelta(days=1, seconds=1)
        request = other.reserve("NEXT", tomorrow)
        assert request
        other.finish(request, "NEXT", tomorrow, {"Information": "quota"}, [], "throttled")
        assert other.reserve("EXTRA", tomorrow) is None
        assert not other.available(tomorrow)


def test_a020_pit_uses_latest_visible_whole_response_and_table_is_append_only(database):
    _, db = database
    repo = Repository(db)
    raw = sample()
    request = repo.reserve("NVDA", NOW)
    repo.finish(request, "NVDA", NOW, raw, parse_estimates("NVDA", raw, NOW), "ok")
    assert repo.pit("NVDA", NOW - timedelta(seconds=1)) is None
    visible = repo.pit("NVDA", NOW)
    assert visible["raw"] == raw and len(visible["estimates"]) == 3
    later = NOW + timedelta(days=1, seconds=1)
    request = repo.reserve("NVDA", later)
    repo.finish(request, "NVDA", later, {"Error Message": "unavailable"}, [], "error")
    assert repo.pit("NVDA", NOW)["raw"] == raw
    assert repo.pit("NVDA", later)["status"] == "error"
    assert repo.pit("NVDA", later)["estimates"] == []
    with pytest.raises(psycopg.Error):
        db.execute("DELETE FROM valuation_v1.consensus_snapshots")
    db.execute("RESET ROLE")
    with pytest.raises(psycopg.Error):
        db.execute("UPDATE valuation_v1.consensus_snapshots SET status='error'")
    for role in ["role_web", "role_trading"]:
        db.execute("SET ROLE " + role)
        assert Repository(db).pit("NVDA", NOW)["raw"] == raw
        assert not db.execute(
            "SELECT has_table_privilege(current_user,'valuation_v1.consensus_snapshots','INSERT') AS yes"
        ).fetchone()["yes"]
        db.execute("RESET ROLE")


def test_a020_abandoned_http_reservation_fails_closed(database):
    _, db = database
    repo = Repository(db)
    assert repo.reserve("A", NOW)
    assert Repository(db).reserve("B", NOW) is None
    assert not Repository(db).available(NOW)
