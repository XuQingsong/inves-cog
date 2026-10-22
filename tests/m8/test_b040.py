"""B-040: pool events, no second model call, and a measured replay count."""

from datetime import timedelta

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.chain import run_scheduled
from inves_cog.perception.attribution.replay_window import Counting, replay_window, slot_moment
from tests.m8.test_b039_run import DAY, REAL, STARTED, Pages, _anomaly, _news

pytestmark = pytest.mark.phase1_blocking


def _pool(anomaly_id, ticker):
    row = _anomaly()
    row["anomaly_id"] = anomaly_id
    row["members"] = [{"ticker": ticker}]
    row["relations"] = [{"ticker": ticker, "exposure": "直接", "status": "观察到"}]
    return row


def _wide(anomaly_id):
    return {
        "anomaly_id": anomaly_id,
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "wide",
        "members": [{"ticker": "ZZZZ"}],
        "started_at": STARTED,
        "generated_at": STARTED,
    }


def _seen(info_id, ticker):
    return _news(info_id, STARTED - timedelta(hours=2), STARTED - timedelta(hours=1)) | {"tickers": [ticker]}


def _mix():
    return (
        [
            _pool("nvda-close", "NVDA"),
            _pool("mu-quiet", "MU"),
            _wide("wide-heard"),
            _wide("wide-quiet"),
        ],
        [_seen("nvda-news", "NVDA"), _seen("wide-news", "ZZZZ")],
    )


def test_pool_pre_move_news_persists_the_structured_event_and_snapshot(tmp_path):
    from inves_cog.perception.attribution.replay_window import MemoryStore

    anomalies, items = _mix()
    store = MemoryStore()
    client = Counting()
    moment = slot_moment(DAY, "attribution_candidates")
    rows = run_scheduled(moment, anomalies=anomalies, items=items, client=client, store=store)
    saved = {row["anomaly_id"]: row for row in rows["rows"]}
    assert saved["nvda-close"]["saved"] is True
    assert saved["nvda-close"]["move_card"]["问法"]
    bundle = store.bundles["nvda-close"]
    assert bundle["linkage"]["lifecycle"] not in {None, "已发现"}
    assert bundle["linkage"]["mechanism"] == "供给"
    assert bundle["claims"]
    assert bundle["tracks"]
    assert bundle["report"]
    assert any(row.get("scored") and row.get("mechanism") == "供给" for row in bundle["candidates"])
    assert any(row.get("ticker") == "NVDA" and row.get("exposure") == "直接" for row in bundle["report"]["scope"])
    assert bundle["candidates"][0]["affected"][0]["exposure"] == "直接"
    # N1/N2/N6 stay the only ticker_status codes. A scored supply hypothesis has none.
    assert bundle["report"]["ticker_status"] == []

    pages = Pages()
    played = replay_window(
        pages,
        FrozenClock(REAL),
        anomalies=anomalies,
        items=items,
        days=(DAY,),
        client=Counting(),
        log_path=tmp_path / "run.json",
    )
    assert played["days"][0]["snapshot_id"] == 1
    event = next(row for row in pages.snapshots[0]["events"] if row["anomaly_id"] == "nvda-close")
    assert event["fields"]["lifecycle"]["value"] not in {None, "已发现"}
    assert event["fields"]["mechanism"]["value"] == "供给"
    assert event["fields"]["exposure"]["value"] == "直接"
    assert event["members"][0]["ticker"] == "NVDA"
    assert event["members"][0]["exposure"] == "直接"


def test_tracks_with_pre_move_news_does_not_call_or_overwrite():
    from inves_cog.perception.attribution.replay_window import MemoryStore

    anomaly = _pool("nvda-close", "NVDA")
    seen = _seen("nvda-news", "NVDA")
    store = MemoryStore()
    morning = Counting()
    run_scheduled(
        slot_moment(DAY, "attribution_candidates"),
        anomalies=[anomaly],
        items=[seen],
        client=morning,
        store=store,
    )
    kept = store.bundles["nvda-close"]
    assert kept["linkage"]["mechanism"] == "供给"
    card = kept["report"]["move_card"]
    before = [
        {
            "mechanism": row.get("mechanism"),
            "info_ids": list(row.get("info_ids") or []),
            "score": row.get("score"),
            "exposure": [item.get("exposure") for item in row.get("affected") or []],
        }
        for row in kept["report"]["candidates"]
    ]
    later = Counting()
    followed = run_scheduled(
        slot_moment(DAY, "attribution_tracks"),
        anomalies=[anomaly],
        items=[seen],
        client=later,
        store=store,
    )
    assert later.tasks == []
    assert followed["rows"][0]["saved"] is True
    current = store.bundles["nvda-close"]
    assert current["linkage"]["mechanism"] == "供给"
    assert current["report"]["move_card"] == card
    after = [
        {
            "mechanism": row.get("mechanism"),
            "info_ids": list(row.get("info_ids") or []),
            "score": row.get("score"),
            "exposure": [item.get("exposure") for item in row.get("affected") or []],
        }
        for row in current["report"]["candidates"]
    ]
    assert after == before
    labels = Counting()
    run_scheduled(
        slot_moment(DAY, "attribution_labels"),
        anomalies=[anomaly],
        items=[seen],
        client=labels,
        store=store,
    )
    assert labels.tasks == []


def test_dry_run_counts_match_the_measured_stages():
    anomalies, items = _mix()
    dry = replay_window(Pages(), FrozenClock(REAL), anomalies=anomalies, items=items, days=(DAY,), dry_run=True)
    measured = replay_window(
        Pages(),
        FrozenClock(REAL),
        anomalies=anomalies,
        items=items,
        days=(DAY,),
        client=Counting(),
    )
    dry_calls = [stage["calls"] for stage in dry["days"][0]["stages"]]
    measured_calls = [stage["calls"] for stage in measured["days"][0]["stages"]]
    assert dry_calls == measured_calls
    assert dry_calls[1] == {}
    assert dry_calls[2] == {}
    assert measured["calls"]
    assert "move_card" in dry_calls[0]
    assert dry["calls"] == []
    assert measured["days"][0]["snapshot_id"] == 1
