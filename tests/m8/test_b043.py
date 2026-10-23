"""B-043: replay selects anomalies by trade date, including a later backfill."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import regular_bounds
from inves_cog.perception.anomaly.service import write_anomalies
from inves_cog.perception.attribution.morning import _load
from inves_cog.perception.attribution.morning import main as morning_main
from inves_cog.perception.attribution.replay_window import DAYS, Counting, replay_window, slot_moment
from inves_cog.perception.attribution.replay_window import main as replay_main
from inves_cog.perception.attribution.scheduled import main as stage_main
from inves_cog.perception.attribution.snapshot import read_replay_snapshot
from tests.m8.test_b039_run import Pages
from tests.m8.test_b041_contract import _clear, _db_anomaly
from tests.m8.test_b042 import _close, _insert_news, _open, _Trace

pytestmark = pytest.mark.phase1_blocking

BACKFILL = datetime(2026, 10, 22, 3, 49, tzinfo=timezone.utc)
ON_TIME = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
LATE_SEEN = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
OTHER_SEEN = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)
REAL = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)
POOLS = {"2026-10-15": 2, "2026-10-16": 5, "2026-10-19": 0, "2026-10-20": 1, "2026-10-21": 1}
WIDES = {"2026-10-15": 0, "2026-10-16": 0, "2026-10-19": 0, "2026-10-20": 10, "2026-10-21": 8}
LATE_DAYS = {"2026-10-15", "2026-10-16", "2026-10-20"}
_LIVE = ("linkage_events", "ticker_status", "candidates", "tracks", "claims", "reports", "market_day")


class _Record:
    def __init__(self):
        self.inner = Counting()
        self.tasks = []
        self.payloads = []

    def call(self, task, payload):
        self.tasks.append(task)
        self.payloads.append(payload)
        return self.inner.call(task, payload)


class _Boom:
    def call(self, task, payload):
        raise AssertionError(task)


def _session_open(day):
    bounds = regular_bounds(date.fromisoformat(day))
    assert bounds is not None and bounds[0].tzinfo is not None
    return bounds[0]


def _anomaly(anomaly_id, day, universe, ticker, generated):
    return {
        "anomaly_id": anomaly_id,
        "trade_date": day,
        "session": "close",
        "direction": "down",
        "universe": universe,
        "members": [{"ticker": ticker}],
        "generated_at": generated,
    }


def _news(info_id, ticker, published, seen):
    return {
        "info_id": info_id,
        "kind": "news",
        "published_at": published,
        "first_seen_at": seen,
        "headline": info_id,
        "flags": [],
        "tickers": [ticker],
        "entities": [],
        "extraction_source": {"news_card": {"说了什么": info_id, "名单内": [], "钟点清楚": True}},
    }


def _fixture():
    anomalies = []
    items = []
    for day in DAYS:
        generated = ON_TIME if day == "2026-10-21" else BACKFILL
        opened = _session_open(day)
        published = opened - timedelta(minutes=30)
        for index in range(POOLS[day]):
            ticker = f"P{day[5:].replace('-', '')}{index}"
            anomaly_id = f"b043-{day[5:]}-p{index}"
            anomalies.append(_anomaly(anomaly_id, day, "pool", ticker, generated))
            items.append(_news(f"pre-{day}-{index}", ticker, published, published))
            items.append(_news(f"late-{day}-{index}", ticker, published, LATE_SEEN))
        for index in range(WIDES[day]):
            ticker = f"W{day[5:].replace('-', '')}{index}"
            anomalies.append(_anomaly(f"b043-{day[5:]}-w{index}", day, "wide", ticker, generated))
    items.append(_news("other-day", "P10150", OTHER_SEEN, OTHER_SEEN))
    return anomalies, items


def _calls(pools):
    if not pools:
        return {}
    return {"move_card": pools, "claim_extraction": pools, "anomaly_candidates": pools}


def _ids_for(anomalies, day):
    return [row["anomaly_id"] for row in anomalies if row["trade_date"] == day]


def _dump(payloads):
    return json.dumps(payloads, ensure_ascii=False, default=str)


def _stamp(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _assert_window(played, logged, payloads):
    offset = 0
    anomalies, _items = _fixture()
    for day, found, logged_day in zip(DAYS, played, logged, strict=True):
        pools = POOLS[day]
        assert [stage["anomalies"] for stage in found["stages"]] == [pools + WIDES[day]] * 3
        assert [stage["calls"] for stage in found["stages"]] == [_calls(pools), {}, {}]
        expected = set(_ids_for(anomalies, day)) if day in LATE_DAYS else set()
        assert {row["anomaly_id"] for row in found["generated_after_slot"]} == expected
        assert json.dumps(found["generated_after_slot"], default=_stamp) == json.dumps(
            logged_day["generated_after_slot"]
        )
        for row in found["generated_after_slot"]:
            assert row["generated_after_slot"] is True
            assert row["generated_at"] in {BACKFILL, BACKFILL.isoformat()}
        width = pools * 3
        asked = _dump(payloads[offset : offset + width])
        offset += width
        _assert_payload(asked, anomalies, day)
    assert offset == len(payloads)


def _assert_payload(asked, anomalies, day):
    for other in DAYS:
        if other == day:
            continue
        for anomaly_id in _ids_for(anomalies, other):
            assert anomaly_id not in asked
    for index in range(POOLS[day]):
        assert f"pre-{day}-{index}" in asked
        assert f"late-{day}-{index}" not in asked
    assert "other-day" not in asked
    assert "late-" not in asked


def test_backfilled_window_keeps_trade_date_and_news_time(tmp_path):
    anomalies, items = _fixture()
    dry = replay_window(None, FrozenClock(REAL), anomalies=anomalies, items=items, days=DAYS, dry_run=True)
    client = _Record()
    played = replay_window(
        Pages(),
        FrozenClock(REAL),
        anomalies=anomalies,
        items=items,
        days=DAYS,
        client=client,
        log_path=tmp_path / "replay.json",
    )
    assert [stage["calls"] for day in dry["days"] for stage in day["stages"]] == [
        stage["calls"] for day in played["days"] for stage in day["stages"]
    ]
    logged = json.loads((tmp_path / "replay.json").read_text(encoding="utf-8"))
    _assert_window(played["days"], logged["days"], client.payloads)
    assert not list(Path("migrations").glob("*b043*"))


def _seed(admin, anomalies, items):
    ids = [row["anomaly_id"] for row in anomalies]
    _clear(admin, ids)
    for day in DAYS:
        admin.execute("DELETE FROM perception.market_day WHERE trade_date = %s", (day,))
    for generated in (BACKFILL, ON_TIME):
        batch = [row for row in anomalies if row["generated_at"] == generated]
        write_anomalies(admin, [_db_anomaly(row) for row in batch], generated_at=generated)
    for item in items:
        _insert_news(admin, item)


def _cleanup(admin, anomalies, items):
    _clear(admin, [row["anomaly_id"] for row in anomalies])
    for day in DAYS:
        admin.execute("DELETE FROM perception.market_day WHERE trade_date = %s", (day,))
    info_ids = [item["info_id"] for item in items]
    admin.execute("DELETE FROM ingest.info_items WHERE info_id = ANY(%s)", (info_ids,))
    admin.execute(
        "DELETE FROM ingest.job_runs WHERE trade_date = ANY(%s) AND params_version = 'p-2026.10'",
        (list(DAYS),),
    )


def _run_live(connection, perception, client, folder):
    os.environ["INVES_COG_PAGE_DIR"] = str(folder)
    morning = slot_moment("2026-10-15", "attribution_candidates")
    try:
        morning_result = morning_main(
            [],
            connection=connection,
            perception=perception,
            clock=FrozenClock(morning),
            client=client,
            record_clock=FrozenClock(morning),
        )
        assert morning_result == 0
        for name in ("attribution_tracks", "attribution_labels"):
            moment = slot_moment("2026-10-15", name)
            assert (
                stage_main(
                    ["--task", name],
                    connection=connection,
                    perception=perception,
                    clock=FrozenClock(moment),
                    client=client,
                    record_clock=FrozenClock(moment),
                )
                == 0
            )
    finally:
        os.environ.pop("INVES_COG_PAGE_DIR", None)


def test_replay_cli_selects_backfilled_anomalies_on_disposable_database(tmp_path, capsys):
    _host, ingest, perception, admin = _open()
    anomalies, items = _fixture()
    try:
        _seed(admin, anomalies, items)
        traced = _Trace(ingest)
        assert (
            replay_main(
                ["--dry-run", "--days", ",".join(DAYS)],
                connection=traced,
                perception=perception,
                clock=FrozenClock(REAL),
                client=_Boom(),
            )
            == 0
        )
        printed = json.loads(capsys.readouterr().out)
        expected = replay_window(None, FrozenClock(REAL), anomalies=anomalies, items=items, days=DAYS, dry_run=True)
        assert [stage["calls"] for day in printed["days"] for stage in day["stages"]] == [
            stage["calls"] for day in expected["days"] for stage in day["stages"]
        ]
        assert [stage["anomalies"] for day in printed["days"] for stage in day["stages"]] == [
            POOLS[day] + WIDES[day] for day in DAYS for _stage in range(3)
        ]
        assert printed["calls"] == []
        assert not any(item.upper().startswith("INSERT") for item in traced.statements)
        _assert_cli_marks(printed, anomalies, admin)
        writer = _Trace(perception)
        recorded = _Record()
        assert (
            replay_main(
                ["--execute", "--days", ",".join(DAYS)],
                connection=traced,
                perception=writer,
                clock=FrozenClock(REAL),
                client=recorded,
            )
            == 0
        )
        executed = json.loads(capsys.readouterr().out)
        text = " ".join(writer.statements)
        for name in _LIVE:
            assert name not in text
        _assert_window(executed["days"], executed["days"], recorded.payloads)
        for day in DAYS:
            snapshot_id = executed["days"][DAYS.index(day)]["snapshot_id"]
            row = admin.execute(
                "SELECT kind, snapshot_generated_at FROM perception.m9_input_snapshots WHERE snapshot_id = %s",
                (snapshot_id,),
            ).fetchone()
            assert row["kind"] == "historical_backfill"
            assert read_replay_snapshot(perception, day)["replay"] is True
        _assert_cli_marks(executed, anomalies, admin)
        live = _Record()
        loaded = _load(ingest, slot_moment("2026-10-15", "attribution_candidates"), "2026-10-15")
        assert loaded["anomalies"] == []
        _run_live(ingest, perception, live, tmp_path)
        assert live.tasks == []
    finally:
        _cleanup(admin, anomalies, items)
        _close(ingest, perception, admin)


def _assert_cli_marks(printed, anomalies, admin):
    stored = {
        row["anomaly_id"]: row["generated_at"]
        for row in admin.execute(
            "SELECT anomaly_id, generated_at FROM perception.anomalies WHERE anomaly_id = ANY(%s)",
            ([row["anomaly_id"] for row in anomalies],),
        ).fetchall()
    }
    for anomaly in anomalies:
        assert stored[anomaly["anomaly_id"]] == anomaly["generated_at"]
    for day, found in zip(DAYS, printed["days"], strict=True):
        listed = {row["anomaly_id"] for row in found["generated_after_slot"]}
        assert listed == (set(_ids_for(anomalies, day)) if day in LATE_DAYS else set())
        for row in found["generated_after_slot"]:
            assert row["generated_after_slot"] is True
            assert datetime.fromisoformat(row["generated_at"]) == stored[row["anomaly_id"]] == BACKFILL
        body = json.dumps(found, ensure_ascii=False)
        for other in DAYS:
            if other == day:
                continue
            for anomaly_id in _ids_for(anomalies, other):
                assert anomaly_id not in body
