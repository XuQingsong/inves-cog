from configparser import ConfigParser
from datetime import datetime, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from scripts.install_ingest_service import configuration

pytestmark = pytest.mark.phase1_blocking


def frozen(stamp):
    return FrozenClock(datetime.fromisoformat(stamp.replace("Z", "+00:00")))


@pytest.mark.parametrize("platform_name", ["Darwin", "Linux"])
def test_installer_registers_inputs_without_dropping_existing_sec_tasks(platform_name, monkeypatch):
    monkeypatch.setattr("scripts.install_ingest_service.platform.system", lambda: platform_name)
    config = ConfigParser(interpolation=None)
    config.read_string(configuration(Path("/fixture/inves-cog"), Path("/fixture/python")))
    command = config.get("program:scheduler", "command")
    for name in (
        "bars_prefill",
        "bars_full",
        "wide_universe",
        "sec_submissions",
        "sec_index",
        "sec_atom",
        "m6_market_inputs",
        "issuer_profiles",
    ):
        assert name in command
    assert "schedule_daily_modules.py" in config.get("program:daily_modules", "command")
    assert config.getboolean("program:daily_modules", "autostart")
    assert config.getboolean("program:daily_modules", "autorestart")
    assert config.get("program:embedding", "autorestart") == "unexpected"
    for name in ("scheduler", "daily_modules", "financials", "watchdog", "embedding", "morning_page"):
        assert config.has_section("program:" + name)
    assert "schedule_morning_page.py" in config.get("program:morning_page", "command")
    assert config.getboolean("program:morning_page", "autostart")
    assert config.getboolean("program:morning_page", "autorestart")
    assert config.has_section("program:awake") is (platform_name == "Darwin")
    for section in config.sections():
        if section.startswith("program:") and config.has_option(section, "environment"):
            assert config.get(section, "environment") == 'PYTHONUNBUFFERED="1"'


@pytest.mark.parametrize(
    "stamp,names",
    [
        ("2026-10-17T00:44:00Z", []),
        ("2026-10-17T00:45:00Z", ["market_structure"]),
        ("2026-10-17T02:29:00Z", ["market_structure"]),
        ("2026-10-17T02:30:00Z", ["market_structure", "rule_a_scores", "valuation_v1"]),
        ("2026-11-03T01:44:00Z", []),
        ("2026-11-03T01:45:00Z", ["market_structure"]),
        ("2026-11-03T03:30:00Z", ["market_structure", "rule_a_scores", "valuation_v1"]),
    ],
)
def test_module_poll_uses_et_boundaries_and_real_module_schedule_guards(stamp, names):
    from scripts.schedule_daily_modules import run_once

    calls = []

    def market(**kwargs):
        calls.append(("market_structure", kwargs))
        return {"status": "ok", "processed_count": 1}

    def scores(**kwargs):
        calls.append(("rule_a_scores", kwargs))
        return {"status": "ok", "processed_count": 2}

    def valuation(**kwargs):
        calls.append(("valuation_v1", kwargs))
        return {"status": "ok", "processed_count": 59}

    clock = frozen(stamp)
    result = run_once(
        clock=clock,
        values={},
        ready=lambda *args: True,
        market_run=market,
        score_run=scores,
        valuation_run=valuation,
    )
    assert list(result) == names
    assert [name for name, kwargs in calls] == names
    for name, kwargs in calls:
        assert kwargs["clock"] is clock
        if name != "valuation_v1":
            assert kwargs["schedule"] is True
            assert kwargs["day" if name == "market_structure" else "signal_date"] == clock.today_trade_date()


def test_module_poll_waits_for_inputs_and_financials_before_dispatch():
    from scripts.schedule_daily_modules import dependencies_met, run_once

    complete = {"status": "ok", "ended_at": datetime(2026, 10, 17, 0, tzinfo=timezone.utc)}
    records = {"bars_full": complete}
    assert not dependencies_met("market_structure", records)
    records["m6_market_inputs"] = complete
    assert dependencies_met("market_structure", records)
    assert not dependencies_met("rule_a_scores", records)
    records["financials"] = {**complete, "status": "running", "ended_at": None}
    assert not dependencies_met("rule_a_scores", records)
    records["financials"] = {**complete, "status": "degraded"}
    assert dependencies_met("rule_a_scores", records)
    result = run_once(
        clock=frozen("2026-10-17T02:30:00Z"),
        values={},
        ready=lambda *args: False,
        market_run=lambda **kw: pytest.fail("unready market task started"),
        score_run=lambda **kw: pytest.fail("unready scoring task started"),
    )
    assert all(row["status"] == "waiting_dependencies" for row in result.values())


def test_market_failure_does_not_prevent_ready_scoring():
    from scripts.schedule_daily_modules import run_once

    def fail(**kwargs):
        raise TimeoutError("recorded fixture interruption")

    result = run_once(
        clock=frozen("2026-10-17T02:30:00Z"),
        values={},
        ready=lambda *args: True,
        market_run=fail,
        score_run=lambda **kwargs: {"status": "ok", "processed_count": 59},
    )
    assert result["market_structure"] == {"status": "failed", "error_type": "TimeoutError"}
    assert result["rule_a_scores"]["status"] == "ok"


def test_module_poll_never_starts_on_weekend():
    from scripts.schedule_daily_modules import run_once

    result = run_once(
        clock=frozen("2026-10-18T02:30:00Z"),
        values={},
        ready=lambda *args: True,
        market_run=lambda **kw: pytest.fail("weekend market task started"),
        score_run=lambda **kw: pytest.fail("weekend scoring task started"),
    )
    assert result == {}
