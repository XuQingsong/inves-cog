"""Native-entry integration with the accepted M8 reader, entirely offline."""

from contextlib import contextmanager
from datetime import date, datetime

import psycopg
import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.snapshot import STAGES
from inves_cog.shadow.inputs import ReadInputs
from inves_cog.shadow.pipeline import MemoryOutputs, run_overlay

pytestmark = pytest.mark.phase1_blocking
TARGET = date(2026, 10, 21)
SOURCE_DAY = date(2026, 10, 20)
ENDED = datetime.fromisoformat("2026-10-21T01:30:00Z")
CLOCK = FrozenClock(datetime.fromisoformat("2026-10-21T12:15:00Z"))


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return next(iter(self.rows), None)


class Database:
    def __init__(self, kind, events=()):
        self.kind, self.events = kind, list(events)
        self.statements, self.depth, self.closed = [], 0, False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    @contextmanager
    def transaction(self):
        self.depth += 1
        try:
            yield self
        finally:
            self.depth -= 1

    def execute(self, statement, params=None):
        sql = " ".join(statement.split())
        self.statements.append((sql, params))
        if sql.startswith("BEGIN"):
            assert self.depth == 0, "provider must not roll back the main input transaction"
        if self.kind == "source" and "FROM ingest.job_runs" in sql:
            return Cursor(
                {"id": n, "task_name": name, "trade_date": SOURCE_DAY, "status": "ok", "ended_at": ENDED}
                for n, name in enumerate(STAGES, 1)
                if str(params[0]) == str(SOURCE_DAY)
            )
        if self.kind == "source" and "FROM perception.linkage_events" in sql:
            return Cursor(self.events)
        if self.kind == "operations":
            if "SELECT task_name,status,ended_at" in sql:
                return Cursor([{"task_name": "premarket_review", "status": "ok", "ended_at": ENDED}])
            if "pg_try_advisory_lock" in sql:
                return Cursor([{"acquired": True}])
        return Cursor()


def test_native_scheduled_default_reads_real_provider(monkeypatch, tmp_path):
    from inves_cog.shadow import cli

    data, source, operations = Database("data"), Database("source"), Database("operations")
    shadow_connections = iter([data, source])
    calls, jobs = [], []

    def connect(values):
        selected = values["INVES_COG_DATABASE_URL"]
        calls.append(selected)
        if selected == "synthetic-shadow":
            return next(shadow_connections)
        return operations if selected == "synthetic-operations" else Database("overlay")

    class Repository:
        def __init__(self, _):
            pass

        def health_rows(self):
            return {}

        def write_health(self, _):
            pass

        def write_job(self, row):
            jobs.append(dict(row))
            return 1

    store = MemoryOutputs(tmp_path)
    monkeypatch.setattr(cli, "connect", connect)
    monkeypatch.setattr(cli, "Operations", Repository)
    monkeypatch.setattr(cli, "DatabaseOutputs", lambda **_: store)
    result = cli.scheduled(
        clock=CLOCK,
        values={
            "INVES_COG_DATABASE_URL": "synthetic-operations",
            "INVES_COG_SHADOW_DATABASE_URL": "synthetic-shadow",
            "INVES_COG_OVERLAY_DATABASE_URL": "synthetic-overlay",
            "INVES_COG_OVERLAY_DIR": str(tmp_path),
        },
    )
    assert result["m9_overlay"]["status"] == "ok"
    assert len(store.overlays) == 1 and store.overlays[0]["tickers"] == {}
    assert store.overlays[0]["source_events_asof"] == ENDED.isoformat()
    assert result["m9_overlay"]["source_ids"]["jobs"][0]["id"] == 1
    assert calls.count("synthetic-shadow") == 2 and source.closed
    statements = " ".join(sql for sql, _ in source.statements)
    assert "REPEATABLE READ READ ONLY" in statements and "ROLLBACK" in statements
    assert not any(word in statements for word in ("SET ROLE", "INSERT", "UPDATE"))
    assert [row["status"] for row in jobs] == ["running", "ok"]


def test_m8_reader_uses_closed_input_day_and_keeps_source_ids():
    calls = []

    def provider(day, cutoff):
        calls.append((day, cutoff))
        return {"complete": False, "events": [], "source_ids": {"jobs": [{"id": 17}]}}

    bundle = ReadInputs(Database("data"), m8_provider=provider).load(clock=CLOCK, target=TARGET, tickers=[])
    assert calls == [(SOURCE_DAY, CLOCK.now_utc())]
    assert bundle["source_ids"]["m8"]["jobs"] == [{"id": 17}]
    assert bundle["source_ids"]["m8_trade_date"] == str(SOURCE_DAY)


def test_incomplete_native_event_keeps_old_overlay_and_reports_fields(monkeypatch, tmp_path):
    from inves_cog.shadow import cli

    source = Database(
        "source",
        [
            {
                "event_id": "synthetic-event",
                "anomaly_id": "synthetic-anomaly",
                "generated_at": ENDED,
                "history": [{"at": ENDED.isoformat(), "new": "市场确认", "evidence_ids": ["synthetic-info"]}],
            }
        ],
    )
    monkeypatch.setattr(cli, "_scoped", lambda *_: source)
    snapshot = cli._read_m8({}, SOURCE_DAY, CLOCK.now_utc())
    store = MemoryOutputs(tmp_path)
    old = run_overlay(
        clock=CLOCK,
        target=TARGET,
        source={"complete": True, "events": [], "source_events_asof": ENDED.isoformat()},
        outputs=store,
    )["overlay"]
    result = run_overlay(clock=CLOCK, target=TARGET, source=snapshot, outputs=store)
    assert result["status"] == "degraded" and result["overlay"] == old and len(store.overlays) == 1
    assert "mechanism" in result["missing"]["fields"] and "affected" in result["missing"]["fields"]
    assert "mechanism" in result["note"] and result["source_ids"]["events"][0]["event_id"] == "synthetic-event"


def test_reader_permission_failure_stays_unknown_without_role_fallback(monkeypatch):
    from inves_cog.shadow import cli

    selected = []

    def denied(values, key):
        selected.append(key)
        raise psycopg.errors.InsufficientPrivilege("synthetic denied; do not expose database text")

    monkeypatch.setattr(cli, "_scoped", denied)
    result = cli._read_m8({}, SOURCE_DAY, CLOCK.now_utc())
    assert result["complete"] is False and result["source_events_asof"] is None and result["events"] == []
    assert result["missing"]["reader"] == "InsufficientPrivilege"
    assert selected == ["INVES_COG_SHADOW_DATABASE_URL"]
    assert "do not expose" not in str(result)
