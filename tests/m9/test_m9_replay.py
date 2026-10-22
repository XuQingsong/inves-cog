"""M9 consumes accepted M8 historical snapshots without publishing live overlays."""

import json
from datetime import date, datetime

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.snapshot import append_replay_snapshot
from tests.m8.test_b036 import Cursor, Memory

pytestmark = pytest.mark.phase1_blocking
DAYS = [date(2026, 10, day) for day in (15, 16, 19, 20, 21)]
CLOCK = FrozenClock(datetime.fromisoformat("2026-10-22T14:00:00Z"))


class ReplayDatabase(Memory):
    def execute(self, statement, params=None):
        if statement.startswith("SET statement_timeout="):
            self.statements.append(statement)
            return Cursor([])
        if "FROM perception.m9_input_snapshots" in statement:
            self.statements.append(" ".join(statement.split()))
            return Cursor([row for row in self.snapshots if str(row["trade_date"]) == str(params[0])])
        return super().execute(statement, params)


def source():
    # The native M8 writer supplies the storage shape; no hand-built provider output.
    db = ReplayDatabase([])
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


@pytest.mark.parametrize("days", [[DAYS[0], DAYS[0]], [date(2026, 10, 23)]])
def test_m8_replay_rejects_duplicate_or_future_dates_before_reading(tmp_path, days):
    from inves_cog.shadow.replay import replay_m8

    db = Memory([])
    with pytest.raises(ValueError, match="dates"):
        replay_m8(db, days=days, clock=CLOCK, output_directory=tmp_path / "replay", live_directory=tmp_path / "live")
    assert db.statements == [] and not (tmp_path / "replay").exists()


def test_m8_replay_keeps_an_existing_run_untouched(tmp_path):
    from inves_cog.shadow.replay import replay_m8

    output = tmp_path / "replay"
    output.mkdir()
    original = output / "replay-manifest.json"
    original.write_bytes(b"original evidence")
    db = Memory([])
    with pytest.raises(ValueError, match="already exists"):
        replay_m8(db, days=DAYS, clock=CLOCK, output_directory=output, live_directory=tmp_path / "live")
    assert original.read_bytes() == b"original evidence" and db.statements == []


def test_native_m8_replay_entry_uses_only_the_scoped_shadow_reader(monkeypatch, tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from inves_cog.shadow import cli

    db, keys = source(), []
    monkeypatch.setattr(cli, "read_environment", lambda: {"INVES_COG_OVERLAY_DIR": str(tmp_path / "live")})

    def scoped(values, key):
        keys.append(key)
        return nullcontext(db)

    monkeypatch.setattr(cli, "_scoped", scoped)
    result = cli._replay_m8(SimpleNamespace(trade_dates=DAYS, output_directory=tmp_path / "replay"), CLOCK)
    assert keys == ["INVES_COG_SHADOW_DATABASE_URL"]
    assert len(result["days"]) == 5 and result["replay"] is True
