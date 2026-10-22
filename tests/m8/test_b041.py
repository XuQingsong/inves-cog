"""B-041: a null deadline result is missing only once the deadline day has arrived."""

from datetime import datetime

import pytest

from inves_cog.perception.attribution.replay_window import _event
from inves_cog.perception.attribution.snapshot import (
    append_replay_snapshot,
    capture_if_ready,
    read_replay_snapshot,
    read_snapshot,
)
from tests.m8.test_b036 import AFTER, BEFORE, CUTOFF, DAY, EARLIER, Memory, _clock, _entry, _jobs

pytestmark = pytest.mark.phase1_blocking

OPEN = datetime.fromisoformat("2026-10-16T09:00:00+08:00")
SEEN = datetime.fromisoformat("2026-10-16T08:40:00+08:00")
ARRIVED = "截止日已到（{day}）但没有支持/反证/条件风险结果"
UNKNOWN = "截止日未知"


def _open(deadline_on=None, outcome=None, seen=EARLIER):
    report = {}
    if deadline_on is not None:
        report["deadline_on"] = deadline_on
    if outcome is not None:
        report["deadline_outcome"] = outcome
    return {
        "event_id": "evt-1",
        "anomaly_id": "anom-1",
        "history": [_entry(seen, "假设中", ["info-1"])],
        "generated_at": seen,
        "mechanism": "供给",
        "deadline_outcome": outcome,
        "tickers": [{"ticker": "NVDA", "exposure": "直接"}],
        "candidates": [],
        "tracks": [{"trade_date": DAY, "emotion": "初现", "capital": "观望", "fundamental": "未证"}],
        "claims": [{"direction": "不利"}],
        "report": report,
        "systemic_event_tag": "无",
    }


def _read(row, *, ended=BEFORE, clock=CUTOFF, cutoff=CUTOFF):
    pages = Memory(_jobs(ended=ended), [row])
    assert capture_if_ready(pages, DAY, _clock(clock)) == 1
    return read_snapshot(pages, DAY, cutoff)


def test_a_future_deadline_is_not_a_missing_result():
    found = _read(_open("2026-11-06"))
    event = found["events"][0]
    assert event["deadline_on"] == "2026-11-06"
    assert event["deadline_outcome"] is None
    assert "deadline_outcome" not in found["missing"]["fields"].get("evt-1", {})


def test_an_arrived_deadline_without_a_result_is_missing():
    found = _read(_open("2026-10-15"))
    event = found["events"][0]
    assert event["deadline_on"] == "2026-10-15"
    assert event["deadline_outcome"] is None
    assert found["missing"]["fields"]["evt-1"]["deadline_outcome"] == ARRIVED.format(day="2026-10-15")


def test_the_deadline_day_itself_counts_as_arrived():
    found = _read(_open("2026-10-16"))
    assert found["missing"]["fields"]["evt-1"]["deadline_outcome"] == ARRIVED.format(day="2026-10-16")


def test_an_unknown_deadline_is_missing():
    found = _read(_open())
    event = found["events"][0]
    assert event["deadline_on"] is None
    assert found["missing"]["fields"]["evt-1"]["deadline_outcome"] == UNKNOWN


@pytest.mark.parametrize("outcome", ["支持", "反证", "条件风险"])
def test_a_recorded_deadline_result_stays_visible(outcome):
    found = _read(_open("2026-10-15", outcome))
    assert found["events"][0]["deadline_outcome"] == outcome
    assert found["events"][0]["deadline_on"] == "2026-10-15"
    assert "deadline_outcome" not in found["missing"]["fields"].get("evt-1", {})


def test_a_later_cutoff_marks_a_deadline_that_has_since_arrived():
    found = _read(_open("2026-10-16", seen=SEEN), ended=OPEN, clock=OPEN, cutoff=CUTOFF)
    assert found["events"][0]["deadline_on"] == "2026-10-16"
    assert found["missing"]["fields"]["evt-1"]["deadline_outcome"] == ARRIVED.format(day="2026-10-16")


