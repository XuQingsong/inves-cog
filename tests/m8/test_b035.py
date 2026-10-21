"""M9 reads a stored M8 snapshot. Live tables are not a snapshot."""

from datetime import datetime

import pytest

from inves_cog.perception.attribution.snapshot import m8_provider, read_snapshot

DAY = "2026-10-15"
CUTOFF = datetime.fromisoformat("2026-10-16T12:00:00+08:00")
BEFORE = datetime.fromisoformat("2026-10-16T09:40:00+08:00")
EARLIER = datetime.fromisoformat("2026-10-16T09:20:00+08:00")
AFTER = datetime.fromisoformat("2026-10-16T12:40:00+08:00")

pytestmark = pytest.mark.phase1_blocking


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class Pages:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.statements = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.statements.append(compact)
        if compact.upper().startswith("BEGIN") or compact.upper().startswith("ROLLBACK"):
            return Cursor([])
        if "perception.m9_input_snapshots" in compact:
            return Cursor(self.snapshots)
        raise AssertionError(compact)


def _field(value, when=EARLIER):
    return {"value": value, "at": when.isoformat(), "missing_reason": None}


def _stored(**changes):
    event = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "observed_at": EARLIER.isoformat(),
        "evidence_ids": ["info-1"],
        "fields": {
            "lifecycle": _field("假设中"),
            "mechanism": _field("供给"),
            "ticker": _field("NVDA"),
            "exposure": _field("直接"),
            "direction": _field("不利"),
            "divergence_tag": _field("分化"),
            "dimensions": _field({"emotion": "初现"}),
            "next_filing_at": _field("2026-11-01"),
            "systemic_tag": _field("无"),
            "deadline_outcome": _field("未到"),
        },
    }
    row = {
        "snapshot_id": 1,
        "trade_date": DAY,
        "snapshot_generated_at": BEFORE,
        "source_asof": EARLIER,
        "status": "complete",
        "kind": "stage_completion",
        "jobs": [{"id": 1, "task_name": "attribution_labels", "status": "ok", "ended_at": BEFORE.isoformat()}],
        "events": [event],
        "missing": {"stages": [], "events": [], "fields": {}},
    }
    row.update(changes)
    return row


def _read(snapshots, cutoff=CUTOFF):
    pages = Pages(snapshots)
    found = read_snapshot(pages, DAY, cutoff)
    called = m8_provider(pages)(DAY, cutoff)
    assert called["complete"] == found["complete"]
    text = "\n".join(pages.statements).upper()
    assert "REPEATABLE READ" in text and "READ ONLY" in text
    assert "INSERT" not in text and "UPDATE" not in text and "SET ROLE" not in text
    assert "ingest.job_runs" not in text and "linkage_events" not in text
    return found


def test_live_jobs_without_a_stored_snapshot_are_not_complete():
    found = _read([])
    assert found["complete"] is False
    assert found["events"] == []
    assert found["source_events_asof"] is None
    assert found["source_ids"] == {"jobs": [], "events": []}
    assert "完整快照" in " ".join(found["missing"]["stages"])


def test_future_snapshot_stays_out():
    found = _read([_stored(snapshot_generated_at=AFTER, source_asof=AFTER)])
    assert found["complete"] is False
    assert found["events"] == []
    assert "供给" not in str(found["events"])


def test_degraded_snapshot_is_not_a_complete_overlay():
    found = _read(
        [
            _stored(
                status="degraded",
                events=[
                    {
                        "event_id": "evt-1",
                        "anomaly_id": "anom-1",
                        "observed_at": EARLIER.isoformat(),
                        "evidence_ids": ["info-1"],
                        "fields": {"lifecycle": _field("市场确认"), "mechanism": _field("供给")},
                    }
                ],
                missing={"stages": [], "events": [], "fields": {"evt-1": {"exposure": "没有生成时间"}}},
            )
        ]
    )
    assert found["complete"] is False
    assert found["source_events_asof"] is None
    assert found["events"][0]["lifecycle"] == "市场确认"
    assert found["events"][0]["mechanism"] == "供给"
    assert found["events"][0]["affected"] == []
    assert "没有生成时间" in str(found["missing"])


def test_a_newer_degraded_snapshot_does_not_hide_an_older_complete_one():
    older = _stored(snapshot_id=1, snapshot_generated_at=EARLIER)
    newer = _stored(snapshot_id=2, snapshot_generated_at=BEFORE, status="degraded")
    found = _read([newer, older])
    assert found["complete"] is True
    assert found["source_events_asof"] == EARLIER.isoformat()
    assert found["events"][0]["lifecycle"] == "假设中"


def test_visible_complete_snapshot_is_returned():
    older = _stored(snapshot_id=1, snapshot_generated_at=EARLIER)
    newer = _stored(snapshot_id=2, snapshot_generated_at=BEFORE)
    future = _stored(snapshot_id=3, snapshot_generated_at=AFTER)
    found = _read([future, older, newer])
    assert found["complete"] is True
    assert found["source_events_asof"] == EARLIER.isoformat()
    event = found["events"][0]
    assert event["lifecycle"] == "假设中"
    assert event["mechanism"] == "供给"
    assert event["direction"] == "不利"
    assert event["evidence_ids"] == ["info-1"]
    assert event["affected"][0]["ticker"] == "NVDA"
    assert found["source_ids"]["events"][0]["event_id"] == "evt-1"
    assert found["source_ids"]["jobs"][0]["task_name"] == "attribution_labels"
