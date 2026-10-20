"""A014: real clocks, persisted dependency days and isolated existing entry points."""

from datetime import date, datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from scripts import schedule_daily_modules as schedule

pytestmark = pytest.mark.phase1_blocking


def clock(stamp):
    return FrozenClock(datetime.fromisoformat(stamp.replace("Z", "+00:00")))


def probe(stamp, ready=lambda *args: True, failure=None):
    calls = []

    def operation(name):
        def run(**kwargs):
            calls.append((name, kwargs))
            if name == failure:
                raise ValueError("private fixture value must not be logged")
            return {"status": "ok", "processed_count": 4, "plan": {"private": "must not be logged"}}

        return run

    result = schedule.run_once(
        clock=clock(stamp),
        values={},
        ready=ready,
        market_run=operation("market_structure"),
        score_run=operation("rule_a_scores"),
        anomaly_run=operation("anomaly_daily"),
        valuation_run=operation("valuation_v1"),
        paper_run=operation("paper_plan"),
        premarket_run=operation("premarket_review"),
    )
    assert "private" not in str(result)
    return result, calls


@pytest.mark.parametrize(
    "stamp,names",
    [
        ("2026-10-21T00:54:59Z", ["market_structure"]),
        ("2026-10-21T00:55:00Z", ["market_structure", "anomaly_daily"]),
        ("2026-10-21T01:00:00Z", ["market_structure"]),
        ("2026-10-21T02:30:00Z", ["market_structure", "rule_a_scores", "valuation_v1"]),
        ("2026-11-03T01:55:00Z", ["market_structure", "anomaly_daily"]),
        ("2026-11-03T03:30:00Z", ["market_structure", "rule_a_scores", "valuation_v1"]),
        ("2026-10-20T11:59:59Z", []),
        ("2026-10-20T12:00:00Z", ["premarket_review", "paper_plan"]),
        ("2026-10-20T12:30:00Z", []),
        ("2026-11-03T12:00:00Z", ["paper_plan"]),
        ("2026-11-03T13:00:00Z", ["premarket_review"]),
        ("2026-10-18T12:00:00Z", []),
    ],
)
def test_a014_runtime_windows_and_dst(stamp, names):
    result, calls = probe(stamp)
    assert list(result) == names
    assert [name for name, _ in calls] == names
    for name, kwargs in calls:
        assert kwargs["clock"].now_utc() == clock(stamp).now_utc()
        assert kwargs["values"] == {}
        if name in {"market_structure", "rule_a_scores"}:
            assert kwargs["schedule"] is True
        else:
            assert set(kwargs) == {"clock", "values"}


def test_a014_paper_uses_previous_session_scores_and_current_premarket_inputs():
    seen = []

    def ready(name, day):
        seen.append((name, day))
        return False

    result, calls = probe("2026-10-19T12:00:00Z", ready=ready)
    assert seen == [("premarket_review", date(2026, 10, 19)), ("paper_plan", date(2026, 10, 16))]
    assert calls == []
    assert all(row["status"] == "waiting_dependencies" for row in result.values())


def test_a014_dependencies_both_reject_incomplete_and_allow_degraded_finished():
    done = {"status": "degraded", "ended_at": datetime(2026, 10, 20, tzinfo=timezone.utc)}
    cases = {
        "anomaly_daily": {"bars_full": done, "market_structure": done},
        "valuation_v1": {"bars_full": done, "m2_financials": done},
        "paper_plan": {"rule_a_scores": done},
        "premarket_review": {"bars_prefill": done},
    }
    for name, records in cases.items():
        assert schedule.dependencies_met(name, records)
        for task in records:
            assert not schedule.dependencies_met(name, {**records, task: {"status": "running", "ended_at": None}})
            assert not schedule.dependencies_met(name, {**records, task: {**done, "status": "failed"}})


def test_a014_valuation_failure_does_not_suppress_paper_or_anomaly_dispatch():
    result, calls = probe("2026-10-20T12:00:00Z", failure="premarket_review")
    assert result["premarket_review"] == {"status": "failed", "error_type": "ValueError"}
    assert result["paper_plan"]["status"] == "ok"
    assert [name for name, _ in calls] == ["premarket_review", "paper_plan"]


