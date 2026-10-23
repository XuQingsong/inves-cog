"""B-045: the later stages are real programs, and job rows use a moving clock."""

import os
import subprocess
import sys
from datetime import timedelta

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.morning import main as morning_main
from inves_cog.perception.attribution.replay_window import slot_moment
from inves_cog.perception.attribution.scheduled import main as stage_main
from tests.m8.test_b039_run import DAY, STARTED, Cursor, Pages, Quiet, _anomaly, _news

pytestmark = pytest.mark.phase1_blocking

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_OFF_SLOT = "2026-10-16T08:00:00+08:00"


class StepClock:
    """First read is the start. Every later read is thirty minutes after that."""

    def __init__(self, start):
        self.start = start
        self.end = start + timedelta(minutes=30)
        self.calls = 0

    def now_utc(self):
        self.calls += 1
        if self.calls == 1:
            return self.start
        return self.end


class Jobs(Pages):
    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {
                "id": len(self.jobs) + 1,
                "task_name": params[0],
                "trade_date": params[1],
                "started_at": params[2],
                "status": "failed",
                "ended_at": None,
                "error_summary": None,
            }
            self.jobs.append(row)
            return Cursor([{"id": row["id"]}])
        return Pages.execute(self, statement, params)


class Deny:
    def execute(self, statement, params=None):
        if "has_table_privilege" in statement:
            return Cursor([{"allowed": False}])
        return Cursor([])


def _job(pages, name):
    return next(row for row in pages.jobs if row["task_name"] == name)


def _prior(name, ended):
    return {
        "id": 0,
        "task_name": name,
        "trade_date": DAY,
        "status": "ok",
        "started_at": ended - timedelta(minutes=1),
        "ended_at": ended,
        "error_summary": None,
    }


