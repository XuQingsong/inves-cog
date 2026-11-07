from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.dataguard.recovery import ResourceState, attempt, eligible

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def gap(**kw):
    return dict(status="open", kind="missing", attempts=0, last_attempt_at=None, **kw)


def test_detect_only_resources_and_suspect_never_spawn():
    for detect, resource, kind in [
        (True, ResourceState(), "missing"),
        (False, ResourceState(memory_alarm=True), "missing"),
        (False, ResourceState(io_alarm=True), "missing"),
        (False, ResourceState(), "suspect"),
    ]:
        row = gap()
        row["kind"] = kind
        assert not eligible(row, NOW, detect_only=detect, resources=resource)


def test_increasing_retry_and_terminal_after_bounded_attempts():
    row = gap()
    row.update(attempts=2, last_attempt_at=NOW)
    assert not eligible(row, NOW + timedelta(minutes=19), detect_only=False, resources=ResourceState())
    assert eligible(row, NOW + timedelta(minutes=20), detect_only=False, resources=ResourceState())
    trace = []
    attempt(
        row,
        NOW + timedelta(minutes=20),
        max_attempts=3,
        run=lambda: trace.append("run") or True,
        downstream=lambda: trace.append("downstream") or True,
        recheck=lambda: False,
        persist=lambda r: trace.append(r["status"]),
    )
    assert row["status"] == "unrecoverable"
    assert trace == ["backfilling", "run", "downstream", "unrecoverable"]


def test_exit_zero_is_not_business_success_and_downstream_failure_is_not_resolution():
    for succeeded, downstream in [(True, False), (False, True)]:
        row = gap()
        attempt(
            row,
            NOW,
            max_attempts=3,
            run=lambda succeeded=succeeded: succeeded,
            downstream=lambda downstream=downstream: downstream,
            recheck=lambda: True,
            persist=lambda r: None,
        )
        assert row["status"] == "open"
    row = gap()
    attempt(
        row,
        NOW,
        max_attempts=3,
        run=lambda: True,
        downstream=lambda: True,
        recheck=lambda: True,
        persist=lambda r: None,
    )
    assert row["status"] == "resolved"
