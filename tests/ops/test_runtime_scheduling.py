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