def test_module_entry_reaches_main_and_writes_both_stage_rows():
    off = subprocess.run(
        [
            sys.executable,
            "-m",
            "inves_cog.perception.attribution.scheduled",
            "--task",
            "attribution_tracks",
            "--at",
            _OFF_SLOT,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert off.returncode == 0
    assert off.stdout.strip() == "not-due"

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    import psycopg
    from psycopg.rows import dict_row

    dsn = f"postgresql://inves_cog_admin@{host}/inves_cog"
    admin = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    tracks = slot_moment(DAY, "attribution_tracks")
    labels = slot_moment(DAY, "attribution_labels")
    try:
        admin.execute(
            "DELETE FROM ingest.job_runs WHERE trade_date = %s AND task_name = ANY(%s)",
            (DAY, ["attribution_candidates", "attribution_tracks", "attribution_labels"]),
        )
        admin.execute(
            "INSERT INTO ingest.job_runs "
            "(task_name, trade_date, started_at, ended_at, status, processed_count, params_version) "
            "VALUES ('attribution_candidates', %s, %s, %s, 'ok', 0, 'p-2026.10')",
            (DAY, tracks - timedelta(minutes=20), tracks - timedelta(minutes=15)),
        )
        env = dict(os.environ)
        env["INVES_COG_DATABASE_URL"] = dsn
        env["INVES_COG_PERCEPTION_DATABASE_URL"] = dsn
        for task_name, moment in (("attribution_tracks", tracks), ("attribution_labels", labels)):
            ran = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inves_cog.perception.attribution.scheduled",
                    "--task",
                    task_name,
                    "--at",
                    moment.isoformat(),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            assert ran.returncode == 0, ran.stderr
            row = admin.execute(
                "SELECT status FROM ingest.job_runs WHERE trade_date = %s AND task_name = %s",
                (DAY, task_name),
            ).fetchone()
            assert row is not None
            assert row["status"] == "ok"
    finally:
        admin.execute(
            "DELETE FROM perception.m9_input_snapshots WHERE trade_date = %s AND kind = 'stage_completion'",
            (DAY,),
        )
        admin.execute(
            "DELETE FROM ingest.job_runs WHERE trade_date = %s AND task_name = ANY(%s)",
            (DAY, ["attribution_candidates", "attribution_tracks", "attribution_labels"]),
        )
        admin.close()


def test_job_rows_use_the_moving_clock_including_failures():
    morning = slot_moment(DAY, "attribution_candidates")
    tracks = slot_moment(DAY, "attribution_tracks")
    labels = slot_moment(DAY, "attribution_labels")
    pages = Jobs()
    clock = StepClock(morning + timedelta(minutes=2))
    assert morning_main([], connection=pages, clock=FrozenClock(morning), client=Quiet(), record_clock=clock) == 0
    _assert_span(_job(pages, "attribution_candidates"), clock, morning)

    pages.jobs.append(_prior("attribution_candidates", tracks - timedelta(minutes=1)))
    track_clock = StepClock(tracks + timedelta(minutes=2))
    assert (
        stage_main(
            ["--task", "attribution_tracks"],
            connection=pages,
            clock=FrozenClock(tracks),
            client=Quiet(),
            record_clock=track_clock,
        )
        == 0
    )
    _assert_span(_job(pages, "attribution_tracks"), track_clock, tracks)

    label_pages = Jobs()
    label_pages.jobs.append(_prior("attribution_tracks", labels - timedelta(minutes=1)))
    label_clock = StepClock(labels + timedelta(minutes=2))
    assert (
        stage_main(
            ["--task", "attribution_labels"],
            connection=label_pages,
            clock=FrozenClock(labels),
            client=Quiet(),
            record_clock=label_clock,
        )
        == 0
    )
    _assert_span(_job(label_pages, "attribution_labels"), label_clock, labels)

    failed = Jobs()
    fail_clock = StepClock(tracks + timedelta(minutes=3))
    assert (
        stage_main(
            ["--task", "attribution_tracks"],
            connection=failed,
            clock=FrozenClock(tracks),
            client=Quiet(),
            record_clock=fail_clock,
        )
        == 1
    )
    row = _job(failed, "attribution_tracks")
    assert row["status"] == "failed"
    assert "缺少已成功的attribution_candidates" in row["error_summary"]
    _assert_span(row, fail_clock, tracks)

    denied = Jobs()
    deny_clock = StepClock(morning + timedelta(minutes=4))
    assert (
        morning_main(
            [],
            connection=denied,
            perception=Deny(),
            clock=FrozenClock(morning),
            client=Quiet(),
            record_clock=deny_clock,
        )
        == 1
    )
    morning_fail = _job(denied, "attribution_candidates")
    assert morning_fail["status"] == "failed"
    assert "没有写入权限" in morning_fail["error_summary"]
    _assert_span(morning_fail, deny_clock, morning)


def test_slot_still_filters_visibility_and_previous_stage_readiness():
    morning = slot_moment(DAY, "attribution_candidates")
    tracks = slot_moment(DAY, "attribution_tracks")
    early = _anomaly()
    late_anomaly = {**_anomaly(), "anomaly_id": "late-anomaly", "generated_at": morning + timedelta(minutes=1)}
    early_news = _news("early-news", STARTED - timedelta(hours=2), STARTED - timedelta(hours=1))
    late_news = _news("late-news", morning + timedelta(minutes=1), STARTED)
    pages = Jobs()
    news = [early_news, late_news]

    def execute(statement, params=None):
        compact = " ".join(statement.split())
        if "perception.anomalies" in compact and "INSERT" not in compact.upper():
            day, cutoff = params
            rows = [
                row
                for row in (early, late_anomaly)
                if str(row["trade_date"])[:10] == str(day)[:10] and row["generated_at"] <= cutoff
            ]
            return Cursor(rows)
        if "ingest.info_items" in compact:
            cutoff, start, end = params
            rows = [row for row in news if row["first_seen_at"] <= cutoff and start <= row["published_at"] <= end]
            return Cursor(rows)
        return Pages.execute(pages, statement, params)

    pages.execute = execute
    client = Quiet()
    original = client.call
    payloads = []

    def call(task, payload):
        payloads.append(payload)
        return original(task, payload)

    client.call = call
    assert (
        morning_main(
            [],
            connection=pages,
            clock=FrozenClock(morning),
            client=client,
            record_clock=StepClock(morning + timedelta(minutes=2)),
        )
        == 0
    )
    asked = str(payloads)
    assert "early-news" in asked
    assert "late-news" not in asked
    assert "late-anomaly" not in asked

    blocked = Jobs()
    blocked.jobs.append(_prior("attribution_candidates", tracks + timedelta(minutes=1)))
    assert (
        stage_main(
            ["--task", "attribution_tracks"],
            connection=blocked,
            clock=FrozenClock(tracks),
            client=Quiet(),
            record_clock=StepClock(tracks + timedelta(minutes=2)),
        )
        == 1
    )
    assert "缺少已成功的attribution_candidates" in _job(blocked, "attribution_tracks")["error_summary"]

    ready = Jobs()
    ready.jobs.append(_prior("attribution_candidates", tracks - timedelta(minutes=1)))
    assert (
        stage_main(
            ["--task", "attribution_tracks"],
            connection=ready,
            clock=FrozenClock(tracks),
            client=Quiet(),
            record_clock=StepClock(tracks + timedelta(minutes=2)),
        )
        == 0
    )
    assert _job(ready, "attribution_tracks")["status"] == "ok"


def test_live_snapshot_uses_the_latest_real_end():
    labels = slot_moment(DAY, "attribution_labels")
    pages = Jobs()
    candidates_end = labels - timedelta(hours=3)
    tracks_end = labels - timedelta(hours=2)
    pages.jobs.extend(
        [
            _prior("attribution_candidates", candidates_end),
            _prior("attribution_tracks", tracks_end),
        ]
    )
    for index, row in enumerate(pages.jobs, start=1):
        row["id"] = index
    clock = StepClock(labels + timedelta(minutes=2))
    assert (
        stage_main(
            ["--task", "attribution_labels"],
            connection=pages,
            clock=FrozenClock(labels),
            client=Quiet(),
            record_clock=clock,
        )
        == 0
    )
    ended = _job(pages, "attribution_labels")["ended_at"]
    assert pages.snapshots[0]["source_asof"] == ended
    assert ended == clock.end
    assert ended != labels
    assert ended > candidates_end
    assert ended > tracks_end


def _assert_span(row, clock, slot):
    assert row["started_at"] == clock.start
    assert row["ended_at"] == clock.end
    assert row["ended_at"] - row["started_at"] == timedelta(minutes=30)
    assert row["started_at"] != slot
    assert row["ended_at"] != slot
