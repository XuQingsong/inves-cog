"""B-039 parts 2 and 3: persist the morning run, schedule the later stages, replay five days."""

import json
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.morning import main as morning_main
from inves_cog.perception.attribution.replay_window import replay_window, slot_moment, visible_news
from inves_cog.perception.attribution.scheduled import main as stage_main
from inves_cog.perception.attribution.snapshot import read_replay_snapshot, read_snapshot
from scripts.install_ingest_service import configuration

pytestmark = pytest.mark.phase1_blocking

DAY = "2026-10-15"
MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
REAL = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)
STARTED = datetime(2026, 10, 15, 20, 0, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class Quiet:
    def __init__(self):
        self.tasks = []

    def call(self, task, payload):
        self.tasks.append(task)
        return {"没有": True}


class Boom:
    def call(self, task, payload):
        raise AssertionError(task)


class Pages:
    def __init__(self, *, fail_save=False):
        self.fail_save = fail_save
        self.jobs = []
        self.calls = []
        self.snapshots = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.calls.append((compact, params))
        if self.fail_save and compact.startswith("INSERT INTO perception."):
            raise RuntimeError("保存失败")
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {
                "id": len(self.jobs) + 1,
                "task_name": params[0],
                "trade_date": params[1],
                "status": "failed",
                "ended_at": None,
                "error_summary": None,
            }
            self.jobs.append(row)
            return Cursor([{"id": row["id"]}])
        if compact.startswith("UPDATE ingest.job_runs"):
            ended, status, _count, error, row_id = params
            found = next(job for job in self.jobs if job["id"] == row_id)
            found.update(status=status, ended_at=ended, error_summary=error)
            return Cursor([])
        if "ingest.job_runs" in compact:
            return Cursor(self.jobs)
        if "perception.anomalies" in compact:
            return Cursor(list(getattr(self, "anomalies", [])))
        if compact.upper().startswith("INSERT INTO PERCEPTION.M9_INPUT_SNAPSHOTS"):
            row = {
                "snapshot_id": len(self.snapshots) + 1,
                "trade_date": params[0],
                "snapshot_generated_at": params[1],
                "source_asof": params[2],
                "status": params[3],
                "kind": params[4],
                "jobs": params[5].obj if hasattr(params[5], "obj") else params[5],
                "events": params[6].obj if hasattr(params[6], "obj") else params[6],
                "missing": params[7].obj if hasattr(params[7], "obj") else params[7],
            }
            self.snapshots.append(row)
            return Cursor([{"snapshot_id": row["snapshot_id"]}])
        if "m9_input_snapshots" in compact:
            return Cursor(self.snapshots)
        if compact.upper().startswith(("BEGIN", "ROLLBACK")):
            return Cursor([])
        return Cursor([])


def _anomaly():
    return {
        "anomaly_id": "nvda-close",
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "pool",
        "members": [{"ticker": "NVDA"}],
        "started_at": STARTED,
        "generated_at": STARTED,
    }


def _news(info_id, published, seen):
    return {
        "info_id": info_id,
        "kind": "news",
        "published_at": published,
        "first_seen_at": seen,
        "headline": info_id,
        "flags": [],
        "tickers": ["NVDA"],
        "entities": [],
        "extraction_source": {"news_card": {"说了什么": info_id, "名单内": [], "钟点清楚": True}},
    }


def test_morning_persists_and_the_job_is_ok_only_after_save(tmp_path, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
    seen = _news("seen", STARTED - timedelta(hours=1), STARTED - timedelta(minutes=30))
    pages = Pages()
    pages.anomalies = [_anomaly()]
    pages.news = [seen]

    def execute(statement, params=None):
        compact = " ".join(statement.split())
        if "ingest.info_items" in compact:
            return Cursor([seen])
        return Pages.execute(pages, statement, params)

    pages.execute = execute
    client = Quiet()
    assert morning_main([], connection=pages, clock=FrozenClock(MORNING), client=client) == 0
    assert client.tasks == ["move_card", "claim_extraction"]
    assert pages.jobs[0]["status"] == "ok"
    assert any(statement.startswith("INSERT INTO perception.reports") for statement, _params in pages.calls)
    text = (tmp_path / f"daily_page_{DAY}.txt").read_text(encoding="utf-8")
    assert "NVDA" in text

    broken = Pages(fail_save=True)
    broken.anomalies = [_anomaly()]
    broken.execute = lambda statement, params=None: (
        Cursor([seen])
        if "ingest.info_items" in " ".join(statement.split())
        else Pages.execute(broken, statement, params)
    )
    assert morning_main([], connection=broken, clock=FrozenClock(MORNING), client=Quiet()) == 1
    assert broken.jobs[0]["status"] == "failed"
    assert "保存失败" in broken.jobs[0]["error_summary"]
    assert (tmp_path / f"daily_page_{DAY}.txt").exists()


def test_tracks_reads_the_saved_stage_and_does_not_call_the_model():
    moment = slot_moment(DAY, "attribution_tracks")
    pages = Pages()
    pages.anomalies = [_anomaly()]
    pages.jobs.append(
        {
            "id": 1,
            "task_name": "attribution_candidates",
            "trade_date": DAY,
            "status": "ok",
            "ended_at": slot_moment(DAY, "attribution_candidates"),
            "error_summary": None,
        }
    )
    client = Boom()
    assert stage_main(["--task", "attribution_tracks"], connection=pages, clock=FrozenClock(moment), client=client) == 0
    assert any(statement.startswith("INSERT INTO perception.") for statement, _params in pages.calls)
    tracks = next(job for job in pages.jobs if job["task_name"] == "attribution_tracks")
    assert tracks["status"] == "ok"
    missing = Pages()
    missing.anomalies = [_anomaly()]
    assert (
        stage_main(["--task", "attribution_tracks"], connection=missing, clock=FrozenClock(moment), client=Boom()) == 1
    )
    assert missing.jobs[0]["status"] == "failed"
    assert "缺少已成功的attribution_candidates" in missing.jobs[0]["error_summary"]
    assert not any(statement.startswith("INSERT INTO perception.") for statement, _params in missing.calls)


def test_labels_writes_the_snapshot_after_the_previous_stage():
    moment = slot_moment(DAY, "attribution_labels")
    pages = Pages()
    for name in ("attribution_candidates", "attribution_tracks"):
        pages.jobs.append(
            {
                "id": len(pages.jobs) + 1,
                "task_name": name,
                "trade_date": DAY,
                "status": "ok",
                "ended_at": slot_moment(DAY, name),
                "error_summary": None,
            }
        )
    assert stage_main(["--task", "attribution_labels"], connection=pages, clock=FrozenClock(moment), client=Boom()) == 0
    assert pages.snapshots[0]["kind"] == "stage_completion"
    assert pages.snapshots[0]["status"] == "complete"
    labels = next(job for job in pages.jobs if job["task_name"] == "attribution_labels")
    assert labels["status"] == "ok"


def test_replay_uses_seen_news_and_dry_run_does_not_call_or_write(tmp_path):
    labels = slot_moment(DAY, "attribution_labels")
    seen = _news("seen", STARTED - timedelta(hours=2), STARTED - timedelta(hours=1))
    late = _news("late", STARTED - timedelta(hours=3), labels + timedelta(minutes=5))
    assert [item["info_id"] for item in visible_news([seen, late], labels)] == ["seen"]
    pages = Pages()
    client = Boom()
    result = replay_window(
        pages,
        FrozenClock(REAL),
        anomalies=[_anomaly()],
        items=[seen, late],
        days=(DAY,),
        client=client,
        dry_run=True,
        log_path=tmp_path / "dry.json",
    )
    assert result["calls"] == []
    assert pages.snapshots == []
    stage = result["days"][0]["stages"][0]
    assert stage["task_name"] == "attribution_candidates"
    assert stage["info_ids"] == ["seen"]
    assert stage["anomalies"] == 1
    assert stage["news"] == 1
    assert stage["calls"] == {"move_card": 1, "claim_extraction": 1, "anomaly_candidates": 1}
    assert result["days"][0]["stages"][1]["calls"] == {}
    assert result["days"][0]["stages"][2]["calls"] == {}
    logged = json.loads((tmp_path / "dry.json").read_text(encoding="utf-8"))
    assert logged["calls"] == []
    assert "late" not in json.dumps(stage)


def test_replay_snapshot_is_invisible_to_the_live_reader(tmp_path):
    seen = _news("seen", STARTED - timedelta(hours=2), STARTED - timedelta(hours=1))
    pages = Pages()
    client = Quiet()
    result = replay_window(
        pages,
        FrozenClock(REAL),
        anomalies=[_anomaly()],
        items=[seen],
        days=(DAY,),
        client=client,
        log_path=tmp_path / "run.json",
    )
    assert result["days"][0]["snapshot_id"] == 1
    stored = pages.snapshots[0]
    assert stored["kind"] == "historical_backfill"
    assert stored["snapshot_generated_at"] == REAL
    assert stored["source_asof"] == slot_moment(DAY, "attribution_labels")
    assert stored["jobs"][0]["replay"] is True
    assert {row["task_name"] for row in stored["jobs"]} == {
        "attribution_candidates",
        "attribution_tracks",
        "attribution_labels",
    }
    forbidden = ("linkage_events", "ticker_status", "candidates", "tracks", "claims", "reports", "market_day")
    assert not any(name in statement for statement, _params in pages.calls for name in forbidden)
    live = read_snapshot(pages, DAY, slot_moment(DAY, "attribution_labels"))
    assert live["complete"] is False
    found = read_replay_snapshot(pages, DAY)
    assert found["replay"] is True
    assert found["complete"] is True
    body = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert body["calls"][0]["task"] == "move_card"
    assert body["calls"][0]["input_hash"]
    assert body["calls"][0]["output"] == {"没有": True}


def test_later_slots_are_polled_once_and_registered(tmp_path):
    from scripts.schedule_attribution_stage import run_once

    moment = slot_moment(DAY, "attribution_tracks")
    calls = []

    def invoke(command, **kwargs):
        calls.append(command)
        return type("Done", (), {"returncode": 0})()

    root = tmp_path / "repo"
    first = run_once(
        root=root,
        task_name="attribution_tracks",
        clock=FrozenClock(moment),
        python=Path("/fixture/python"),
        run=invoke,
        load_environment=lambda _path: {},
    )
    assert first["status"] == "ok"
    assert calls[0][-2:] == ["--task", "attribution_tracks"]
    assert (
        run_once(
            root=root,
            task_name="attribution_tracks",
            clock=FrozenClock(moment + timedelta(seconds=20)),
            python=Path("/fixture/python"),
            run=invoke,
            load_environment=lambda _path: {},
        )["status"]
        == "already_attempted"
    )
    assert len(calls) == 1
    failed = run_once(
        root=tmp_path / "other",
        task_name="attribution_labels",
        clock=FrozenClock(slot_moment(DAY, "attribution_labels")),
        python=Path("/fixture/python"),
        run=lambda command, **kwargs: type("Done", (), {"returncode": 1})(),
        load_environment=lambda _path: {},
    )
    assert failed["status"] == "failed"
    config = ConfigParser(interpolation=None)
    config.read_string(configuration(Path("/fixture/inves-cog"), Path("/fixture/python")))
    for name in ("attribution_tracks", "attribution_labels"):
        command = config.get("program:" + name, "command")
        assert "schedule_attribution_stage.py" in command
        assert name in command
        assert config.getboolean("program:" + name, "autostart")
        assert config.getboolean("program:" + name, "autorestart")
    assert "schedule_morning_page.py" in config.get("program:morning_page", "command")
