"""A024 schema roles and exact 30-day cleanup in disposable PostgreSQL."""

from datetime import timedelta

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.ingest.repository import Repository
from tests.m1.test_a024 import CLOCK, sample
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking


def check_a024_database(c):
    from inves_cog.ingest.intraday import parse_snapshots

    repo = Repository(c)
    row = parse_snapshots(sample("spy_snapshot.json"), {"SPY": 759.97}, ["SPY"], CLOCK)[0]
    c.execute("SET LOCAL ROLE role_ingest")
    for days in [31, 30, 0]:
        repo.write("intraday_snapshots", {**row, "as_of": CLOCK.now_utc() - timedelta(days=days)})
    assert repo.cleanup_intraday(CLOCK.now_utc() - timedelta(days=30)) == 1
    assert repo.cleanup_intraday(CLOCK.now_utc() - timedelta(days=30)) == 0
    c.execute("RESET ROLE")
    c.execute("SET LOCAL ROLE role_web")
    actual = c.execute("SELECT * FROM ingest.intraday_snapshots ORDER BY as_of").fetchall()
    assert len(actual) == 2 and actual[0]["as_of"] == CLOCK.now_utc() - timedelta(days=30)
    assert actual[-1]["last"] == row["last"]
    assert (
        c.execute(
            "SELECT has_table_privilege(current_user,'ingest.intraday_snapshots','INSERT') AS can_write"
        ).fetchone()["can_write"]
        is False
    )
    c.execute("RESET ROLE")


def test_a024_real_pg_schema_roles_and_30_day_cleanup():
    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row
    ) as c:
        try:
            check_a024_database(c)
        finally:
            c.rollback()
