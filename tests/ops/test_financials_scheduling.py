"""Register only the authorized M2 financial update, without Yahoo side effects."""

import ast
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from scripts.install_ingest_service import configuration

pytestmark = pytest.mark.phase1_blocking


def test_installer_registers_restarting_financials_only_service():
    config = ConfigParser(interpolation=None)
    config.read_string(configuration(Path("/fixture/root"), Path("/fixture/python")))
    assert "schedule_financials.py" in config.get("program:financials", "command")
    assert config.getboolean("program:financials", "autostart")
    assert config.getboolean("program:financials", "autorestart")


@pytest.mark.parametrize(
    "stamp,ready",
    [
        ("2026-10-17T01:14:59+00:00", False),
        ("2026-10-17T01:15:00+00:00", True),
        ("2026-10-17T01:44:59+00:00", True),
        ("2026-10-17T01:45:00+00:00", False),
        ("2026-11-03T02:15:00+00:00", True),
        ("2026-10-18T01:15:00+00:00", False),
    ],
)
def test_financials_slot_et_dst_and_no_repeat(stamp, ready):
    from scripts.schedule_financials import due

    clock = FrozenClock(datetime.fromisoformat(stamp))
    assert due(clock) == ready
    assert not due(clock, clock.now_utc())


def test_financials_dispatch_uses_existing_m2_runner_and_only_financials():
    from scripts.schedule_financials import run_once

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, *args):
            return self

        def fetchone(self):
            return None

    calls = []
    clock = FrozenClock(datetime.fromisoformat("2026-10-17T01:15:00+00:00"))

    def build(**kwargs):
        return None, "existing-runner", {"financials": "existing-task"}, None

    def dispatch(**kwargs):
        calls.append(kwargs)
        return {"financials": {"status": "ok", "processed_count": 59}}

    result = run_once(clock=clock, values={}, connect=lambda values: Connection(), build=build, dispatch=dispatch)
    assert result["financials"]["processed_count"] == 59
    assert calls == [
        {"clock": clock, "runner": "existing-runner", "tasks": {"financials": "existing-task"}, "names": ["financials"]}
    ]

    class Completed(Connection):
        def fetchone(self):
            return {"started_at": clock.now_utc()}

    assert (
        run_once(
            clock=clock,
            values={},
            connect=lambda values: Completed(),
            build=lambda **kw: pytest.fail("repeated build"),
            dispatch=dispatch,
        )["status"]
        == "not_due"
    )


def test_financials_failure_logs_the_full_traceback(monkeypatch, capsys):
    import json

    import scripts.schedule_financials as module

    monkeypatch.setattr(module, "SystemClock", lambda: FrozenClock(datetime.fromisoformat("2026-10-17T01:15:00+00:00")))
    monkeypatch.setattr(module, "read_environment", lambda: {})

    def fail(**kwargs):
        raise ValueError("financials fixture")

    def stop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(module, "run_once", fail)
    monkeypatch.setattr(module.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        module.main()

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "failed", "error_type": "ValueError"}
    assert "Traceback (most recent call last):" in captured.err
    assert "financials fixture" in captured.err


def test_resident_schedule_failure_handlers_print_tracebacks():
    scripts = (
        "schedule_attribution_stage.py",
        "schedule_consensus.py",
        "schedule_daily_modules.py",
        "schedule_financials.py",
        "schedule_flows.py",
        "schedule_m9.py",
        "schedule_morning_page.py",
        "schedule_review.py",
        "schedule_translate.py",
    )
    root = Path(__file__).resolve().parents[2]
    for name in scripts:
        path = root / "scripts" / name
        tree = ast.parse(path.read_text(), filename=str(path))
        handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
        typed = [
            handler
            for handler in handlers
            if "type(exc).__name__" in (ast.get_source_segment(path.read_text(), handler) or "")
        ]
        assert typed, name
        for handler in typed:
            source = ast.get_source_segment(path.read_text(), handler) or ""
            assert "traceback.print_exc()" in source, f"{name}:{handler.lineno}"
