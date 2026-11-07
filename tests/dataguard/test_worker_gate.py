import contextlib
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from inves_cog.dataguard import worker
from inves_cog.dataguard.recovery import ResourceState

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 6, 22, tzinfo=timezone.utc)


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []


def _setup(monkeypatch, *, switch, runtime_row):
    attempts = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def transaction(self):
            return contextlib.nullcontext()

        def execute(self, sql, args=()):
            if "pg_try_advisory_lock" in sql:
                return _Result({"ok": True})
            if "data_guard_runtime" in sql:
                return _Result(runtime_row)
            if "data_gaps" in sql:
                return _Result(
                    {
                        "dataset": "测试集",
                        "data_date": date(2026, 11, 5),
                        "kind": "missing",
                        "status": "open",
                        "attempts": 0,
                        "generation": 0,
                        "detail": {},
                    }
                )
            if "job_runs" in sql:
                return _Result(None)
            raise AssertionError("unexpected query: " + sql)

    conn = Conn()
    item = SimpleNamespace(
        dataset="测试集",
        table="flows.example",
        scope=None,
        backfill={"entry": "no_such_entry", "max_attempts": 3},
    )
    monkeypatch.setattr(worker, "connect", lambda values, writer=False: conn)
    monkeypatch.setattr(worker, "load_values", lambda: {"INVES_DATAGUARD_BACKFILL": switch})
    monkeypatch.setattr(worker, "load", lambda path: ({}, [item]))
    monkeypatch.setattr(worker, "SystemClock", lambda: SimpleNamespace(now_utc=lambda: NOW))
    monkeypatch.setattr(worker, "eligible", lambda *a, **k: True)
    monkeypatch.setattr(worker, "slice_resources", lambda: ResourceState())
    monkeypatch.setattr(worker, "attempt", lambda *a, **k: attempts.append("attempt"))
    monkeypatch.setattr(worker.signal, "signal", lambda *a: None)
    monkeypatch.setattr(worker.signal, "alarm", lambda *a: None)
    monkeypatch.setattr(worker.os, "nice", lambda *a: None)
    monkeypatch.setattr(worker.resource, "setrlimit", lambda *a: None)
    monkeypatch.setattr(sys, "argv", ["worker", "--dataset", "测试集", "--date", "2026-11-05", "--kind", "missing"])
    return attempts


def test_worker_recovers_within_first_day_when_backfill_enabled(monkeypatch):
    """Switch=1 dispatches even when first_started_at is less than a day old."""
    attempts = _setup(
        monkeypatch,
        switch="1",
        runtime_row={"first_started_at": NOW - timedelta(hours=1), "detect_only": False},
    )
    worker.main()
    assert attempts == ["attempt"]


def test_worker_never_recovers_when_backfill_disabled(monkeypatch):
    """Switch=0 never dispatches, regardless of runtime age."""
    attempts = _setup(
        monkeypatch,
        switch="0",
        runtime_row={"first_started_at": NOW - timedelta(days=30), "detect_only": False},
    )
    worker.main()
    assert attempts == []


def test_worker_respects_stored_detect_only_runtime(monkeypatch):
    """Switch=1 but the stored runtime is still detect-only -> no dispatch."""
    attempts = _setup(
        monkeypatch,
        switch="1",
        runtime_row={"first_started_at": NOW - timedelta(days=30), "detect_only": True},
    )
    worker.main()
    assert attempts == []
