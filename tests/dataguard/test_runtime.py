from datetime import date, datetime, timezone

import pytest

from inves_cog.dataguard.core import Expectation
from inves_cog.dataguard.daily import matrix, resource_log_summary
from inves_cog.dataguard.reader import read
from inves_cog.dataguard.recovery import ResourceState
from inves_cog.dataguard.service import dispatch

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 6, 22, tzinfo=timezone.utc)


def test_existing_worker_prevents_another_spawn_without_even_querying_database():
    class Child:
        def poll(self):
            return None

    class DB:
        def execute(self, *a):
            pytest.fail("queried while known child still running")

    child = Child()
    assert dispatch(DB(), [], NOW, detect_only=False, resources=ResourceState(), child=child) is child


def test_presence_uses_limited_per_key_index_seeks_not_entire_strike_aggregation():
    calls = []

    class Result:
        def fetchall(self):
            return []

    class DB:
        def execute(self, sql, args):
            calls.append((sql, args))
            return Result()

    item = Expectation(
        dataset="期权链",
        table="flows.option_chain",
        date_column="snapshot_at",
        deadline_et="16:30",
        timestamp=True,
        key_column="underlying",
        expected_keys=("SPX", "SPY"),
    )
    read(DB(), item, date(2026, 11, 5), date(2026, 11, 6), NOW)
    sql, args = calls[0]
    assert "JOIN LATERAL" in sql and "LIMIT %s" in sql
    assert "snapshot_at>=p.lo" in sql and "snapshot_at<p.hi" in sql and "underlying=p.key" in sql
    assert args[-1] == 1


def test_daily_matrix_does_not_call_unchecked_or_not_yet_due_data_complete():
    item = Expectation(dataset="波动率", table="flows.observations", date_column="obs_date", deadline_et="20:45")
    assert matrix([item], [], NOW)[0]["status"] == "unknown"
    assert matrix([item], [(item, {})], NOW)[0]["status"] == "not_due"


def test_resource_log_returns_counts_only_and_old_alarm_does_not_pause_today(tmp_path):
    path = tmp_path / "alerts.log"
    path.write_text(
        "2026-11-01T00:00:00Z memory password=private-fixture\n"
        "2026-11-06T21:00:00Z memory key=private-fixture\n"
        "2026-11-06T21:30:00Z io.pressure private-page-fixture\n"
    )
    text = resource_log_summary(path, NOW)
    assert "内存1条" in text and "IO1条" in text
    assert "private-fixture" not in text and "private-page" not in text