def test_a_deadline_seen_after_cutoff_is_unknown():
    cell = {"value": "假设中", "at": BEFORE.isoformat(), "missing_reason": None}
    pages = Memory([])
    pages.snapshots.append(
        {
            "snapshot_id": 1,
            "trade_date": DAY,
            "snapshot_generated_at": BEFORE,
            "source_asof": BEFORE,
            "status": "complete",
            "kind": "stage_completion",
            "jobs": [],
            "events": [
                {
                    "event_id": "evt-1",
                    "anomaly_id": "anom-1",
                    "observed_at": BEFORE.isoformat(),
                    "evidence_ids": [],
                    "fields": {
                        "lifecycle": cell,
                        "deadline_outcome": {"value": None, "at": None, "missing_reason": None},
                        "deadline_on": {"value": "2026-11-06", "at": AFTER.isoformat(), "missing_reason": None},
                    },
                }
            ],
            "missing": {"stages": [], "events": [], "fields": {}},
        }
    )
    found = read_snapshot(pages, DAY, CUTOFF)
    assert found["events"][0]["deadline_on"] is None
    assert found["events"][0]["deadline_outcome"] is None
    gaps = found["missing"]["fields"]["evt-1"]
    assert gaps["deadline_on"] == "来源时间晚于 cutoff"
    assert gaps["deadline_outcome"] == UNKNOWN


def _replay_bundle(name, deadline_on, outcome=None):
    report = {"mechanism": "供给", "deadline_on": deadline_on}
    linkage = {"event_id": f"evt-{name}", "lifecycle": "假设中", "mechanism": "供给"}
    if outcome is not None:
        report["deadline_outcome"] = outcome
        linkage["deadline_outcome"] = outcome
    return {
        "anomaly_id": name,
        "report": report,
        "linkage": linkage,
        "candidates": [],
        "claims": [{"direction": "不利"}],
    }


def test_replay_snapshot_uses_the_same_four_deadline_cases():
    cases = (
        ("future", "2026-11-06", None, None),
        ("arrived", "2026-10-15", None, ARRIVED.format(day="2026-10-15")),
        ("unknown", None, None, UNKNOWN),
        ("kept", "2026-10-15", "支持", None),
    )
    events = []
    missing_fields = {}
    for name, deadline_on, outcome, reason in cases:
        bundle = _replay_bundle(name, deadline_on, outcome)
        event, gaps = _event(bundle, BEFORE)
        assert event["fields"]["deadline_on"]["value"] == deadline_on
        if reason is None:
            assert "deadline_outcome" not in gaps
        else:
            assert gaps["deadline_outcome"] == reason
        events.append(event)
        if gaps:
            missing_fields[event["event_id"]] = gaps
    pages = Memory([])
    append_replay_snapshot(
        pages,
        DAY,
        _clock(CUTOFF),
        source_asof=BEFORE,
        events=events,
        stages={name: BEFORE for name in ("attribution_candidates", "attribution_tracks", "attribution_labels")},
        missing={"stages": [], "events": [], "fields": missing_fields},
    )
    found = read_replay_snapshot(pages, DAY)
    assert found["replay"] is True
    by_id = {event["event_id"]: event for event in found["events"]}
    assert by_id["evt-future"]["deadline_on"] == "2026-11-06"
    assert by_id["evt-future"]["deadline_outcome"] is None
    assert "deadline_outcome" not in found["missing"]["fields"].get("evt-future", {})
    assert found["missing"]["fields"]["evt-arrived"]["deadline_outcome"] == ARRIVED.format(day="2026-10-15")
    assert found["missing"]["fields"]["evt-unknown"]["deadline_outcome"] == UNKNOWN
    assert by_id["evt-kept"]["deadline_outcome"] == "支持"
    assert "deadline_outcome" not in found["missing"]["fields"].get("evt-kept", {})
