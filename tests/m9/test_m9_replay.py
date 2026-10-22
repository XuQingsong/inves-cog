"""M9 consumes accepted M8 historical snapshots without publishing live overlays."""

import json
from datetime import date, datetime

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.snapshot import append_replay_snapshot
from tests.m8.test_b036 import Memory

pytestmark = pytest.mark.phase1_blocking
DAYS = [date(2026, 10, day) for day in (15, 16, 19, 20, 21)]
CLOCK = FrozenClock(datetime.fromisoformat("2026-10-22T14:00:00Z"))


def source():
    # The native M8 writer supplies the storage shape; no hand-built provider output.
    db = Memory([])
    for day in DAYS:
        at = CLOCK.now_utc()
        event = {
            "event_id": "synthetic-" + str(day),
            "anomaly_id": "synthetic-anomaly",
            "observed_at": at.isoformat(),
            "fields": {"lifecycle": {"value": "市场确认", "at": at.isoformat(), "missing_reason": None}},
            "members": [{"ticker": "NVDA", "exposure": "直接"}],
        }
        append_replay_snapshot(
            db,
            day,
            CLOCK,
            source_asof=at,
            stages={name: at for name in ("attribution_candidates", "attribution_tracks", "attribution_labels")},
            events=[] if day.day == 19 else [event],
            missing={
                "stages": [],
                "events": [],
                "fields": {} if day.day == 19 else {event["event_id"]: {"mechanism": "历史字段没有版本"}},
            },
        )
    return db


def test_five_day_m8_replay_is_explicit_and_never_publishes_live(tmp_path):
    from inves_cog.shadow.replay import replay_m8

    db = source()
    live, output = tmp_path / "live", tmp_path / "replay-run"
    live.mkdir()
    sentinel = live / "event_overlay_2026-10-22.json"
    sentinel.write_bytes(b"existing live output")
    db.statements.clear()
    result = replay_m8(db, days=DAYS, clock=CLOCK, output_directory=output, live_directory=live)
    assert result["replay"] is True and result["kind"] == "historical_backfill_not_natural"
    assert result["actual_generated_at"] == CLOCK.now_utc().isoformat()
    assert sentinel.read_bytes() == b"existing live output" and len(list(live.iterdir())) == 1
    assert not list(output.glob("event_overlay_*.json"))
    assert len(result["days"]) == 5
    for day in DAYS:
        row = json.loads((output / ("replay_overlay_" + str(day) + ".json")).read_text())
        assert row["replay"] is True and row["trade_date"] == str(day)
        assert row["actual_generated_at"] == row["overlay"]["generated_at"] == CLOCK.now_utc().isoformat()
        if day.day == 19:
            assert row["overlay"]["tickers"] == {} and row["empty_reason"]
        else:
            assert row["overlay"]["tickers"]["NVDA"]["cooling_status"] == "unknown"
            assert row["overlay"]["tickers"]["NVDA"]["cooling_off"] is False
    assert all(not sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql in db.statements)
    assert "READ ONLY" in db.statements[0] and db.statements[-1] == "ROLLBACK"


@pytest.mark.parametrize("relative", ["live", "live/replay", "."])
def test_m8_replay_rejects_paths_overlapping_live_before_reading(tmp_path, relative):
    from inves_cog.shadow.replay import replay_m8

    db = Memory([])
    with pytest.raises(ValueError, match="separate"):
        replay_m8(db, days=DAYS, clock=CLOCK, output_directory=tmp_path / relative, live_directory=tmp_path / "live")
    assert db.statements == []


def test_m8_replay_missing_snapshot_is_unavailable_not_an_empty_success(tmp_path):
    from inves_cog.shadow.replay import replay_m8

    result = replay_m8(
        Memory([]), days=DAYS[:1], clock=CLOCK, output_directory=tmp_path / "replay", live_directory=tmp_path / "live"
    )
    row = json.loads((tmp_path / "replay/replay_overlay_2026-10-15.json").read_text())
    assert result["days"][0]["status"] == row["status"] == "unavailable"
    assert row["overlay"] is None and row["missing"]["stages"]
