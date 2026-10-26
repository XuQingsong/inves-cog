"""Real PostgreSQL contracts for A023, in the harness disposable database only."""

import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.clock import FrozenClock
from inves_cog.ingest.info import make_item
from inves_cog.ingest.repository import Repository
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking
CLOCK = FrozenClock(datetime(2026, 10, 26, 14, tzinfo=timezone.utc))


@pytest.fixture
def database():
    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row
    ) as c:
        try:
            yield c
        finally:
            c.rollback()


def check_a023_database(c):
    from inves_cog.ingest.resilience import parse_earnings, parse_econ

    repo = Repository(c)
    for name, parser, day in [
        ("earnings_calendar", parse_earnings, "earnings_2026-10-28.json"),
        ("econ_calendar", parse_econ, "econ_2026-10-28.json"),
    ]:
        raw = json.loads((Path(__file__).parent / "fixtures/a023" / day).read_text())
        rows = parser(raw, CLOCK.today_trade_date(), CLOCK)
        c.execute("SET LOCAL ROLE role_ingest")
        for row in rows:
            repo.write(name, row, update=("fetched_at",))
        c.execute("RESET ROLE")
        assert c.execute("SELECT count(*) n FROM ingest." + name).fetchone()["n"] > 0
        c.execute("SET LOCAL ROLE role_web")
        assert c.execute("SELECT count(*) n FROM ingest." + name).fetchone()["n"] > 0
        c.execute("RESET ROLE")
    for n in range(3):
        item = make_item(
            "news",
            "benzinga",
            "a023-sql-" + str(n),
            headline="Original title",
            body="Original body",
            clock=CLOCK,
            published_at=CLOCK.now_utc(),
            tickers=["GOOGL"],
        )
        item["extraction_source"] = {
            "news_rules": {"tags": ["earnings"]},
            "news_triage": {"retry_at": "9999-12-31T00:00:00+00:00"},
        }
        repo.put_info(item)
    assert repo.has_pending_info(as_of=CLOCK.now_utc(), include_news=False)
    assert repo.finish_pending_news(2, as_of=CLOCK.now_utc()) == 2
    assert repo.finish_pending_news(2, as_of=CLOCK.now_utc()) == 1
    assert repo.finish_pending_news(2, as_of=CLOCK.now_utc()) == 0
    rows = c.execute("SELECT * FROM ingest.info_items WHERE info_id LIKE 'news:benzinga:a023-sql-%'").fetchall()
    assert len(rows) == 3
    for r in rows:
        assert r["extraction_status"] == "ok" and r["body"] == "Original body"
        assert r["extraction_source"]["news_rules"] == {"tags": ["earnings"]}
        assert r["extraction_source"]["a023_previous_triage"]["retry_at"].startswith("9999")
        assert r["first_seen_at"] == CLOCK.now_utc()
    assert not repo.pending_info(32, as_of=CLOCK.now_utc(), include_news=False)
    from inves_cog.ingest.embedding_backfill import collect

    assert collect(c, "text-embedding-async-v1", include_news=False) == []
    assert collect(c, "text-embedding-async-v1", include_news=True)
    c.execute(
        "INSERT INTO trading.ledger (portfolio_id,trade_date,phase,extractor,rule_set,params_version,"
        "cash,peak_equity,state,observed_at) VALUES "
        "('paper-fixed','2026-10-23','plan','fixed','A','p-2026.10',100,100,%s,%s)",
        (json.dumps({"positions": {"ONE": {}, "TWO": {}}}), CLOCK.now_utc()),
    )
    assert set(repo.holding_tickers()) == {"ONE", "TWO"}


def test_a023_postgres_roles_queue_cleanup_embeddings_and_holdings(database):
    check_a023_database(database)


def check_calendar_reschedule(c):
    from datetime import date
    from inves_cog.ingest.resilience import parse_earnings, parse_econ

    repo = Repository(c)
    c.execute("SET LOCAL ROLE role_ingest")
    for table, parser, fixture in [
        ("earnings_calendar", parse_earnings, "earnings_2026-10-28.json"),
        ("econ_calendar", parse_econ, "econ_2026-10-28.json"),
    ]:
        raw = json.loads((Path(__file__).parent / "fixtures/a023" / fixture).read_text())
        rows = parser(raw, date(2026, 10, 28), CLOCK)[:1]
        repo.replace_calendar_day(table, date(2026, 10, 28), "Nasdaq", rows)
        # Another source's record must survive a Nasdaq refresh.
        other = [{**r, "source": "Other"} for r in rows]
        repo.replace_calendar_day(table, date(2026, 10, 28), "Other", other)
        moved = [
            {**r, ("report_date" if table == "earnings_calendar" else "event_date"): date(2026, 10, 30)} for r in rows
        ]
        repo.replace_calendar_day(table, date(2026, 10, 30), "Nasdaq", moved)
        repo.replace_calendar_day(table, date(2026, 10, 28), "Nasdaq", [])
        column = "report_date" if table == "earnings_calendar" else "event_date"
        actual = c.execute("SELECT " + column + " d,source FROM ingest." + table).fetchall()
        assert {(r["d"], r["source"]) for r in actual} == {
            (date(2026, 10, 28), "Other"),
            (date(2026, 10, 30), "Nasdaq"),
        }
    c.execute("RESET ROLE")


def test_a023_calendar_reschedule_removes_old_day_preserves_other_source(database):
    check_calendar_reschedule(database)
