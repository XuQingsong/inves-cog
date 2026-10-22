"""B-039 part 1: a finished day stays complete when a field is missing."""

import pytest

from inves_cog.perception.attribution.snapshot import capture_if_ready, read_snapshot
from tests.m8.test_b035 import AFTER, Pages, _field, _stored
from tests.m8.test_b036 import BEFORE, CUTOFF, DAY, Memory, _clock, _db_event, _jobs, _linkage

pytestmark = pytest.mark.phase1_blocking


def test_a_missing_display_field_does_not_hide_the_day():
    report = {}
    pages = Memory(_jobs(), [_db_event(report=report)])
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    event = stored["events"][0]
    assert event["fields"]["mechanism"]["value"] == "供给"
    assert event["fields"]["exposure"]["value"] == "直接"
    assert event["fields"]["next_filing_at"]["value"] is None
    assert event["fields"]["divergence_tag"]["value"] is None
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["source_events_asof"] == BEFORE.isoformat()
    assert found["events"][0]["mechanism"] == "供给"
    assert found["events"][0]["affected"][0]["ticker"] == "NVDA"
    gaps = found["missing"]["fields"]["evt-1"]
    assert "next_filing_at" in gaps
    assert "divergence_tag" in gaps


def test_a_missing_failed_or_late_stage_still_writes_nothing():
    missing = Memory(_jobs(skip={"attribution_tracks"}))
    failed = Memory(_jobs(status="failed"))
    late = Memory(_jobs(ended=AFTER))
    assert capture_if_ready(missing, DAY, _clock(CUTOFF)) is None
    assert capture_if_ready(failed, DAY, _clock(CUTOFF)) is None
    assert capture_if_ready(late, DAY, _clock(CUTOFF)) is None
    assert missing.snapshots == []
    assert failed.snapshots == []
    assert late.snapshots == []


def test_an_event_without_visible_lifecycle_stays_on_a_complete_day():
    pages = Memory(_jobs(), [_linkage(event_id="plain", history=[])])
    capture_if_ready(pages, DAY, _clock(CUTOFF))
    stored = pages.snapshots[0]
    assert stored["status"] == "complete"
    event = stored["events"][0]
    assert event["event_id"] == "plain"
    assert event["fields"]["lifecycle"]["value"] is None
    assert event["fields"]["lifecycle"]["missing_reason"]
    assert event["fields"]["mechanism"]["value"] == "供给"
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["complete"] is True
    assert found["events"][0]["lifecycle"] is None
    assert found["events"][0]["mechanism"] == "供给"
    assert "lifecycle" in found["missing"]["fields"]["plain"]


def test_a_field_time_after_the_cutoff_is_missing_without_clearing_siblings():
    row = _stored()
    row["events"][0]["fields"]["next_filing_at"] = _field("2026-11-01", AFTER)
    found = read_snapshot(Pages([row]), DAY, CUTOFF)
    assert found["complete"] is True
    event = found["events"][0]
    assert event["mechanism"] == "供给"
    assert event["affected"][0]["ticker"] == "NVDA"
    assert event["next_filing_at"] is None
    assert event["divergence_tag"] == "分化"
    assert found["missing"]["fields"]["evt-1"]["next_filing_at"] == "来源时间晚于 cutoff"
