"""A024 contract from recorded Alpaca SPY responses; no network or models."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks

pytestmark = pytest.mark.phase1_blocking
FIXTURES = Path(__file__).parent / "fixtures/a024"
CLOCK = FrozenClock(datetime(2026, 10, 26, 12, 4, 30, tzinfo=timezone.utc))


def sample(name):
    return json.loads((FIXTURES / name).read_text())


def test_a024_recorded_snapshot_actual_timestamp_delay_and_adjusted_previous_close():
    from inves_cog.ingest.intraday import parse_snapshots

    rows = parse_snapshots(sample("spy_snapshot.json"), {"SPY": 759.97}, ["SPY"], CLOCK)
    assert len(rows) == 1
    row = rows[0]
    assert row["last"] == 761.53 and row["prev_close"] == 759.97
    assert row["as_of"].isoformat().startswith("2026-10-26T11:49:21.288507")
    assert row["fetched_at"] == CLOCK.now_utc() and row["as_of"] != row["fetched_at"]
    assert row["session"] == "pre" and row["delay_minutes"] == 16
    assert row["source"] == "Alpaca:delayed_sip"


@pytest.mark.parametrize(
    "hour,minute,expected",
    [(13, 29, "pre"), (13, 30, "regular"), (19, 59, "regular"), (20, 0, "post"), (23, 59, "post")],
)
def test_a024_session_uses_trade_time_not_fetch_time(hour, minute, expected):
    from inves_cog.ingest.intraday import parse_snapshots

    raw = sample("spy_snapshot.json")
    stamp = datetime(2026, 10, 26, hour, minute, tzinfo=timezone.utc)
    raw["SPY"]["latestTrade"]["t"] = stamp.isoformat()
    clock = FrozenClock(stamp + timedelta(minutes=16))
    assert parse_snapshots(raw, {}, ["SPY"], clock)[0]["session"] == expected


def test_a024_never_fabricates_previous_day_or_future_trade():
    from inves_cog.ingest.intraday import parse_snapshots

    raw = sample("spy_snapshot.json")
    raw["SPY"]["latestTrade"]["t"] = "2026-10-23T19:59:00Z"
    assert parse_snapshots(raw, {}, ["SPY"], CLOCK) == []
    raw["SPY"]["latestTrade"]["t"] = "2026-10-26T12:05:00Z"
    assert parse_snapshots(raw, {}, ["SPY"], CLOCK) == []
    raw["SPY"]["latestTrade"]["p"] = 0
    assert parse_snapshots(raw, {}, ["SPY"], CLOCK) == []


@pytest.mark.parametrize(
    "local,elapsed,due",
    [
        ("2026-10-26T03:59:00-04:00", None, False),
        ("2026-10-26T04:00:00-04:00", None, True),
        ("2026-10-26T04:29:00-04:00", 10, False),
        ("2026-10-26T04:30:00-04:00", 10, True),
        ("2026-10-26T09:30:00-04:00", 10, True),
        ("2026-10-26T15:59:00-04:00", 10, False),
        ("2026-10-26T16:00:00-04:00", 10, True),
        ("2026-10-26T16:30:00-04:00", 10, False),
        ("2026-10-26T17:00:00-04:00", 10, True),
        ("2026-10-26T20:00:00-04:00", None, False),
        ("2026-10-24T10:00:00-04:00", None, False),
        ("2026-12-25T10:00:00-05:00", None, False),
        ("2026-11-02T04:30:00-05:00", 10, True),
    ],
)
def test_a024_frequency_sessions_weekends_holidays_and_dst(local, elapsed, due):
    clock = FrozenClock(datetime.fromisoformat(local))
    last = {} if elapsed is None else {"intraday_snapshots": clock.now_utc() - timedelta(minutes=elapsed)}
    assert ("intraday_snapshots" in due_tasks(clock, last)) == due


def test_a024_collect_scope_consistent_adjustment_and_partial_health():
    from inves_cog.ingest.intraday import collect_intraday

    repo = Mock()
    repo.holding_tickers.return_value = ["OUTSIDE", "SPY"]
    p = SimpleNamespace(repo=repo, clock=CLOCK, stocks=["GOOGL", "SPY"], alpaca=SimpleNamespace(headers={}))
    http = Mock()
    http.get.side_effect = [sample("spy_snapshot.json"), sample("spy_previous_all.json")]
    result = collect_intraday(p, http=http)
    assert result["processed_count"] == 1 and result["status"] == "degraded"
    first, second = http.get.call_args_list
    assert first.kwargs["params"]["symbols"] == "GOOGL,IWM,OUTSIDE,QQQ,SPY"
    assert first.kwargs["params"]["feed"] == "delayed_sip"
    assert second.kwargs["params"]["adjustment"] == "all" and second.kwargs["params"]["asof"] == "2026-10-26"
    assert second.kwargs["params"]["start"].startswith("2026-10-23")
    assert second.kwargs["params"]["end"].startswith("2026-10-24")
    repo.cleanup_intraday.assert_called_once_with(CLOCK.now_utc() - timedelta(days=30))
    assert repo.write.call_args.args[0] == "intraday_snapshots"
    assert repo.write.call_args.args[1]["prev_close"] == 759.97


def test_a024_failure_no_http_retry_and_persisted_health(monkeypatch):
    from inves_cog.ingest.intraday import collect_intraday

    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.jobs import HealthBook, JobRunner

    send = Mock(return_value=Response(403, {"message": "not available"}))
    made = []

    def client(**kwargs):
        made.append(kwargs)
        return HTTPClient(send=send, **kwargs)

    monkeypatch.setattr("inves_cog.ingest.intraday.HTTPClient", client)
    repo = Mock()
    repo.holding_tickers.return_value = []
    p = SimpleNamespace(repo=repo, clock=CLOCK, stocks=[], alpaca=SimpleNamespace(headers={}))
    health = HealthBook(clock=CLOCK, persist=repo.write_health)
    runner = JobRunner(clock=CLOCK, health=health, persist=repo.write_job)
    runner.run("intraday_snapshots", "AlpacaIntraday", lambda: collect_intraday(p))
    assert made[0]["retries"] == 0 and send.call_count == 1
    row = repo.write_health.call_args.args[0]
    assert row["source"] == "AlpacaIntraday" and row["status"] != "ok" and row["consecutive_failures"] == 1
    repo.write.assert_not_called()
