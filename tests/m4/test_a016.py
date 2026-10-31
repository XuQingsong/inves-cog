"""A016: ET windows, real upstream completion and explicit input gaps."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.trading.execution import cli

NY = ZoneInfo("America/New_York")
pytestmark = pytest.mark.phase1_blocking


def by_source(result):
    return {row["source"]: row for row in result["sources"]}


def clock(day, hour, minute):
    return FrozenClock(datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=NY))


@pytest.mark.parametrize("day", ["2026-07-13", "2026-01-12"])
def test_e1_et_window_and_restart(day):
    for hour, minute, expected in [(8, 34, False), (8, 35, True), (9, 4, True), (9, 5, False)]:
        c = clock(day, hour, minute)
        assert cli.due(c) is expected
        assert not cli.due(c, last=c.now_utc())
    assert not cli.due(FrozenClock(datetime.fromisoformat(day).replace(hour=20, tzinfo=ZoneInfo("Asia/Shanghai"))))


def test_e2_only_real_success_before_now_is_ready():
    c = clock("2026-07-13", 8, 51)
    ended = clock("2026-07-13", 8, 50).now_utc()
    from inves_cog.trading.execution.cli import scores_ready

    assert scores_ready([{"status": "ok", "ended_at": ended}], c.now_utc())
    assert not scores_ready([{"status": "ok", "ended_at": ended}], clock("2026-07-13", 8, 49).now_utc())
    assert not scores_ready([{"status": "failed", "ended_at": ended}], c.now_utc())
    assert not scores_ready([{"status": "ok", "ended_at": None}], c.now_utc())


def test_e5_seven_sources_no_empty_insider_proof():
    from inves_cog.trading.execution.completeness import describe_inputs

    c = clock("2026-07-13", 8, 40)
    day = date(2026, 7, 10)
    inputs = {
        "bars": {"AAA": {day: {"open": 10, "close": 11}}},
        "signals": {"AAA": {day: {}}},
        "vix": {},
        "first_trade_dates": {"AAA": day},
    }
    plan = {"missing_scores": [], "missing_tickers": [], "overlay": {"status": "missing", "version": None}}
    result = describe_inputs(
        plan,
        inputs,
        [{"ticker": "AAA"}],
        signal_day=day,
        cutoff=c.now_utc(),
        insiders={},
        ledger=None,
        ledger_checked=True,
    )
    sources = by_source(result)
    assert set(sources) == {"scores", "bars", "vix", "membership", "insiders", "overlay", "ledger"}
    assert result["status"] == "degraded"
    for source in result["sources"]:
        assert {
            "status",
            "as_of",
            "required",
            "expected_count",
            "available_count",
            "missing",
            "fallback",
            "decision_effect",
        } <= source.keys()
        assert all({"ticker", "field", "reason"} <= gap.keys() for gap in source["missing"])
    assert sources["vix"]["status"] == "missing"
    assert sources["vix"]["fallback"] == "按非恐慌"
    assert sources["insiders"]["status"] == "unknown"
    assert sources["membership"]["status"] == "unknown"
    assert sources["overlay"]["decision_effect"] == "冷静期未生效"
    assert sources["ledger"]["status"] == "missing"


class Operations:
    def __init__(self):
        self.jobs, self.scores, self.sql = [], [], []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if "pg_try_advisory_lock" in sql:
            self.result = {"acquired": True}
        elif "pg_advisory_unlock" in sql:
            self.result = None
        elif "task_name='paper_plan'" in sql:
            self.result = self.jobs[0] if self.jobs else None
        elif "task_name='rule_a_scores'" in sql:
            assert params == (date(2026, 7, 10),)
            self.result = self.scores
        else:
            raise AssertionError(sql)
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def setup_scheduler(monkeypatch):
    db, calls = Operations(), []

    class Repository:
        def __init__(self, connection):
            self.connection = connection

        def write_job(self, row):
            row = dict(row)
            row["id"] = row.get("id", len(db.jobs) + 1)
            db.jobs[:] = [j for j in db.jobs if j["id"] != row["id"]] + [row]
            return row["id"]

        def health_rows(self):
            return {}

        def write_health(self, row):
            pass

    def plan(**kwargs):
        calls.append(kwargs)
        return {"published": True, "orders": [{"action": "buy"}], "missing_scores": [], "health_codes": []}

    monkeypatch.setattr(cli, "connect", lambda values: db)
    monkeypatch.setattr(cli, "OperationalRepository", Repository)
    monkeypatch.setattr(cli, "run_daily", plan)
    return db, calls


def test_e2_e4_wait_then_plan_once_across_restart(monkeypatch):
    db, calls = setup_scheduler(monkeypatch)
    for minute in [35, 40, 49, 50]:
        assert cli.scheduled(clock=clock("2026-07-13", 8, minute), values={})["status"] == "waiting_dependencies"
    assert not db.jobs and not calls
    db.scores = [{"status": "ok", "ended_at": clock("2026-07-13", 8, 50).now_utc()}]
    cli.scheduled(clock=clock("2026-07-13", 8, 51), values={})
    assert len(calls) == 1 and db.jobs[0]["status"] == "ok"
    assert cli.scheduled(clock=clock("2026-07-13", 8, 52), values={})["status"] == "already_attempted"
    # A new repository object on every call is the restarted process's persistent lookup.
    assert cli.scheduled(clock=clock("2026-07-13", 9, 0), values={})["status"] == "already_attempted"
    assert len(calls) == 1


def test_e2_deadline_failure_no_plan_or_duplicate(monkeypatch):
    db, calls = setup_scheduler(monkeypatch)
    assert cli.scheduled(clock=clock("2026-07-13", 9, 4), values={})["status"] == "waiting_dependencies"
    assert cli.scheduled(clock=clock("2026-07-13", 9, 5), values={})["status"] == "failed"
    assert not calls and len(db.jobs) == 1
    assert db.jobs[0]["error_summary"].startswith("skipped_upstream:")
    assert db.jobs[0]["trade_date"] == date(2026, 7, 13)
    assert cli.scheduled(clock=clock("2026-07-13", 9, 5), values={})["status"] == "already_attempted"


def test_e3_e6_actual_plan_unchanged_except_completeness(monkeypatch):
    from inves_cog.trading.engine import ExecutionEngine
    from inves_cog.trading.execution import service
    from tests.m4.test_execution import DAY, NEXT, signal

    c = clock("2026-01-12", 8, 40)
    universe = [{"ticker": "AAA", "listed_on": "2000-01-01"}]
    inputs = {
        "bars": {"AAA": {DAY: {"open": 100, "close": 100}}, "SPY": {DAY: {"open": 100, "close": 100}}},
        "signals": {"AAA": {DAY: signal()}},
        "vix": {},
        "vix_sources": {},
        "first_trade_dates": {"AAA": DAY},
        "score_source": "trading.daily_scores",
    }

    class Repository:
        def __init__(self, connection):
            pass

        def inputs(self, *args):
            return inputs

        def insider_events(self, day):
            return {}

    monkeypatch.setattr(service, "Repository", Repository)
    baseline = service.prepare(ExecutionEngine(clock=c), NEXT, inputs, universe)
    result = service.daily_plan(clock=c, connection=None, universe=universe, target=NEXT, persist=False)
    completeness = result.pop("input_completeness")
    assert result == baseline and result["orders"]
    assert by_source(completeness)["overlay"]["status"] == "missing"
    assert by_source(completeness)["overlay"]["decision_effect"] == "冷静期未生效"
    overlay = {
        "generated_at": clock("2026-01-12", 8, 20).now_utc(),
        "version": 7,
        "tickers": {},
        "m8_completeness": {"complete": True, "unknown": ["AAA"]},
    }
    with_overlay = service.daily_plan(
        clock=c, connection=None, universe=universe, target=NEXT, persist=False, overlay=overlay
    )
    assert with_overlay["overlay"]["version"] == 7
    assert by_source(with_overlay["input_completeness"])["overlay"]["status"] == "ok"
    assert by_source(with_overlay["input_completeness"])["overlay"]["m8_completeness"] == overlay["m8_completeness"]


def test_e2_outer_worker_does_not_hide_deadline():
    from scripts.schedule_daily_modules import run_once

    calls = []

    def paper_run(**kwargs):
        calls.append(kwargs)
        return {"status": "failed", "processed_count": 0}

    result = run_once(
        clock=clock("2026-07-13", 9, 5), values={}, ready=lambda *a: False, paper_run=paper_run, names=["paper_plan"]
    )
    assert result["paper_plan"]["status"] == "failed" and len(calls) == 1


def test_e7_add_only_m9_program_separate_migration():
    import configparser
    from pathlib import Path

    from scripts.install_ingest_service import configuration

    root = Path("/project")
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(configuration(root, root / ".venv/bin/python"))
    assert config["program:m9"]["command"].endswith("/project/scripts/schedule_m9.py")
    assert config["program:m9"]["autostart"] == "true"
    assert config["program:paper_plan"]["command"].endswith("--tasks paper_plan")
    programs = {s.removeprefix("program:") for s in config.sections() if s.startswith("program:")}
    assert programs - {"awake"} == {
        "m9",
        "scheduler",
        "stock_snapshots",
        "iex_snapshots",
        "macro_snapshots",
        "wide_snapshots",
        "daily_modules",
        "anomaly_daily",
        "valuation_v1",
        "consensus_snapshots",
        "paper_plan",
        "morning_page",
        "attribution_tracks",
        "attribution_labels",
        "financials",
        "watchdog",
        "embedding",
        "news_translate",
        "flows",
    }


def test_e3_late_overlay_not_consumed(tmp_path):
    import json

    target = date(2026, 7, 13)
    path = tmp_path / f"event_overlay_{target}.json"
    path.write_text(json.dumps({"version": 9, "generated_at": clock("2026-07-13", 8, 40).now_utc().isoformat()}))
    values = {"INVES_COG_OVERLAY_DIR": str(tmp_path)}
    assert cli.read_overlay(values, target, asof=clock("2026-07-13", 8, 35).now_utc()) is None
