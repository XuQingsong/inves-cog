import shlex
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks
from scripts.install_ingest_service import configuration

pytestmark = pytest.mark.phase1_blocking
ORIGINAL = [
    "bars_prefill",
    "bars_full",
    "wide_universe",
    "sec_submissions",
    "sec_index",
    "sec_atom",
    "m6_market_inputs",
    "issuer_profiles",
]
ADDED = ["news_prefill", "news_full", "fred", "cboe", "finra", "fed_news"]


@pytest.mark.parametrize("platform_name", ["Linux", "Darwin"])
def test_n1_scheduler_exact_tasks_and_other_programs_unchanged(platform_name, monkeypatch):
    monkeypatch.setattr("scripts.install_ingest_service.platform.system", lambda: platform_name)
    root, python = Path("/fixture/inves-cog"), Path("/fixture/python")
    config = ConfigParser(interpolation=None)
    config.read_string(configuration(root, python))
    command = shlex.split(config["program:scheduler"]["command"])
    assert command == [str(python), "-u", "-m", "inves_cog.ingest.cli", "schedule", "--tasks", *ORIGINAL, *ADDED]
    expected = {
        "daily_modules": ["scripts/schedule_daily_modules.py", "--tasks", "market_structure", "rule_a_scores"],
        "anomaly_daily": ["scripts/schedule_daily_modules.py", "--tasks", "anomaly_daily", "premarket_review"],
        "valuation_v1": ["scripts/schedule_daily_modules.py", "--tasks", "valuation_v1"],
        "consensus_snapshots": ["scripts/schedule_consensus.py"],
        "paper_plan": ["scripts/schedule_daily_modules.py", "--tasks", "paper_plan"],
        "m9": ["scripts/schedule_m9.py"],
        "morning_page": ["scripts/schedule_morning_page.py"],
        "attribution_tracks": ["scripts/schedule_attribution_stage.py", "--task", "attribution_tracks"],
        "attribution_labels": ["scripts/schedule_attribution_stage.py", "--task", "attribution_labels"],
        "financials": ["scripts/schedule_financials.py"],
        "watchdog": ["-m", "inves_cog.ingest.service"],
        "embedding": ["-m", "inves_cog.ingest.embedding_backfill", "--model", "text-embedding-async-v1"],
    }
    programs = {name.removeprefix("program:") for name in config.sections() if name.startswith("program:")}
    assert programs == {"scheduler", *expected} | ({"awake"} if platform_name == "Darwin" else set())
    for name, args in expected.items():
        args = [str(root / args[0]), *args[1:]] if args[0].startswith("scripts/") else args
        section = config["program:" + name]
        assert shlex.split(section["command"]) == [str(python), "-u", *args]
        assert section["autorestart"] == ("unexpected" if name == "embedding" else "true")
        assert section["environment"] == 'PYTHONUNBUFFERED="1"'


@pytest.mark.parametrize("day", ["2026-10-26", "2026-11-02", "2026-10-24"])
@pytest.mark.parametrize(
    "clock_time,expected",
    [
        ("07:59", set()),
        ("08:00", {"news_prefill"}),
        ("08:09", {"news_prefill"}),
        ("08:10", set()),
        ("20:19", set()),
        ("20:20", {"news_full"}),
        ("20:44", {"news_full"}),
        ("20:45", {"news_full", "fred", "cboe", "finra", "fed_news"}),
    ],
)
def test_n2_existing_et_windows_dst_and_non_session(day, clock_time, expected):
    moment = datetime.fromisoformat(day + "T" + clock_time).replace(tzinfo=ZoneInfo("America/New_York"))
    clock = FrozenClock(moment)
    assert set(due_tasks(clock, {})) & set(ADDED) == expected
    # Existing sources also run on non-session dates; same-day persisted starts prevent duplicates.
    assert not (set(due_tasks(clock, {task: moment for task in ADDED})) & set(ADDED))
