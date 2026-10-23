"""B-046: cutoff stays put while the scheduler waits, skips, and retries."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.morning import (
    _write_page,
    at_stage_deadline,
    dispatch_decision,
    in_stage_window,
    skip_summary,
    stage_bounds,
    stage_cutoff,
    upstream_phrase,
)
from inves_cog.perception.attribution.replay_window import slot_moment
from inves_cog.perception.attribution.scheduled import main as stage_main
from scripts import schedule_daily_modules as daily
from scripts.schedule_attribution_stage import run_once as stage_once
from scripts.schedule_morning_page import run_once as morning_once
from tests.m8.test_b039_run import Cursor, Pages, Quiet, _news

pytestmark = pytest.mark.phase1_blocking

_NY = ZoneInfo("America/New_York")
_SH = ZoneInfo("Asia/Shanghai")
_SUMMER = "2026-10-15"
_WINTER = "2026-11-12"


def _ok(name, ended):
    return {"task_name": name, "status": "ok", "ended_at": ended, "error_summary": None}


def _failed(name, summary="boom"):
    return {"task_name": name, "status": "failed", "ended_at": None, "error_summary": summary}


class _Store:
    def __init__(self, rows):
        self.rows = rows
        self.skips = []
        self.calls = []

    def records(self, task, _day):
        return [row for row in self.rows if row["task_name"] == task]

    def skip(self, task, _day, summary):
        self.skips.append((task, summary))
        self.rows.append(_failed(task, summary))

    def launch(self, command, **_kwargs):
        self.calls.append(command)
        return type("Done", (), {"returncode": 0})()


def _stage(task, moment, store, *, code=0, remember=False):
    def launch(command, **kwargs):
        store.calls.append(command)
        if remember and code == 0:
            store.rows.append(_ok(task, moment))
        return type("Done", (), {"returncode": code})()

    return stage_once(
        root="/tmp/b046",
        task_name=task,
        clock=FrozenClock(moment),
        python="/fixture/python",
        run=launch,
        load_environment=lambda _path: {},
        records=store.records,
        skip=store.skip,
    )


def test_d1_tracks_waits_for_the_real_end_and_keeps_the_cutoff():
    start, _end = stage_bounds("attribution_tracks", _SUMMER)
    ended = start + timedelta(minutes=15, seconds=30)
    store = _Store([_ok("attribution_candidates", ended)])
    for minute in range(16):
        result = _stage("attribution_tracks", start + timedelta(minutes=minute), store)
        assert result["status"] == "waiting_dependencies"
    assert store.calls == []
    launch = start + timedelta(minutes=16)
    assert _stage("attribution_tracks", launch, store, remember=True)["status"] == "ok"
    sent = store.calls[0][store.calls[0].index("--at") + 1]
    assert datetime.fromisoformat(sent) == launch
    cutoff = stage_cutoff("attribution_tracks", launch)
    assert cutoff == start
    late_news = _news("late-news", cutoff + timedelta(minutes=1), cutoff + timedelta(minutes=1))
    early_news = _news("early-news", cutoff - timedelta(hours=2), cutoff - timedelta(hours=1))
    pages = Pages()
    pages.jobs.append({**_ok("attribution_candidates", ended), "id": 1})

    def execute(statement, params=None):
        compact = " ".join(statement.split())
        if "ingest.info_items" in compact:
            pages.calls.append((compact, params))
            news_cutoff, begin, finish = params
            rows = [
                row
                for row in (early_news, late_news)
                if row["first_seen_at"] <= news_cutoff and begin <= row["published_at"] <= finish
            ]
            return Cursor(rows)
        return Pages.execute(pages, statement, params)

    pages.execute = execute
    assert (
        stage_main(
            ["--task", "attribution_tracks"],
            connection=pages,
            clock=FrozenClock(launch),
            client=Quiet(),
            record_clock=FrozenClock(launch + timedelta(minutes=1)),
        )
        == 0
    )
    queried = [params for statement, params in pages.calls if statement and "info_items" in statement]
    assert queried and queried[0][0] == cutoff and queried[0][2] == cutoff
    assert late_news["first_seen_at"] > cutoff
    assert early_news["first_seen_at"] <= cutoff
    labels = stage_cutoff("attribution_labels", start + timedelta(hours=4))
    label_store = _Store([_ok("attribution_tracks", launch + timedelta(minutes=1))])
    assert _stage("attribution_labels", labels + timedelta(minutes=10), label_store, remember=True)["status"] == "ok"
    snap = Pages()
    snap.jobs.extend([_ok("attribution_candidates", ended), _ok("attribution_tracks", launch)])
    for index, row in enumerate(snap.jobs, start=1):
        row["id"] = index
    assert (
        stage_main(
            ["--task", "attribution_labels"],
            connection=snap,
            clock=FrozenClock(labels + timedelta(minutes=10)),
            client=Quiet(),
            record_clock=FrozenClock(labels + timedelta(minutes=12)),
        )
        == 0
    )
    assert snap.snapshots[0]["source_asof"] == labels + timedelta(minutes=12)


def test_d2_deadline_skip_names_the_upstream_and_does_not_call_the_model():
    _start, tracks_end = stage_bounds("attribution_tracks", _SUMMER)
    _label_start, labels_end = stage_bounds("attribution_labels", _SUMMER)
    store = _Store([_failed("attribution_candidates", "still running")])
    result = _stage("attribution_tracks", tracks_end, store)
    assert result["status"] == "failed"
    assert result["error_summary"].startswith("skipped_upstream:")
    assert "attribution_candidates 状态 failed" in result["error_summary"]
    labels = _stage("attribution_labels", labels_end, store)
    assert labels["error_summary"].startswith("skipped_upstream:")
    assert "attribution_tracks 被跳过" in labels["error_summary"]
    assert store.calls == []


def test_d3_anomaly_window_marks_late_and_skips_at_the_deadline(monkeypatch):
    def probe(stamp, ready, calls):
        return daily.run_once(
            clock=FrozenClock(datetime.fromisoformat(stamp.replace("Z", "+00:00"))),
            values={},
            ready=lambda *_args: ready,
            market_run=lambda **_kwargs: {"status": "ok"},
            anomaly_run=lambda **_kwargs: calls.append("anomaly") or {"status": "ok"},
            score_run=lambda **_kwargs: {"status": "ok"},
            valuation_run=lambda **_kwargs: {"status": "ok"},
            paper_run=lambda **_kwargs: {"status": "ok"},
            premarket_run=lambda **_kwargs: {"status": "ok"},
            names=["anomaly_daily"],
            dependency_rows=lambda _day: [_failed("market_structure", "running")],
            skip_job=lambda *args: calls.append(args),
        )

    early = []
    assert "anomaly_daily" in probe("2026-10-21T00:58:00Z", True, early)
    assert early == ["anomaly"]
    late = []
    assert probe("2026-10-21T01:05:00Z", True, late)["anomaly_daily"]["status"] == "ok"
    skipped = []
    result = probe("2026-10-21T01:10:00Z", False, skipped)
    assert result["anomaly_daily"]["error_summary"].startswith("skipped_upstream:")
    assert "market_structure" in result["anomaly_daily"]["error_summary"]
    assert "anomaly" not in skipped
    after = probe("2026-10-21T01:12:00Z", True, [])
    assert "anomaly_daily" not in after

    from inves_cog.perception.anomaly import database, service
    from tests.ops.test_runtime_scheduling import RecordedConnection

    class LateConnection(RecordedConnection):
        def fetchone(self):
            if self.statements and "marketstate.market" in self.statements[-1][0]:
                return {"trade_date": "2026-10-20"}
            return self.job

    class Panel:
        def detect(self, _day, _session):
            return []

    connection = LateConnection()
    monkeypatch.setattr(daily, "connect", lambda _values: connection)
    monkeypatch.setattr(database.DatabasePanel, "from_connection", lambda *_args, **_kwargs: Panel())
    monkeypatch.setattr(service, "write_anomalies", lambda *_a, **_k: None)
    values = {"INVES_COG_PERCEPTION_DATABASE_URL": "perception-fixture"}
    recorded = daily.run_anomalies(clock=FrozenClock(datetime(2026, 10, 21, 1, 5, tzinfo=timezone.utc)), values=values)
    assert recorded["late"] is True
    assert any(params and params[0] == "迟到" for _statement, params in connection.statements)


def test_d4_page_is_sent_while_the_chain_waits_for_anomalies(tmp_path, monkeypatch):
    morning = slot_moment(_SUMMER, "attribution_candidates")
    calls = []
    store = _Store([])

    def run(command, **_kwargs):
        calls.append(command)
        if "--chain-only" in command:
            store.rows.append(_ok("attribution_candidates", morning + timedelta(minutes=5)))
        return type("Done", (), {"returncode": 0})()

    first = morning_once(
        root=tmp_path / "repo",
        clock=FrozenClock(morning),
        python="/fixture/python",
        run=run,
        load_environment=lambda _path: {},
        records=store.records,
        skip=store.skip,
    )
    assert first["status"] == "ok"
    assert calls[0][-1] == "--page-only"
    assert _stage_waiting(morning_once, tmp_path, morning + timedelta(minutes=4), store, calls)
    store.rows.append(_ok("anomaly_daily", morning + timedelta(minutes=5)))
    later = morning_once(
        root=tmp_path / "later",
        clock=FrozenClock(morning + timedelta(minutes=5)),
        python="/fixture/python",
        run=run,
        load_environment=lambda _path: {},
        records=store.records,
        skip=store.skip,
    )
    assert later["status"] == "ok"
    assert "--chain-only" in calls[-1]
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    page = _Page()
    assert _write_page(page, morning, Quiet()) == 0
    text = (tmp_path / f"daily_page_{_SUMMER}.txt").read_text(encoding="utf-8")
    assert "异常检测未完成" in text
    assert "估值 2026-10-14" in text


def _stage_waiting(runner, tmp_path, moment, store, calls):
    before = len(calls)
    result = runner(
        root=tmp_path / "wait",
        clock=FrozenClock(moment),
        python="/fixture/python",
        run=lambda command, **_kwargs: calls.append(command) or type("Done", (), {"returncode": 0})(),
        load_environment=lambda _path: {},
        records=store.records,
        skip=store.skip,
    )
    return result["status"] == "waiting_dependencies" and len(calls) == before


class _Page:
    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        if "valuation_v1.ranges" in compact:
            return Cursor(
                [
                    {
                        "trade_date": "2026-10-14",
                        "ticker": "NVDA",
                        "status": "ok",
                        "bear": 10,
                        "neutral": 20,
                        "bull": 30,
                        "payload": {},
                        "observed_at": params[-1],
                    }
                ]
            )
        if "bars_daily" in compact:
            return Cursor([{"ticker": "NVDA", "close": 20}])
        if "trading.ledger" in compact:
            return Cursor([{"state": {"positions": {"NVDA": 1}}, "trade_date": _SUMMER, "observed_at": params[-1]}])
        return Cursor([])


def test_d5_retries_stop_after_the_cap_and_candidates_do_not_retry():
    start, _end = stage_bounds("attribution_tracks", _SUMMER)
    moment = start + timedelta(minutes=5)
    store = _Store([_ok("attribution_candidates", start - timedelta(minutes=1))])
    codes = iter([1, 0])

    def launch(command, **_kwargs):
        store.calls.append(command)
        code = next(codes)
        summary = None if code == 0 else "boom"
        status = "ok" if code == 0 else "failed"
        store.rows.append(
            {"task_name": "attribution_tracks", "status": status, "ended_at": moment, "error_summary": summary}
        )
        return type("Done", (), {"returncode": code})()

    kwargs = dict(
        root="/tmp/b046-retry",
        task_name="attribution_tracks",
        clock=FrozenClock(moment),
        python="/fixture/python",
        run=launch,
        load_environment=lambda _path: {},
        records=store.records,
        skip=store.skip,
    )
    assert stage_once(**kwargs)["status"] == "failed"
    assert stage_once(**kwargs)["status"] == "ok"
    assert stage_once(**kwargs)["status"] == "already_attempted"
    assert len(store.calls) == 2

    blocked = _Store(
        [
            _ok("attribution_candidates", start),
            _failed("attribution_tracks"),
            _failed("attribution_tracks"),
            _failed("attribution_tracks"),
        ]
    )
    assert _stage("attribution_tracks", moment, blocked)["status"] == "already_attempted"
    assert blocked.calls == []

    morning = slot_moment(_SUMMER, "attribution_candidates")
    chain = _Store([_ok("anomaly_daily", morning - timedelta(minutes=1)), _failed("attribution_candidates")])
    result = morning_once(
        root="/tmp/b046-chain",
        clock=FrozenClock(morning + timedelta(minutes=2)),
        python="/fixture/python",
        run=lambda command, **_kwargs: chain.calls.append(command),
        load_environment=lambda _path: {},
        records=chain.records,
        skip=chain.skip,
    )
    assert result["status"] == "already_attempted"
    assert chain.calls == []
    assert dispatch_decision("attribution_candidates", [_failed("attribution_candidates")]) == "exhausted"


def test_d6_exit_without_a_job_row_is_not_ok_and_restart_keeps_the_count():
    start, _end = stage_bounds("attribution_tracks", _SUMMER)
    moment = start + timedelta(minutes=2)
    store = _Store([_ok("attribution_candidates", start - timedelta(minutes=1))])
    result = _stage("attribution_tracks", moment, store, code=0)
    assert result["status"] == "failed"
    assert result["reason"] == "no_job_row"
    store.rows.append(_ok("attribution_tracks", moment))
    assert _stage("attribution_tracks", moment + timedelta(minutes=1), store)["status"] == "already_attempted"
    assert len(store.calls) == 1
    restarted = _Store(
        [
            _ok("attribution_candidates", start),
            _failed("attribution_tracks"),
            _failed("attribution_tracks"),
            _failed("attribution_tracks"),
        ]
    )
    assert _stage("attribution_tracks", moment, restarted)["status"] == "already_attempted"
    assert restarted.calls == []


def test_d7_winter_shifts_beijing_and_keeps_the_et_window():
    summer = slot_moment(_SUMMER, "attribution_tracks")
    winter = slot_moment(_WINTER, "attribution_tracks")
    assert summer.astimezone(_NY).hour == 21 and summer.minute == 30
    assert winter.astimezone(_NY).hour == 21 and winter.minute == 30
    assert winter.astimezone(_SH).hour == summer.astimezone(_SH).hour + 1
    assert in_stage_window("attribution_tracks", winter)
    assert not in_stage_window("attribution_tracks", winter - timedelta(hours=1))
    start, end = stage_bounds("attribution_labels", _WINTER)
    assert start.astimezone(_NY).hour == 0 and start.minute == 30
    assert at_stage_deadline("attribution_labels", end)
    assert stage_cutoff("attribution_labels", end + timedelta(minutes=30)) == start
    page = slot_moment(_WINTER, "attribution_candidates")
    assert page.astimezone(_NY).hour == 21 and page.astimezone(_SH).hour == 10
    assert skip_summary([upstream_phrase("anomaly_daily", [])]) == "skipped_upstream: anomaly_daily 没有记录"
