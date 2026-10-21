"""B-035: M9 reads only an M8 snapshot already visible at the cutoff."""

from datetime import datetime

import pytest

from inves_cog.perception.attribution.snapshot import m8_provider, read_snapshot

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


class Pages:
    def __init__(self, jobs, events):
        self.jobs = list(jobs)
        self.events = list(events)
        self.statements = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.statements.append(compact)
        if compact.upper().startswith("BEGIN") or compact.upper().startswith("ROLLBACK"):
            return Cursor([])
        if "ingest.job_runs" in compact:
            day = str(params[0])[:10]
            rows = [row for row in self.jobs if str(row["trade_date"])[:10] == day]
            return Cursor(rows)
        if "perception.linkage_events" in compact:
            return Cursor(self.events)
        raise AssertionError(compact)


def _jobs(ended=BEFORE, status="ok", skip=()):
    rows = []
    for index, name in enumerate(STAGES, start=1):
        if name in skip:
            continue
        rows.append(
            {
                "id": index,
                "task_name": name,
                "trade_date": DAY,
                "status": status,
                "ended_at": ended,
            }
        )
    return rows


def _entry(when, new, evidence):
    return {"at": when, "old": None, "new": new, "trigger": "测试", "evidence_ids": evidence}


def _event(**changes):
    row = {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "lifecycle": "市场确认",
        "history": [_entry(EARLIER, "假设中", ["info-1"])],
        "mechanism": "供给",
        "deadline_outcome": "条件风险",
        "generated_at": EARLIER,
    }
    row.update(changes)
    return row


def _read(jobs, events, cutoff=CUTOFF):
    pages = Pages(jobs, events)
    found = read_snapshot(pages, DAY, cutoff)
    called = m8_provider(pages)(DAY, cutoff)
    assert called["complete"] == found["complete"]
    text = "\n".join(pages.statements).upper()
    assert "REPEATABLE READ" in text and "READ ONLY" in text
    assert "INSERT" not in text and "UPDATE" not in text and "SET ROLE" not in text
    return found


def test_finished_stages_with_no_events_are_complete():
    found = _read(_jobs(), [])
    assert found["complete"] is True
    assert found["events"] == []
    assert found["source_events_asof"] == BEFORE.isoformat()
    assert [row["task_name"] for row in found["source_ids"]["jobs"]] == list(STAGES)
    assert found["missing"]["stages"] == []


def test_missing_failed_or_late_stage_is_not_complete():
    missing = _read(_jobs(skip={"attribution_labels"}), [])
    failed = _read(_jobs(status="failed"), [])
    late = _read(_jobs(ended=AFTER), [], cutoff=CUTOFF)
    assert missing["complete"] is False
    assert failed["complete"] is False
    assert late["complete"] is False
    assert "attribution_labels" in " ".join(missing["missing"]["stages"])
    assert late["source_events_asof"] in {None, ""}
    assert late["events"] == []


def test_late_events_stay_out():
    found = _read(
        _jobs(),
        [
            _event(event_id="late-anomaly", generated_at=AFTER, history=[_entry(EARLIER, "假设中", ["info-1"])]),
            _event(event_id="late-history", history=[_entry(AFTER, "市场确认", ["info-9"])]),
            _event(),
        ],
    )
    identifiers = [row["event_id"] for row in found["events"]]
    assert identifiers == ["evt-1"]
    assert "info-9" not in str(found)


def test_history_without_a_visible_time_stays_incomplete():
    found = _read(_jobs(), [_event(history=[], lifecycle="已验证·有影响")])
    assert found["complete"] is False
    assert found["events"] == []
    assert "已验证" not in str(found["events"])
    assert any("evt-1" in item for item in found["missing"]["events"])


def test_only_the_version_known_at_the_cutoff_is_returned():
    found = _read(
        _jobs(),
        [
            _event(
                history=[
                    _entry(EARLIER, "假设中", ["info-1"]),
                    _entry(AFTER, "市场确认", ["info-2"]),
                ]
            )
        ],
    )
    assert len(found["events"]) == 1
    event = found["events"][0]
    assert event["lifecycle"] == "假设中"
    assert event["observed_at"] == EARLIER.isoformat()
    assert "市场确认" not in str(event)
    assert "供给" not in str(event)
    assert "条件风险" not in str(event)
    assert event["evidence_ids"] == ["info-1"]


def test_source_ids_and_field_gaps_are_explicit():
    found = _read(_jobs(), [_event()])
    event = found["events"][0]
    assert event["event_id"] == "evt-1"
    assert event["anomaly_id"] == "anom-1"
    assert found["source_ids"]["events"][0]["evidence_ids"] == ["info-1"]
    gaps = found["missing"]["fields"]
    assert "mechanism" in gaps and "exposure" in gaps and "direction" in gaps and "divergence_tag" in gaps
    assert found["complete"] is False
