"""A025 minute/overnight observations: injected clocks, recorded quotes, no network."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks

pytestmark = pytest.mark.phase1_blocking


@pytest.mark.parametrize(
    "moment,stock,macro,wide",
    [
        ("2026-10-27T04:01:00-04:00", True, True, False),
        ("2026-10-27T09:35:00-04:00", True, True, True),
        ("2026-10-27T16:01:00-04:00", True, True, False),
        ("2026-10-27T20:15:00-04:00", False, True, False),
        ("2026-10-28T03:15:00-04:00", False, True, False),
        ("2026-10-24T20:15:00-04:00", False, True, False),
        ("2026-11-02T04:01:00-05:00", True, True, False),
    ],
)
def test_schedule_each_minute_and_overnight_quarter_hour(moment, stock, macro, wide):
    c = FrozenClock(datetime.fromisoformat(moment))
    last = {n: c.now_utc() - timedelta(minutes=1) for n in ("intraday_snapshots", "yahoo_intraday", "wide_snapshots")}
    tasks = due_tasks(c, last)
    assert ("intraday_snapshots" in tasks) == stock
    assert ("yahoo_intraday" in tasks) == macro
    assert ("wide_snapshots" in tasks) == wide
    assert not set(last) & set(due_tasks(c, dict.fromkeys(last, c.now_utc())))


def test_overnight_symbols_weekends_and_original_session():
    from inves_cog.ingest.intraday import YAHOO_TICKERS, parse_yahoo_snapshot, yahoo_symbols
    from tests.m1.test_a024_yahoo import sample

    c = FrozenClock(datetime.fromisoformat("2026-10-27T01:15:00-04:00"))
    assert yahoo_symbols(c.now_utc()) == YAHOO_TICKERS
    assert yahoo_symbols(datetime.fromisoformat("2026-10-24T21:00:00-04:00")) == ("BTC-USD",)
    assert yahoo_symbols(datetime.fromisoformat("2026-10-25T18:15:00-04:00")) == YAHOO_TICKERS
    raw = sample("ES=F")
    raw["chart"]["result"][0]["meta"]["regularMarketTime"] = (c.now_utc() - timedelta(minutes=16)).timestamp()
    r = parse_yahoo_snapshot(raw, "ES=F", c)
    assert r["session"] == "overnight" and r["delay_minutes"] == 16
    assert r["as_of"] != r["fetched_at"]


def test_persisted_failure_backoff_recovery_and_quarter_hour_health():
    from inves_cog.ingest.snapshot_poll import SnapshotPoll

    state, health = {}, Mock()
    repo = Mock()
    repo.get_cursor.side_effect = lambda k: state.get(k)
    repo.set_cursor.side_effect = lambda k, v, t: state.update({k: v})
    t = datetime.fromisoformat("2026-10-27T10:00:00-04:00")

    def poll(at, good=False):
        op = Mock(
            return_value={
                "processed_count": 1 if good else 0,
                "source_success": good,
                "status": "ok" if good else "degraded",
            }
        )
        return SnapshotPoll(repo, FrozenClock(at), health).run("yahoo_intraday", "YahooIntraday", op), op

    poll(t)
    for minutes, delay in [(1, 2), (3, 4), (7, 8), (15, 15)]:
        poll(t + timedelta(minutes=minutes))
        s = state["snapshot-poll:yahoo_intraday"]
        assert datetime.fromisoformat(s["retry_at"]) == t + timedelta(minutes=minutes + delay)
    _, op = poll(t + timedelta(minutes=16))
    op.assert_not_called()
    poll(t + timedelta(minutes=30), True)
    assert state["snapshot-poll:yahoo_intraday"]["failures"] == 0
    assert health.record.call_count == 3  # first observation, +15, +30
    assert "backoff_seconds=0" in health.record.call_args.kwargs["note"]


def test_wide_scope_and_duplicate_insert_contract():
    from inves_cog.ingest.intraday import collect_wide
    from tests.m1.test_a024 import sample

    c = FrozenClock(datetime.fromisoformat("2026-10-26T10:00:00-04:00"))
    repo, http = Mock(), Mock()
    repo.latest_wide.return_value = [{"ticker": "SPY", "included": True}, {"ticker": "BAD", "included": False}]
    http.get.side_effect = [sample("spy_snapshot.json"), sample("spy_previous_all.json")]
    p = SimpleNamespace(clock=c, repo=repo, alpaca=SimpleNamespace(headers={}))
    result = collect_wide(p, http=http)
    assert result["processed_count"] == 1
    assert http.get.call_args_list[0].kwargs["params"]["symbols"] == "SPY"
    assert repo.write.call_args.args[0] == "wide_snapshots"
    assert not repo.write.call_args.kwargs.get("update")


def test_alpaca_429_persists_halt_and_never_auto_retries():
    from inves_cog.ingest.snapshot_poll import SnapshotPoll

    state, repo = {}, Mock()
    repo.get_cursor.side_effect = lambda k: state.get(k)
    repo.set_cursor.side_effect = lambda k, v, t: state.update({k: v})
    c = FrozenClock(datetime.fromisoformat("2026-10-27T10:00:00-04:00"))
    op = Mock(return_value={"processed_count": 0, "source_success": False, "rate_limited": True})
    poll = SnapshotPoll(repo, c, Mock())
    poll.run("intraday_snapshots", "AlpacaIntraday", op)
    poll.run("wide_snapshots", "AlpacaWideSnapshots", op)
    poll.run("intraday_snapshots", "AlpacaIntraday", op)
    assert op.call_count == 1


def test_minute_collections_never_overwrite_original_snapshot():
    from inves_cog.ingest.intraday import collect_intraday
    from tests.m1.test_a024 import CLOCK, sample

    repo, http = Mock(), Mock()
    repo.holding_tickers.return_value = []
    p = SimpleNamespace(clock=CLOCK, repo=repo, stocks=["SPY"], alpaca=SimpleNamespace(headers={}))
    http.get.side_effect = [sample("spy_snapshot.json"), sample("spy_previous_all.json")]
    collect_intraday(p, http=http)
    assert all(not call.kwargs.get("update") for call in repo.write.call_args_list)


@pytest.mark.parametrize(
    "local,expected",
    [
        ("2026-10-30T20:00:00-04:00", ("BTC-USD",)),
        ("2026-10-31T01:00:00-04:00", ("BTC-USD",)),
        ("2026-11-01T01:00:00-04:00", ("BTC-USD",)),
        ("2026-11-01T01:00:00-05:00", ("BTC-USD",)),
        ("2026-11-01T18:00:00-05:00", None),
        ("2026-12-24T20:00:00-05:00", ("BTC-USD",)),
    ],
)
def test_future_closure_holiday_and_fall_back(local, expected):
    from inves_cog.ingest.intraday import YAHOO_TICKERS, yahoo_symbols

    assert yahoo_symbols(datetime.fromisoformat(local)) == (YAHOO_TICKERS if expected is None else expected)


def test_market_poll_runtime_skips_per_minute_health_and_enforces_deadline():
    from inves_cog.ingest.runtime import Runtime

    c = FrozenClock(datetime.fromisoformat("2026-10-27T10:00:00-04:00"))
    repo, health = Mock(), Mock()
    repo.get_cursor.return_value = None
    op = Mock(return_value={"processed_count": 13, "source_success": True, "latest_data_at": c.now_utc().isoformat()})
    from contextlib import nullcontext

    repo.snapshot_lock.side_effect = lambda task: nullcontext(True)
    runtime = Runtime(
        clock=c, health=health, persist_job=Mock(), snapshot_repo=repo, tasks={"yahoo_intraday": ("YahooIntraday", op)}
    )
    runtime.run(["yahoo_intraday"])
    runtime.run(["yahoo_intraday"])
    assert runtime.runner.timeout_seconds == 50
    # Our mock has no persisted cursor: both are first aggregates; JobRunner adds none.
    assert health.record.call_count == 2


def check_a025_database(c):
    from inves_cog.ingest.market import NY
    from inves_cog.ingest.repository import Repository

    now = datetime.fromisoformat("2026-10-27T12:00:00-04:00")
    repo = Repository(c)
    c.execute("SET LOCAL ROLE role_ingest")
    row = dict(
        ticker="A025_ONLY",
        as_of=now,
        session="overnight",
        last=100,
        prev_close=99,
        delay_minutes=16,
        source="offline",
        fetched_at=now,
    )
    assert repo.write("intraday_snapshots", row) == 1
    assert repo.write("intraday_snapshots", {**row, "last": 999}) == 0
    assert (
        c.execute("SELECT last FROM ingest.intraday_snapshots WHERE ticker=%s", ("A025_ONLY",)).fetchone()["last"]
        == 100
    )
    # Every old half hour retains its first genuine timestamp, not a rounded invention.
    for days in (8, 30, 31):
        for minutes in (0, 1, 29, 30, 31):
            stamp = now - timedelta(days=days) + timedelta(minutes=minutes)
            repo.write("intraday_snapshots", {**row, "as_of": stamp})
    repo.compact_intraday(now)
    got = c.execute(
        "SELECT as_of FROM ingest.intraday_snapshots WHERE ticker=%s ORDER BY as_of", ("A025_ONLY",)
    ).fetchall()
    assert len(got) == 5
    assert {r["as_of"].astimezone(NY).minute for r in got} == {0, 30}
    for day in ("2026-10-23", "2026-10-24", "2026-10-26", "2026-10-27"):
        wide = {k: v for k, v in row.items() if k not in {"session", "delay_minutes"}}
        wide["as_of"] = datetime.fromisoformat(day + "T12:00:00-04:00")
        assert repo.write("wide_snapshots", wide) == 1
        assert repo.write("wide_snapshots", wide) == 0
    repo.cleanup_wide_snapshots(now.date(), (now - timedelta(days=1)).date())
    assert c.execute("SELECT count(*) AS n FROM ingest.wide_snapshots WHERE ticker='A025_ONLY'").fetchone()["n"] == 2
    c.execute("RESET ROLE")
    c.execute("SET LOCAL ROLE role_web")
    assert c.execute("SELECT has_table_privilege(current_user,'ingest.wide_snapshots','SELECT') AS yes").fetchone()[
        "yes"
    ]
    assert not c.execute("SELECT has_table_privilege(current_user,'ingest.wide_snapshots','INSERT') AS yes").fetchone()[
        "yes"
    ]
    c.execute("RESET ROLE")


def test_a025_real_pg_dedup_retention_and_roles():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row
    ) as c:
        try:
            check_a025_database(c)
        finally:
            c.rollback()


def test_adjusted_previous_close_cached_across_minutes_and_empty_values():
    from inves_cog.ingest.intraday import cached_previous
    from tests.m1.test_a024 import CLOCK, sample

    state, repo, http = {}, Mock(), Mock()
    repo.get_cursor.side_effect = lambda key: state.get(key)
    repo.set_cursor.side_effect = lambda key, value, at: state.update({key: value})
    http.get.return_value = sample("spy_previous_all.json")
    p = SimpleNamespace(clock=CLOCK, repo=repo)
    first = cached_previous(p, http, {}, ["SPY", "MISSING"], CLOCK.now_utc().date())
    second = cached_previous(p, http, {}, ["SPY", "MISSING"], CLOCK.now_utc().date())
    assert first == second == {"SPY": 759.97, "MISSING": None}
    assert http.get.call_count == 1


def test_no_http_after_actual_alpaca_limit_response():
    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.intraday import collect_intraday
    from inves_cog.ingest.snapshot_poll import SnapshotPoll
    from tests.m1.test_a024 import CLOCK

    state, repo = {}, Mock()
    repo.get_cursor.side_effect = lambda key: state.get(key)
    repo.set_cursor.side_effect = lambda key, value, at: state.update({key: value})
    repo.holding_tickers.return_value = []
    send = Mock(return_value=Response(429, {}))
    p = SimpleNamespace(clock=CLOCK, repo=repo, stocks=["SPY"], alpaca=SimpleNamespace(headers={}))
    poll = SnapshotPoll(repo, CLOCK, Mock())

    def op():
        return collect_intraday(p, http=HTTPClient(send=send, retries=0))

    assert poll.run("intraday_snapshots", "AlpacaIntraday", op)["rate_limited"] is True
    poll.run("intraday_snapshots", "AlpacaIntraday", op)
    assert send.call_count == 1


def test_success_health_one_aggregate_each_fifteen_minutes():
    from inves_cog.ingest.snapshot_poll import SnapshotPoll

    state, repo, health = {}, Mock(), Mock()
    repo.get_cursor.side_effect = lambda key: state.get(key)
    repo.set_cursor.side_effect = lambda key, value, at: state.update({key: value})
    start = datetime.fromisoformat("2026-10-27T10:00:00-04:00")
    for minute in range(16):
        now = start + timedelta(minutes=minute)

        def op(now=now):
            return {"processed_count": 13, "source_success": True, "latest_data_at": now.isoformat()}

        SnapshotPoll(repo, FrozenClock(now), health).run("yahoo_intraday", "YahooIntraday", op)
    assert health.record.call_count == 2
    args = health.record.call_args.kwargs
    assert args["count"] == 195
    assert "success_count=15; failure_count=0;" in args["note"]
    assert (start + timedelta(minutes=15)).isoformat() in args["note"]


def test_dedicated_scheduler_does_not_spawn_model_enrichment(monkeypatch):
    from contextlib import nullcontext
    from inves_cog.ingest import cli

    c = FrozenClock(datetime.fromisoformat("2026-10-27T10:00:17-04:00"))
    p, proc, sleep = Mock(), Mock(), Mock(side_effect=StopIteration)
    monkeypatch.setattr("sys.argv", ["ingest", "schedule", "--tasks", "yahoo_intraday"])
    monkeypatch.setattr(cli, "SystemClock", lambda: c)
    monkeypatch.setattr(cli, "read_environment", lambda: {})
    monkeypatch.setattr(cli, "connect", lambda values: nullcontext(Mock()))
    monkeypatch.setattr(cli, "build", lambda **kwargs: p)
    monkeypatch.setattr(cli, "schedule_once", lambda *args, **kwargs: {})
    monkeypatch.setattr(cli.subprocess, "Popen", proc)
    monkeypatch.setattr(cli.time, "sleep", sleep)
    with pytest.raises(StopIteration):
        cli.main()
    proc.assert_not_called()
    sleep.assert_called_once_with(43)