def test_a014_m7_dispatch_uses_own_login_and_existing_recorded_guard(monkeypatch):
    from scripts.schedule_daily_modules import run_anomalies

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement, params=None):
            assert "job_runs" in statement
            return self

        def fetchone(self):
            return {"id": 123, "status": "failed"}

    seen = []

    def connect(values):
        seen.append(values["INVES_COG_DATABASE_URL"])
        return Connection()

    monkeypatch.setattr(schedule, "connect", connect)
    assert run_anomalies(
        clock=clock("2026-10-21T00:55:00Z"),
        values={
            "INVES_COG_DATABASE_URL": "operations-fixture",
            "INVES_COG_PERCEPTION_DATABASE_URL": "perception-fixture",
        },
    ) == {"status": "already_attempted"}
    assert seen == ["perception-fixture"]


def test_a014_m7_missing_writer_fails_closed_without_borrowing_admin(monkeypatch):
    from scripts.schedule_daily_modules import run_anomalies

    monkeypatch.setattr(schedule, "connect", lambda _: pytest.fail("must not use another role"))
    with pytest.raises(ValueError, match="INVES_COG_PERCEPTION_DATABASE_URL"):
        run_anomalies(clock=clock("2026-10-21T00:55:00Z"), values={"INVES_COG_DATABASE_URL": "operations"})


def test_a014_preserves_accepted_m4_beijing_window_without_changing_business_guard():
    from inves_cog.trading.execution.cli import due

    assert due(clock("2026-11-03T12:00:00Z"))
    assert not due(clock("2026-11-03T13:00:00Z"))
    assert [name for name, _ in probe("2026-11-03T12:00:00Z")[1]] == ["paper_plan"]


def test_a014_valuation_failure_does_not_suppress_completed_scoring():
    result, calls = probe("2026-10-21T02:30:00Z", failure="valuation_v1")
    assert result["valuation_v1"] == {"status": "failed", "error_type": "ValueError"}
    assert result["rule_a_scores"]["status"] == "ok"
    assert len(calls) == 3


def test_a014_installer_lists_three_workers_without_duplicate_module_dispatch():
    import shlex
    from configparser import ConfigParser
    from pathlib import Path

    from scripts.install_ingest_service import configuration

    config = ConfigParser(interpolation=None)
    config.read_string(configuration(Path("/fixture/project"), Path("/fixture/python")))
    expected = {
        "daily_modules": ["market_structure", "rule_a_scores"],
        "anomaly_daily": ["anomaly_daily", "premarket_review"],
        "valuation_v1": ["valuation_v1"],
        "paper_plan": ["paper_plan"],
    }
    for name, tasks in expected.items():
        section = "program:" + name
        words = shlex.split(config.get(section, "command"))
        assert words[words.index("--tasks") + 1 :] == tasks
        assert config.getboolean(section, "autostart")
        assert config.getboolean(section, "autorestart")


def test_a014_worker_filter_never_calls_other_modules():
    result = schedule.run_once(
        clock=clock("2026-10-21T02:30:00Z"),
        values={},
        names=["valuation_v1"],
        ready=lambda *args: True,
        score_run=lambda **kwargs: pytest.fail("worker must not dispatch another module"),
        valuation_run=lambda **kwargs: {"status": "ok"},
    )
    assert result == {"valuation_v1": {"status": "ok"}}


class RecordedConnection:
    def __init__(self):
        self.statements = []
        self.job = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        if "INSERT INTO ingest.job_runs" in statement:
            self.job = {"id": 42, "status": "failed"}
        if "UPDATE ingest.job_runs" in statement and params:
            if "status = %s" in statement:
                self.job["status"] = params[1]
        return self

    def fetchone(self):
        return self.job


