"""Late catch-up for the attribution chain: skipped stages retry once with PIT intact."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.morning import (
    _load,
    catchup_deadline,
    catchup_pending,
    catchup_ready,
    dispatch_decision,
    stage_bounds,
    upstream_ready,
)
from inves_cog.perception.attribution.morning import (
    main as morning_main,
)
from inves_cog.perception.attribution.scheduled import main as stage_main
from scripts.schedule_attribution_stage import run_once as stage_once
from scripts.schedule_morning_page import run_once as morning_once
from tests.m8.test_b039_run import Cursor, Pages, Quiet, _anomaly, _news

pytestmark = pytest.mark.phase1_blocking

_NY = ZoneInfo("America/New_York")
DAY = "2026-10-15"
LATE = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
CUTOFF = stage_bounds("attribution_candidates", DAY)[0]


def _skip(name):
    return {
        "task_name": name,
        "status": "failed",
        "ended_at": None,
        "error_summary": "skipped_upstream: upstream 没有记录",
    }


def _ok(name, ended):
    return {"task_name": name, "status": "ok", "ended_at": ended, "error_summary": None}


def _catchup(name, status="ok"):
    return {
        "task_name": name,
        "status": status,
        "ended_at": LATE - timedelta(minutes=5),
        "error_summary": f"late_catchup: cutoff={CUTOFF.isoformat()} ran={LATE.isoformat()}",
    }


class Conn(Pages):
    """Param-aware fake: honors the anomaly cutoff, the news window, and the catchup annotation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.anomalies = []
        self.news = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        if "perception.anomalies" in compact:
            day, *bound = params or []
            rows = [row for row in self.anomalies if str(row.get("trade_date") or "")[:10] == str(day)[:10]]
            if bound:
                rows = [row for row in rows if (row.get("generated_at") or bound[0]) <= bound[0]]
            return Cursor(rows)
        if "ingest.info_items" in compact:
            seen, lo, hi = params[0], params[1], params[2]
            rows = [
                row
                for row in self.news
                if (row.get("first_seen_at") or seen) <= seen and lo <= (row.get("published_at") or lo) <= hi
            ]
            return Cursor(rows)
        return Pages.execute(self, statement, params)


def _stage_store(rows, calls=None):
    """Minimal dispatch-time store, shaped like the _Store fixture in test_b046."""

    class Store:
        def __init__(self):
            self.calls = calls if calls is not None else []

        def records(self, task, _day):
            return [row for row in rows if row["task_name"] == task]

        def skip(self, _task, _day, _summary):
            raise AssertionError("no more skips during catch-up tests")

    return Store()


def test_load_late_flag_only_relaxes_the_anomaly_bound():
    conn = Conn()
    on_time = _anomaly()
    late = dict(_anomaly(), anomaly_id="late-one", generated_at=LATE)
    conn.anomalies = [on_time, late]
    fresh = _news("fresh", CUTOFF - timedelta(hours=1), CUTOFF - timedelta(minutes=30))
    later = _news("after-cutoff", CUTOFF + timedelta(hours=1), CUTOFF + timedelta(minutes=5))
    conn.news = [fresh, later]

    normal = _load(conn, CUTOFF, DAY)
    assert [row["anomaly_id"] for row in normal["anomalies"]] == ["nvda-close"]
    assert [row["info_id"] for row in normal["items"]] == ["fresh"]

    relaxed = _load(conn, CUTOFF, DAY, upstream_visible_for_day=DAY)
    assert [row["anomaly_id"] for row in relaxed["anomalies"]] == ["nvda-close", "late-one"]
    assert [row["info_id"] for row in relaxed["items"]] == ["fresh"]


def test_catchup_pending_gate():
    own = [_skip("attribution_candidates")]
    before = catchup_deadline("attribution_candidates", DAY) - timedelta(minutes=1)
    after = catchup_deadline("attribution_candidates", DAY) + timedelta(minutes=1)
    assert catchup_pending("attribution_candidates", DAY, own, before)
    assert not catchup_pending("attribution_candidates", DAY, own, after)
    assert not catchup_pending("attribution_candidates", DAY, own + [_catchup("attribution_candidates")], before)
    assert not catchup_pending("attribution_candidates", DAY, [_ok("attribution_candidates", before)], before)
    assert not catchup_pending("attribution_candidates", DAY, [], before)


def test_catchup_ready_needs_a_finished_upstream():
    own = [_skip("attribution_candidates")]

    def ready(_name):
        return [_ok("anomaly_daily", LATE - timedelta(minutes=10))]

    def missing(_name):
        return []

    assert catchup_ready("attribution_candidates", DAY, own, ready, LATE)
    assert not catchup_ready("attribution_candidates", DAY, own, missing, LATE)


def test_dispatch_decision_treats_catchup_rows_as_terminal():
    assert (
        dispatch_decision("attribution_tracks", [_skip("attribution_tracks"), _catchup("attribution_tracks")]) == "done"
    )
    assert (
        dispatch_decision("attribution_tracks", [_skip("attribution_tracks"), _catchup("attribution_tracks", "failed")])
        == "exhausted"
    )
    assert upstream_ready([_catchup("attribution_candidates")], LATE, "attribution_candidates")


