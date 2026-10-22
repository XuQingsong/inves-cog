"""B-036: M8 appends an immutable PIT snapshot after the day's stages finish."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.snapshot import capture_backfill, capture_if_ready, read_snapshot

ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-10-15"
CUTOFF = datetime.fromisoformat("2026-10-16T12:00:00+08:00")
BEFORE = datetime.fromisoformat("2026-10-16T09:40:00+08:00")
EARLIER = datetime.fromisoformat("2026-10-16T09:20:00+08:00")
AFTER = datetime.fromisoformat("2026-10-16T12:40:00+08:00")
STAGES = ("attribution_candidates", "attribution_tracks", "attribution_labels")

pytestmark = pytest.mark.phase1_blocking


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _unwrap(value):
    return value.obj if hasattr(value, "obj") else value


class Memory:
    def __init__(self, jobs, events=None):
        self.jobs = list(jobs)
        self.events = list(events or [])
        self.snapshots = []
        self.statements = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.statements.append(compact)
        if compact.upper().startswith(("BEGIN", "ROLLBACK")):
            return Cursor([])
        if compact.upper().startswith("INSERT INTO PERCEPTION.M9_INPUT_SNAPSHOTS"):
            row = {
                "snapshot_id": len(self.snapshots) + 1,
                "trade_date": params[0],
                "snapshot_generated_at": params[1],
                "source_asof": params[2],
                "status": params[3],
                "kind": params[4],
                "jobs": _unwrap(params[5]),
                "events": _unwrap(params[6]),
                "missing": _unwrap(params[7]),
            }
            self.snapshots.append(row)
            return Cursor([{"snapshot_id": row["snapshot_id"]}])
        if "FROM perception.m9_input_snapshots" in compact:
            return Cursor(self.snapshots)
        if "ingest.job_runs" in compact:
            day = str(params[0])[:10]
            return Cursor([row for row in self.jobs if str(row["trade_date"])[:10] == day])
        if "perception.linkage_events" in compact:
            return Cursor(self.events)
        raise AssertionError(compact)


def _jobs(ended=BEFORE, status="ok", skip=()):
    rows = []
    for index, name in enumerate(STAGES, start=1):
        if name in skip:
            continue
        rows.append({"id": index, "task_name": name, "trade_date": DAY, "status": status, "ended_at": ended})
    return rows


def _entry(when, new, evidence):
    return {"at": when, "old": None, "new": new, "trigger": "测试", "evidence_ids": evidence}


def _linkage(**changes):
    row = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "history": [_entry(EARLIER, "假设中", ["info-1"])],
        "generated_at": EARLIER,
        "lifecycle": "市场确认",
        "mechanism": "供给",
    }
    row.update(changes)
    return row


def _timed(value, when=EARLIER):
    return {"value": value, "at": when}


def _full_event(**changes):
    row = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "evidence_ids": ["info-1"],
        "lifecycle": _timed("假设中"),
        "mechanism": _timed("供给"),
        "ticker": _timed("NVDA"),
        "exposure": _timed("直接"),
        "direction": _timed("不利"),
        "divergence_tag": _timed("分化"),
        "dimensions": _timed({"emotion": "初现"}),
        "next_filing_at": _timed("2026-11-01"),
        "systemic_tag": _timed("无"),
        "deadline_outcome": _timed("未到"),
    }
    row.update(changes)
    return row


def _clock(instant):
    return FrozenClock(instant)


def test_successful_stages_with_no_events_write_a_complete_snapshot():
    clock = _clock(CUTOFF)
    pages = Memory(_jobs())
    snapshot_id = capture_if_ready(pages, DAY, clock)
    assert snapshot_id == 1
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    assert stored["kind"] == "stage_completion"
    assert stored["events"] == []
    assert stored["snapshot_generated_at"] == clock.now_utc()
    assert stored["source_asof"] == BEFORE
    assert str(stored["source_asof"])[:10] != DAY
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["events"] == []
    assert found["source_events_asof"] == BEFORE.isoformat()
    hidden = read_snapshot(pages, DAY, EARLIER)
    assert hidden["complete"] is False
    assert hidden["events"] == []


def test_complete_event_fields_use_the_injected_clock():
    source = (ROOT / "src/inves_cog/perception/attribution/snapshot.py").read_text()
    assert "datetime.now" not in source
    first = _clock(BEFORE)
    second = _clock(CUTOFF)
    pages = Memory(_jobs(ended=EARLIER))
    capture_if_ready(pages, DAY, first, events=[_full_event()])
    capture_if_ready(pages, DAY, second, events=[_full_event()])
    assert pages.snapshots[0]["snapshot_generated_at"] == first.now_utc()
    assert pages.snapshots[1]["snapshot_generated_at"] == second.now_utc()
    assert pages.snapshots[0]["snapshot_generated_at"] != pages.snapshots[1]["snapshot_generated_at"]
    found = read_snapshot(pages, DAY, CUTOFF)
    event = found["events"][0]
    assert found["complete"] is True
    assert event["mechanism"] == "供给"
    assert event["direction"] == "不利"
    assert event["affected"][0]["exposure"] == "直接"
    assert event["systemic_tag"] == "无"
    assert event["deadline_outcome"] == "未到"
    early = read_snapshot(pages, DAY, EARLIER)
    assert early["complete"] is False


def test_fields_without_a_source_time_stay_null():
    clock = _clock(CUTOFF)
    pages = Memory(_jobs(), [_linkage(price_direction="down")])
    snapshot_id = capture_if_ready(pages, DAY, clock)
    assert snapshot_id == 1
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    event = stored["events"][0]
    text = json.dumps(event, ensure_ascii=False)
    assert event["fields"]["lifecycle"]["value"] == "假设中"
    assert event["fields"]["lifecycle"]["at"] == EARLIER.isoformat()
    assert event["fields"]["mechanism"]["value"] == "供给"
    assert event["fields"]["mechanism"]["at"] == clock.now_utc().isoformat()
    assert event["fields"]["mechanism"]["at"] != BEFORE.isoformat()
    assert event["fields"]["direction"]["value"] is None
    assert "涨跌" in event["fields"]["direction"]["missing_reason"]
    assert "市场确认" not in text
    assert "down" not in text
    for name in (
        "ticker",
        "exposure",
        "divergence_tag",
        "dimensions",
        "next_filing_at",
        "systemic_tag",
        "deadline_outcome",
    ):
        assert event["fields"][name]["value"] is None
        assert event["fields"][name]["missing_reason"]
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["source_events_asof"] == BEFORE.isoformat()
    assert found["events"][0]["mechanism"] == "供给"
    assert found["events"][0]["lifecycle"] == "假设中"
    assert found["events"][0]["direction"] is None
    assert "ticker" in found["missing"]["fields"]["evt-1"]


def _db_event(**changes):
    row = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "history": [_entry(EARLIER, "假设中", ["info-1"])],
        "generated_at": EARLIER,
        "mechanism": "供给",
        "deadline_outcome": "未到",
        "tickers": [{"ticker": "NVDA", "exposure": "直接", "mechanism": "供给"}],
        "candidates": [{"mechanism": "需求", "affected": [{"ticker": "AMD"}]}],
        "tracks": [
            {"trade_date": "2026-10-14", "emotion": "昨日", "capital": "昨日", "fundamental": "昨日"},
            {"trade_date": DAY, "emotion": "初现", "capital": "观望", "fundamental": "未证"},
        ],
        "claims": [{"direction": "不利"}],
        "report": {"divergence_label": "情绪性折价", "next_filing_at": "2026-11-01", "deadline_outcome": "条件风险"},
        "systemic_event_tag": "无",
        "price_direction": "down",
        "direction": "down",
    }
    row.update(changes)
    return row


def test_a_full_m8_event_maps_every_available_field():
    source = (ROOT / "src/inves_cog/perception/attribution/snapshot.py").read_text()
    assert "perception.ticker_status" in source
    assert "perception.tracks" in source
    assert "perception.reports" in source
    assert "perception.market_day" in source
    assert "perception.claims" in source
    assert "a.direction" not in source
    assert "e.lifecycle" not in source
    clock = _clock(CUTOFF)
    pages = Memory(_jobs(), [_db_event()])
    capture_if_ready(pages, DAY, clock)
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    assert stored["source_asof"] == BEFORE
    event = stored["events"][0]
    observed = clock.now_utc().isoformat()
    assert event["fields"]["lifecycle"] == {"value": "假设中", "at": EARLIER.isoformat(), "missing_reason": None}
    assert event["fields"]["mechanism"]["value"] == "供给"
    assert event["fields"]["mechanism"]["at"] == observed
    assert event["fields"]["ticker"]["value"] == "NVDA"
    assert event["fields"]["exposure"]["value"] == "直接"
    assert event["fields"]["direction"]["value"] == "不利"
    assert event["fields"]["divergence_tag"]["value"] == "情绪性折价"
    assert event["fields"]["dimensions"]["value"] == {"emotion": "初现", "capital": "观望", "fundamental": "未证"}
    assert event["fields"]["next_filing_at"]["value"] == "2026-11-01"
    assert event["fields"]["next_filing_at"]["at"] == observed
    assert event["fields"]["systemic_tag"]["value"] == "无"
    assert event["fields"]["deadline_outcome"]["value"] == "未到"
    text = json.dumps(event, ensure_ascii=False)
    assert "市场确认" not in text
    assert "down" not in text
    assert "昨日" not in text
    assert "条件风险" not in text
    assert "AMD" not in text
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["events"][0]["direction"] == "不利"
    assert found["events"][0]["affected"][0]["ticker"] == "NVDA"
    assert found["events"][0]["affected"][0]["exposure"] == "直接"
    assert found["source_events_asof"] == BEFORE.isoformat()


def test_one_missing_field_keeps_the_others():
    report = {"divergence_label": "情绪性折价"}
    pages = Memory(_jobs(), [_db_event(report=report)])
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    event = stored["events"][0]
    assert event["fields"]["mechanism"]["value"] == "供给"
    assert event["fields"]["exposure"]["value"] == "直接"
    assert event["fields"]["direction"]["value"] == "不利"
    assert event["fields"]["divergence_tag"]["value"] == "情绪性折价"
    assert event["fields"]["next_filing_at"]["value"] is None
    assert event["fields"]["next_filing_at"]["missing_reason"]
    assert stored["missing"]["fields"]["evt-1"] == {
        "next_filing_at": event["fields"]["next_filing_at"]["missing_reason"]
    }
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["source_events_asof"] == BEFORE.isoformat()
    assert found["events"][0]["mechanism"] == "供给"
    assert found["events"][0]["next_filing_at"] is None
    assert "next_filing_at" in found["missing"]["fields"]["evt-1"]
    conflict = Memory(_jobs(), [_db_event(claims=[{"direction": "不利"}, {"direction": "有利"}])])
    capture_if_ready(conflict, DAY, _clock(CUTOFF))
    direction = conflict.snapshots[0]["events"][0]["fields"]["direction"]
    assert direction["value"] is None
    assert direction["missing_reason"] == "多条说法的方向不一致"
    assert conflict.snapshots[0]["events"][0]["fields"]["mechanism"]["value"] == "供给"
    assert "down" not in json.dumps(conflict.snapshots[0]["events"], ensure_ascii=False)


def test_missing_or_failed_job_does_not_write():
    missing = Memory(_jobs(skip={"attribution_labels"}))
    failed = Memory(_jobs(status="failed"))
    assert capture_if_ready(missing, DAY, _clock(CUTOFF)) is None
    assert capture_if_ready(failed, DAY, _clock(CUTOFF)) is None
    assert missing.snapshots == []
    assert failed.snapshots == []
    assert not any(item.upper().startswith("INSERT") for item in missing.statements)


def test_jobs_and_events_after_the_cutoff_stay_out():
    late_job = Memory(_jobs(ended=AFTER))
    assert capture_if_ready(late_job, DAY, _clock(CUTOFF)) is None
    assert late_job.snapshots == []
    future = Memory(
        _jobs(),
        [
            _linkage(event_id="future", generated_at=AFTER, history=[_entry(AFTER, "市场确认", ["info-9"])]),
            _linkage(event_id="unproven", generated_at=EARLIER, history=[_entry(AFTER, "市场确认", ["info-8"])]),
        ],
    )
    capture_if_ready(future, DAY, _clock(CUTOFF))
    stored = future.snapshots[0]
    assert stored["status"] == "complete"
    assert [item["event_id"] for item in stored["events"]] == ["unproven"]
    assert stored["events"][0]["fields"]["lifecycle"]["value"] is None
    assert "历史时间" in stored["events"][0]["fields"]["lifecycle"]["missing_reason"]
    assert "future" not in str(stored["events"])
    assert "市场确认" not in json.dumps(stored["events"], ensure_ascii=False)
    assert "lifecycle" in stored["missing"]["fields"]["unproven"]
    only_future = Memory(_jobs(), [_linkage(generated_at=AFTER, history=[_entry(AFTER, "市场确认", ["info-9"])])])
    capture_if_ready(only_future, DAY, _clock(CUTOFF))
    assert only_future.snapshots[0]["status"] == "complete"
    assert only_future.snapshots[0]["events"] == []
    assert "info-9" not in json.dumps(only_future.snapshots[0], ensure_ascii=False, default=str)


def test_only_the_history_version_at_the_clock_is_stored():
    pages = Memory(
        _jobs(),
        [
            _linkage(
                history=[
                    _entry(EARLIER, "假设中", ["info-1"]),
                    _entry(AFTER, "市场确认", ["info-2"]),
                ]
            )
        ],
    )
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    event = pages.snapshots[0]["events"][0]
    assert event["fields"]["lifecycle"]["value"] == "假设中"
    assert event["observed_at"] == EARLIER.isoformat()
    assert event["evidence_ids"] == ["info-1"]
    assert "市场确认" not in json.dumps(event, ensure_ascii=False)
    assert "info-2" not in json.dumps(event, ensure_ascii=False)


def test_append_only_snapshot_cannot_be_overwritten():
    source = (ROOT / "src/inves_cog/perception/attribution/snapshot.py").read_text().upper()
    assert "UPDATE PERCEPTION.M9_INPUT_SNAPSHOTS" not in source
    assert "DELETE FROM PERCEPTION.M9_INPUT_SNAPSHOTS" not in source
    pages = Memory(_jobs())
    capture_if_ready(pages, DAY, _clock(BEFORE))
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    assert [row["snapshot_id"] for row in pages.snapshots] == [1, 2]
    assert pages.snapshots[0]["snapshot_generated_at"] == _clock(BEFORE).now_utc()
    assert not any(item.upper().startswith("UPDATE") or item.upper().startswith("DELETE") for item in pages.statements)
    migration = (ROOT / "migrations/phase1_m8_0002_m9_input_snapshots.sql").read_text()
    grants = [line.strip() for line in migration.splitlines() if line.strip().startswith("GRANT")]
    assert grants == [
        "GRANT SELECT, INSERT ON TABLE perception.m9_input_snapshots TO role_perception;",
        "GRANT SELECT ON TABLE perception.m9_input_snapshots TO role_shadow;",
        "GRANT USAGE, SELECT ON SEQUENCE perception.m9_input_snapshots_snapshot_id_seq TO role_perception;",
    ]
    assert "REVOKE ALL ON TABLE perception.m9_input_snapshots" in migration
    assert "m9_input_snapshots is append-only" in migration
    assert "CREATE ROLE" not in migration
    assert "BEFORE UPDATE OR DELETE" in migration


def test_backfill_uses_original_times_and_the_real_generation_time():
    pages = Memory(_jobs(ended=EARLIER))
    clock = _clock(AFTER)
    snapshot_id = capture_backfill(pages, DAY, clock, [_full_event()])
    assert snapshot_id == 1
    stored = pages.snapshots[0]
    assert stored["kind"] == "historical_backfill"
    assert stored["status"] == "complete"
    assert stored["snapshot_generated_at"] == clock.now_utc()
    assert stored["source_asof"] == EARLIER
    assert stored["events"][0]["fields"]["mechanism"]["at"] == EARLIER.isoformat()
    hidden = read_snapshot(pages, DAY, CUTOFF)
    assert hidden["complete"] is False
    visible = read_snapshot(pages, DAY, AFTER)
    assert visible["complete"] is True
    assert visible["source_events_asof"] == EARLIER.isoformat()
    stripped = Memory([])
    event = _full_event(mechanism={"value": "供给", "at": None})
    capture_backfill(stripped, DAY, clock, [event])
    assert stripped.snapshots[0]["status"] == "degraded"
    assert stripped.snapshots[0]["events"][0]["fields"]["mechanism"]["value"] is None
    assert "供给" not in json.dumps(stripped.snapshots[0]["events"], ensure_ascii=False)
    empty = Memory([])
    assert capture_backfill(empty, DAY, clock, [{"event_id": "evt-1", "mechanism": {"value": "供给"}}]) is None
    assert empty.snapshots == []


def test_naive_clock_is_rejected():
    class Naive:
        def now_utc(self):
            return datetime(2026, 10, 16, 12, 0)

    pages = Memory(_jobs())
    with pytest.raises(ValueError):
        capture_if_ready(pages, DAY, Naive())
    assert pages.snapshots == []


def test_labels_success_captures_a_snapshot():
    from inves_cog.perception.attribution.chain import run_scheduled

    class Connection(Memory):
        def __init__(self):
            super().__init__(_jobs(ended=EARLIER))
            self.calls = []

        def execute(self, statement, params=None):
            self.calls.append((statement, params))
            if "INSERT INTO ingest.job_runs" in statement:
                return Cursor([{"id": 7}])
            if "UPDATE ingest.job_runs" in statement:
                return Cursor([])
            return super().execute(statement, params)

    labels = datetime.fromisoformat("2026-10-16T12:30:00+08:00")
    candidates = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
    recorded = run_scheduled(
        labels,
        anomalies=[],
        items=[],
        connection=Connection(),
        clock=_clock(CUTOFF),
        trade_date=DAY,
    )
    assert recorded["snapshot_id"] == 1
    skipped = run_scheduled(
        candidates,
        anomalies=[],
        items=[],
        connection=Connection(),
        clock=_clock(CUTOFF),
        trade_date=DAY,
    )
    assert "snapshot_id" not in skipped
    assert CUTOFF.astimezone(timezone.utc) == _clock(CUTOFF).now_utc()


def test_roles_cannot_update_the_snapshot_on_disposable_database():
    import psycopg

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    clock = _clock(CUTOFF)
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin") as connection:
        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE role_perception")
        for name in STAGES:
            connection.execute(
                """
                INSERT INTO ingest.job_runs (
                    task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
                ) VALUES (%s, %s, %s, %s, 'ok', 0, NULL, 'b036')
                """,
                (name, DAY, EARLIER, BEFORE),
            )
        snapshot_id = capture_if_ready(connection, DAY, clock)
        assert snapshot_id is not None
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE perception.m9_input_snapshots SET status = 'degraded' WHERE snapshot_id = %s",
                (snapshot_id,),
            )
        connection.rollback()

        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE role_perception")
        for name in STAGES:
            connection.execute(
                """
                INSERT INTO ingest.job_runs (
                    task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
                ) VALUES (%s, %s, %s, %s, 'ok', 0, NULL, 'b036')
                """,
                (name, DAY, EARLIER, BEFORE),
            )
        snapshot_id = capture_if_ready(connection, DAY, clock)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM perception.m9_input_snapshots WHERE snapshot_id = %s", (snapshot_id,))
        connection.rollback()

        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE role_perception")
        for name in STAGES:
            connection.execute(
                """
                INSERT INTO ingest.job_runs (
                    task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
                ) VALUES (%s, %s, %s, %s, 'ok', 0, NULL, 'b036')
                """,
                (name, DAY, EARLIER, BEFORE),
            )
        snapshot_id = capture_if_ready(connection, DAY, clock)
        connection.execute("SET LOCAL ROLE role_shadow")
        status = connection.execute(
            "SELECT status FROM perception.m9_input_snapshots WHERE snapshot_id = %s",
            (snapshot_id,),
        ).fetchone()[0]
        assert status == "complete"
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                """
                INSERT INTO perception.m9_input_snapshots (
                    trade_date, snapshot_generated_at, source_asof, status, kind, jobs, events, missing
                ) VALUES (%s, %s, %s, 'complete', 'stage_completion', '[]', '[]', '{}')
                """,
                (DAY, CUTOFF, BEFORE),
            )
        connection.rollback()

        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE role_overlay")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT snapshot_id FROM perception.m9_input_snapshots")
        connection.rollback()

        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE role_perception")
        for name in STAGES:
            connection.execute(
                """
                INSERT INTO ingest.job_runs (
                    task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
                ) VALUES (%s, %s, %s, %s, 'ok', 0, NULL, 'b036')
                """,
                (name, DAY, EARLIER, BEFORE),
            )
        snapshot_id = capture_if_ready(connection, DAY, clock)
        connection.execute("RESET ROLE")
        with pytest.raises(psycopg.Error, match="append-only"):
            connection.execute(
                "UPDATE perception.m9_input_snapshots SET status = 'degraded' WHERE snapshot_id = %s",
                (snapshot_id,),
            )
        connection.rollback()