def test_a014_m7_records_close_and_post_and_does_not_repeat_after_restart(monkeypatch):
    from inves_cog.perception.anomaly import database, service

    connection = RecordedConnection()
    monkeypatch.setattr(schedule, "connect", lambda _: connection)
    detected, written = [], []

    class Panel:
        def detect(self, day, session):
            detected.append((day, session))
            return [
                {"session": session, "entry_paths": ["B"], "data_quality": ["thin_post"] if session == "post" else []}
            ]

    monkeypatch.setattr(database.DatabasePanel, "from_connection", lambda *args, **kwargs: Panel())
    monkeypatch.setattr(service, "write_anomalies", lambda _, rows: written.extend(rows))
    values = {"INVES_COG_PERCEPTION_DATABASE_URL": "perception-fixture"}
    injected = clock("2026-10-21T00:55:00Z")
    result = schedule.run_anomalies(clock=injected, values=values)
    assert result == {"status": "ok", "job_id": 42, "entry_paths": {"B": 2}, "data_quality": {"thin_post": 1}}
    assert detected == [(date(2026, 10, 20), "close"), (date(2026, 10, 20), "post")]
    assert [row["anomaly_id"] for row in written] == ["2026-10-20:close:001", "2026-10-20:post:001"]
    start = next(params for query, params in connection.statements if "INSERT INTO ingest.job_runs" in query)
    assert start[2] == injected.now_utc()
    assert schedule.run_anomalies(clock=injected, values=values) == {"status": "already_attempted"}
    assert len(detected) == 2


def test_a014_m7_failed_attempt_is_recorded_and_not_silently_retried(monkeypatch):
    from inves_cog.perception.anomaly import database

    connection = RecordedConnection()
    monkeypatch.setattr(schedule, "connect", lambda _: connection)

    def interrupted(*args, **kwargs):
        raise ValueError("recorded input failure")

    monkeypatch.setattr(database.DatabasePanel, "from_connection", interrupted)
    values = {"INVES_COG_PERCEPTION_DATABASE_URL": "perception-fixture"}
    with pytest.raises(ValueError, match="recorded input failure"):
        schedule.run_anomalies(clock=clock("2026-10-21T00:55:00Z"), values=values)
    assert connection.job["status"] == "failed"
    assert any("UPDATE ingest.job_runs" in statement for statement, _ in connection.statements)
    assert schedule.run_anomalies(clock=clock("2026-10-21T00:55:30Z"), values=values) == {"status": "already_attempted"}


def test_a014_premarket_adapter_only_uses_scoped_visible_quotes_and_reports_gaps():
    class Connection:
        def __init__(self):
            self.index = -1
            self.statements = []

        def execute(self, statement, params):
            self.index += 1
            self.statements.append((statement, params))
            return self

        def fetchone(self):
            return {"state": {"positions": {"NVDA": {}, "MU": {}}}}

        def fetchall(self):
            if self.index == 1:
                return [{"ticker": "AMD"}]
            return [
                {"ticker": "NVDA", "prev_close": 100, "premarket_last": 105, "sigma": 0.01},
                {"ticker": "MU", "prev_close": 100, "premarket_last": 101, "sigma": None},
            ]

    db = Connection()
    injected = clock("2026-10-20T12:00:00Z")
    scope, missing = schedule.premarket_scope(db, clock=injected)
    assert scope["holdings"] == ["MU", "NVDA"] and scope["linked"] == ["AMD"]
    assert set(scope["quotes"]) == {"NVDA"} and missing == ["AMD", "MU"]
    statement, params = db.statements[-1]
    assert "m.ts_utc<=%s" in statement and "m.session='pre'" in statement
    assert params[:2] == (date(2026, 10, 19), date(2026, 10, 19))
    assert params[3] == injected.now_utc()
    assert "基本面核查中" in db.statements[1][0]


def test_a014_m7_rejects_missing_current_marketstate_even_if_job_was_finished(monkeypatch):
    from inves_cog.perception.anomaly import database

    class MissingMarket(RecordedConnection):
        def fetchone(self):
            if 'marketstate.market' in self.statements[-1][0]:
                return None
            return self.job

    connection = MissingMarket()
    monkeypatch.setattr(schedule, 'connect', lambda _: connection)
    monkeypatch.setattr(database.DatabasePanel, 'from_connection', lambda *args, **kwargs: pytest.fail('missing structure'))
    with pytest.raises(ValueError, match='marketstate'):
        schedule.run_anomalies(
            clock=clock('2026-10-21T00:55:00Z'), values={'INVES_COG_PERCEPTION_DATABASE_URL': 'fixture'},
        )
    assert connection.job['status'] == 'failed'