def test_candidates_catchup_runs_and_annotates():
    conn = Conn()
    conn.anomalies = [dict(_anomaly(), generated_at=LATE)]
    conn.news = [_news("seen", CUTOFF - timedelta(hours=1), CUTOFF - timedelta(minutes=30))]
    conn.jobs.append({"id": 1, "task_name": "attribution_candidates", "trade_date": DAY, **_skip("x")})
    assert (
        morning_main(
            ["--catchup", "--day", DAY],
            connection=conn,
            clock=FrozenClock(LATE),
            client=Quiet(),
            record_clock=FrozenClock(LATE),
        )
        == 0
    )
    assert conn.jobs[0]["error_summary"].startswith("skipped_upstream:")
    assert conn.jobs[0]["error_summary"].startswith("skipped_upstream:")
    row = conn.jobs[-1]
    assert row["status"] == "ok"
    assert row["error_summary"].startswith("late_catchup: ")
    assert row["error_summary"].count("late_catchup:") == 1
    assert row["error_summary"].count("late_catchup:") == 1
    assert "cutoff=" in row["error_summary"]
    assert any(statement.startswith("INSERT INTO perception.reports") for statement, _p in conn.calls)


def test_downstream_stage_catches_up_after_upstream_catchup():
    conn = Conn()
    conn.anomalies = [_anomaly()]
    conn.jobs.extend(
        [
            {"id": 1, "task_name": "attribution_candidates", "trade_date": DAY, **_skip("a")},
            {
                "id": 2,
                "task_name": "attribution_candidates",
                "trade_date": DAY,
                **_catchup("attribution_candidates"),
            },
            {"id": 3, "task_name": "attribution_tracks", "trade_date": DAY, **_skip("b")},
        ]
    )
    assert (
        stage_main(
            ["--task", "attribution_tracks", "--catchup", "--day", DAY],
            connection=conn,
            clock=FrozenClock(LATE),
            client=Quiet(),
            record_clock=FrozenClock(LATE),
        )
        == 0
    )
    row = conn.jobs[-1]
    assert row["task_name"] == "attribution_tracks"
    assert row["status"] == "ok"
    assert row["error_summary"].startswith("late_catchup: ")


def _receipt_dir(tmp_path, task_name):
    import json

    state = tmp_path / ".harness" / "service"
    state.mkdir(parents=True)
    (state / f"{task_name.replace('_', '-')}-{DAY}-094500.json").write_text(
        json.dumps(
            {
                "beijing_date": DAY,
                "slot": "09:45",
                "status": "failed",
                "error_summary": "skipped_upstream: upstream 没有记录",
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_dispatcher_fires_catchup_inside_the_deadline(tmp_path):
    calls = []
    rows = [_ok("anomaly_daily", LATE - timedelta(hours=1)), _skip("attribution_candidates")]

    def fake_run(command, **_kwargs):
        calls.append(command)
        rows.append(_catchup("attribution_candidates"))
        return type("Done", (), {"returncode": 0})()

    def records(task, _day):
        return [row for row in rows if row["task_name"] == task]

    root = _receipt_dir(tmp_path, "attribution_candidates")
    result = morning_once(
        root=root,
        clock=FrozenClock(LATE),
        python="py",
        run=fake_run,
        load_environment=lambda _p: {},
        records=records,
        skip=lambda *_a: (_ for _ in ()).throw(AssertionError("no skips")),
    )
    assert result.get("catchup") and result["status"] == "ok"
    assert calls and "--catchup" in calls[0] and DAY in calls[0]


def test_dispatcher_without_receipt_stays_credential_free(tmp_path):
    calls = []
    rows = [_ok("anomaly_daily", LATE - timedelta(hours=1)), _skip("attribution_candidates")]

    def records(task, _day):
        return [row for row in rows if row["task_name"] == task]

    def never(*_a, **_k):
        raise AssertionError("no credential reads on an idle poll")

    result = morning_once(
        root=tmp_path,
        clock=FrozenClock(LATE),
        python="py",
        run=never,
        load_environment=never,
        records=None,
        skip=never,
    )
    assert result == {"status": "not_due"}
    assert calls == [] and not (tmp_path / ".harness").exists()


def test_dispatcher_with_receipt_but_no_upstream_stays_not_due(tmp_path):
    calls = []
    rows = [_skip("attribution_candidates")]

    def fake_run(command, **_kwargs):
        calls.append(command)
        return type("Done", (), {"returncode": 0})()

    def records(task, _day):
        return [row for row in rows if row["task_name"] == task]

    root = _receipt_dir(tmp_path, "attribution_candidates")
    result = morning_once(
        root=root,
        clock=FrozenClock(LATE),
        python="py",
        run=fake_run,
        load_environment=lambda _p: {},
        records=records,
        skip=lambda *_a: None,
    )
    assert result == {"status": "not_due"}
    assert calls == []


def test_stage_dispatcher_fires_catchup(tmp_path):
    calls = []
    rows = [_catchup("attribution_candidates"), _skip("attribution_tracks")]

    def fake_run(command, **_kwargs):
        calls.append(command)
        rows.append(_catchup("attribution_tracks"))
        return type("Done", (), {"returncode": 0})()

    def records(task, _day):
        return [row for row in rows if row["task_name"] == task]

    result = stage_once(
        clock=FrozenClock(LATE),
        task_name="attribution_tracks",
        root=_receipt_dir(tmp_path, "attribution_tracks"),
        python="py",
        run=fake_run,
        load_environment=lambda _p: {},
        records=records,
        skip=lambda *_a: (_ for _ in ()).throw(AssertionError("no skips")),
    )
    assert result.get("catchup") and result["status"] == "ok"
    assert calls and "--catchup" in calls[0] and "--task" in calls[0]
