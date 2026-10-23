"""B-041: the contract fixture after the exposure ruling.

V1 compares evt-toshiba and evt-expired with the revised contract.
A price member with no relation stays 纯共振 and is not a missing exposure.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.chain import run_scheduled
from inves_cog.perception.attribution.replay_window import (
    DAYS,
    Counting,
    MemoryStore,
    replay_window,
    slot_moment,
)
from inves_cog.perception.attribution.snapshot import m8_provider, read_replay_snapshot, read_snapshot
from tests.m8.test_b036 import Memory
from tests.m8.test_b039_run import Pages

pytestmark = pytest.mark.phase1_blocking

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/phase1/contracts/m8-m9-provider.json"
DAY = "2026-10-20"
TOSHIBA_START = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)
AMD_START = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)
REAL = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)
ARRIVED = "截止日已到（2026-10-19）但没有支持/反证/条件风险结果"
STAGES = ("attribution_candidates", "attribution_tracks", "attribution_labels")


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _keys(value):
    if isinstance(value, dict):
        return {key: _keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_keys(value[0])] if value else []
    return type(value)


class Fixture(Counting):
    """Count calls and keep each payload. The reply is local and is not a model."""

    def __init__(self):
        super().__init__()
        self.payloads = []

    def call(self, task, payload):
        self.payloads.append((task, payload))
        if task != "anomaly_candidates":
            return super().call(task, payload)
        self.tasks.append(task)
        return {"candidates": [_candidate(payload)]}


def _candidate(payload):
    anomaly = payload.get("anomaly") if isinstance(payload, dict) else {}
    anomaly = anomaly if isinstance(anomaly, dict) else {}
    names = []
    for member in anomaly.get("members") or []:
        name = member.get("ticker") if isinstance(member, dict) else member
        if isinstance(name, str) and name:
            names.append(name)
    info_ids = [
        row.get("info_id") for row in (payload.get("items") or []) if isinstance(row, dict) and row.get("info_id")
    ]
    return {
        "mechanism": "供给",
        "info_ids": info_ids[:1],
        "affected": [{"ticker": name, "direction": "down"} for name in names],
        "chain": [{"entity_id": name} for name in names],
        "control_baskets": [],
        "links": [_link(name) for name in names],
        "竞争解释": [],
        "反证条件": "下一季收入没有下降",
        "证伪预测": [_prediction(name) for name in names],
    }


def _link(name):
    return {
        "kind": "声明的假设",
        "from": "新闻",
        "to": name,
        "hypothesis": f"供应变化影响{name}",
        "hypothesis_type": "暴露关系",
        "falsify": {"metric": "收入", "direction": "下降", "window": "下一季"},
    }


def _prediction(name):
    return {"ticker": name, "control_basket": "存储", "direction": "down", "window": "下一季"}


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


def _pool(anomaly_id, members, relations, started, deadline):
    row = {
        "anomaly_id": anomaly_id,
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "pool",
        "members": [{"ticker": name} for name in members],
        "relations": relations,
        "started_at": started,
        "generated_at": started,
    }
    if deadline is not None:
        row["deadline_on"] = deadline
    return row


def _wide():
    return {
        "anomaly_id": "wide",
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "wide",
        "members": [{"ticker": "ZZZZ"}],
        "started_at": TOSHIBA_START,
        "generated_at": TOSHIBA_START,
    }


def _fixture():
    labels = slot_moment(DAY, "attribution_labels")
    anomalies = [
        _pool(
            "toshiba",
            ["WDC", "STX", "MU"],
            [
                {"ticker": "WDC", "exposure": "直接", "status": "观察到"},
                {"ticker": "STX", "exposure": "直接", "status": "观察到"},
                {"ticker": "MU", "exposure": "概念关联", "status": "候选"},
            ],
            TOSHIBA_START,
            "2026-11-06",
        ),
        _pool("nvda", ["NVDA"], [], TOSHIBA_START, None),
        _pool(
            "expired",
            ["AMD"],
            [{"ticker": "AMD", "exposure": "直接", "status": "观察到"}],
            AMD_START,
            "2026-10-19",
        ),
        _wide(),
    ]
    items = [
        _news("info-toshiba-1", "WDC", TOSHIBA_START - timedelta(hours=2), TOSHIBA_START - timedelta(hours=1)),
        _news("info-nvda-1", "NVDA", TOSHIBA_START - timedelta(hours=2), TOSHIBA_START - timedelta(hours=1)),
        _news("info-expired-1", "AMD", AMD_START - timedelta(hours=2), AMD_START - timedelta(hours=1)),
        _news("late-after-open", "WDC", TOSHIBA_START - timedelta(hours=5), labels + timedelta(minutes=5)),
        _news("late-published-early", "NVDA", TOSHIBA_START - timedelta(days=2), labels + timedelta(hours=1)),
    ]
    return anomalies, items


def _run(store, client):
    anomalies, items = _fixture()
    stages = []
    for name in STAGES:
        moment = slot_moment(DAY, name)
        before = len(client.tasks)
        run_scheduled(moment, anomalies=anomalies, items=items, client=client, store=store)
        stages.append((name, list(client.tasks[before:])))
    return stages


def _exposures(event):
    return [(row["ticker"], row["exposure"]) for row in event["affected"]]


def _assert_contract_events(found, linkage):
    contract = _contract()
    sample = {row["event_id"]: row for row in contract["output"]["events"]}
    body = {key: value for key, value in found.items() if key != "replay"}
    assert set(body) == set(contract["output"])
    assert set(body["source_ids"]) == set(contract["output"]["source_ids"])
    assert set(body["missing"]) == set(contract["output"]["missing"])
    by_id = {row["event_id"]: row for row in found["events"]}
    assert "evt-wide" not in by_id
    toshiba = by_id["evt-toshiba"]
    expired = by_id["evt-expired"]
    assert set(toshiba) == set(sample["evt-toshiba"])
    assert set(expired) == set(sample["evt-expired"])
    assert set(toshiba["affected"][0]) == set(sample["evt-toshiba"]["affected"][0])
    assert toshiba["mechanism"] == sample["evt-toshiba"]["mechanism"] == "供给"
    assert toshiba["direction"] == sample["evt-toshiba"]["direction"] == "down"
    assert toshiba["deadline_on"] == sample["evt-toshiba"]["deadline_on"] == "2026-11-06"
    assert toshiba["lifecycle"] == linkage["toshiba"]
    assert toshiba["lifecycle"]
    assert _exposures(toshiba) == [("WDC", "直接"), ("STX", "直接"), ("MU", "概念关联")]
    assert all(isinstance(row["ticker"], str) for row in toshiba["affected"])
    assert "deadline_outcome" not in found["missing"]["fields"].get("evt-toshiba", {})
    assert expired["direction"] == "down"
    assert expired["deadline_on"] == "2026-10-19"
    assert _exposures(expired) == [("AMD", "直接")]
    assert found["missing"]["fields"]["evt-expired"]["deadline_outcome"] == ARRIVED
    nvda = by_id["evt-nvda"]
    assert _exposures(nvda) == [("NVDA", "纯共振")]
    assert "NVDA.exposure" not in found["missing"]["fields"].get("evt-nvda", {})
    assert "exposure" not in found["missing"]["fields"].get("evt-nvda", {})
    assert found["complete"] is True


def test_v1_replay_matches_the_named_contract_fields():
    store = MemoryStore()
    _run(store, Fixture())
    pages = Pages()
    replay_window(pages, FrozenClock(REAL), anomalies=_fixture()[0], items=_fixture()[1], days=(DAY,), client=Fixture())
    found = read_replay_snapshot(pages, DAY)
    assert found["replay"] is True
    linkage = {key: (store.bundles[key].get("linkage") or {}).get("lifecycle") for key in ("toshiba", "expired")}
    _assert_contract_events(found, linkage)


def test_v2_and_v3_counts_match_and_later_slots_are_quiet():
    anomalies, items = _fixture()
    measured = Fixture()
    stages = _run(MemoryStore(), measured)
    assert stages[0][1] == ["move_card", "claim_extraction", "anomaly_candidates"] * 3
    assert stages[1][1] == []
    assert stages[2][1] == []
    asked = json.dumps(measured.payloads, default=str)
    assert "wide" not in asked
    assert "late-after-open" not in asked
    assert "late-published-early" not in asked
    dry_pages = Pages()

    class Boom:
        def call(self, task, payload):
            raise AssertionError(task)

    dry = replay_window(
        dry_pages,
        FrozenClock(REAL),
        anomalies=anomalies,
        items=items,
        days=(DAY,),
        client=Boom(),
        dry_run=True,
    )
    live = replay_window(Pages(), FrozenClock(REAL), anomalies=anomalies, items=items, days=(DAY,), client=Fixture())
    assert [stage["calls"] for stage in dry["days"][0]["stages"]] == [
        stage["calls"] for stage in live["days"][0]["stages"]
    ]
    assert dry["days"][0]["stages"][1]["calls"] == {}
    assert dry["days"][0]["stages"][2]["calls"] == {}
    assert dry["calls"] == []
    assert dry_pages.snapshots == []
    assert not any(statement.startswith("INSERT") for statement, _params in dry_pages.calls)


def test_v4_tracks_keep_the_morning_page():
    store = MemoryStore()
    client = Fixture()
    anomalies, items = _fixture()
    run_scheduled(
        slot_moment(DAY, "attribution_candidates"),
        anomalies=anomalies,
        items=items,
        client=client,
        store=store,
    )
    morning = store.bundles["toshiba"]["report"]
    card = morning["move_card"]
    text = morning["daily_text"]
    run_scheduled(
        slot_moment(DAY, "attribution_tracks"),
        anomalies=anomalies,
        items=items,
        client=Fixture(),
        store=store,
    )
    current = store.bundles["toshiba"]["report"]
    assert current["move_card"] == card
    assert current["daily_text"] == text


def test_v5_late_news_never_enters_a_stage_payload():
    client = Fixture()
    _run(MemoryStore(), client)
    asked = json.dumps(client.payloads, default=str)
    assert "late-after-open" not in asked
    assert "late-published-early" not in asked
    assert "info-toshiba-1" in asked


def test_v6_missing_stage_matches_the_incomplete_contract_and_a_field_gap_stays_complete():
    contract = _contract()
    found = read_snapshot(Memory([]), DAY, contract["cutoff"])
    expected = contract["incomplete_case"]["output"]
    assert _keys(found) == _keys(expected)
    assert found["complete"] is False
    assert found["source_events_asof"] is None
    assert found["events"] == []
    assert found["missing"]["stages"] == expected["missing"]["stages"]
    pages = Pages()
    replay_window(pages, FrozenClock(REAL), anomalies=_fixture()[0], items=_fixture()[1], days=(DAY,), client=Fixture())
    played = read_replay_snapshot(pages, DAY)
    assert played["complete"] is True
    assert played["missing"]["fields"]["evt-expired"]["deadline_outcome"] == ARRIVED


def test_v8_five_day_replay_does_not_write_live_tables(tmp_path):
    anomalies, items = _fixture()
    pages = Pages()
    played = replay_window(
        pages,
        FrozenClock(REAL),
        anomalies=anomalies,
        items=items,
        days=DAYS,
        client=Fixture(),
        log_path=tmp_path / "run.json",
    )
    forbidden = ("linkage_events", "ticker_status", "candidates", "tracks", "claims", "reports", "market_day")
    assert not any(name in statement for statement, _params in pages.calls for name in forbidden)
    assert all(row["kind"] == "historical_backfill" for row in pages.snapshots)
    assert all(row["snapshot_generated_at"] == REAL for row in pages.snapshots)
    calls = [stage["calls"] for day in played["days"] for stage in day["stages"] if stage["calls"]]
    assert calls == [{"move_card": 3, "claim_extraction": 3, "anomaly_candidates": 3}]
    found = read_replay_snapshot(pages, DAY)
    assert found["replay"] is True
    assert _keys(found)["complete"] == _keys(_contract()["output"])["complete"]
    assert set(found) >= set(_contract()["output"]) | {"replay"}
    historical = slot_moment(DAY, "attribution_labels")
    live = read_snapshot(pages, DAY, historical)
    assert live["complete"] is False
    assert live["events"] == []


def _db_anomaly(anomaly):
    return {
        "anomaly_id": anomaly["anomaly_id"],
        "trade_date": anomaly["trade_date"],
        "session": anomaly["session"],
        "entry_paths": ["B"],
        "layer": "L4",
        "severity": "watch",
        "baskets": [],
        "members": anomaly["members"],
        "direction": anomaly["direction"],
        "max_abs_z": 1.0,
        "data_quality": {},
        "coverage": {},
        "amplification": {},
        "type_candidates_prelim": [],
        "status": "已发现·原因未明",
        "universe": anomaly["universe"],
        "params_version": "b041",
    }


def _clear(connection, anomaly_ids):
    event_ids = [f"evt-{anomaly_id}" for anomaly_id in anomaly_ids]
    connection.execute("DELETE FROM perception.tracks WHERE event_id = ANY(%s)", (event_ids,))
    connection.execute("DELETE FROM perception.linkage_events WHERE anomaly_id = ANY(%s)", (anomaly_ids,))
    connection.execute("DELETE FROM perception.candidates WHERE anomaly_id = ANY(%s)", (anomaly_ids,))
    connection.execute("DELETE FROM perception.retrievals WHERE anomaly_id = ANY(%s)", (anomaly_ids,))
    connection.execute("DELETE FROM perception.ticker_status WHERE anomaly_id = ANY(%s)", (anomaly_ids,))
    connection.execute("DELETE FROM perception.reports WHERE anomaly_id = ANY(%s)", (anomaly_ids,))
    connection.execute("DELETE FROM perception.anomalies WHERE anomaly_id = ANY(%s)", (anomaly_ids,))


def _page(connection, anomaly_id):
    row = connection.execute("SELECT report FROM perception.reports WHERE anomaly_id = %s", (anomaly_id,)).fetchone()
    report = row[0]
    if isinstance(report, str):
        report = json.loads(report)
    return report["daily_text"], report["move_card"]


def test_v1_live_provider_on_disposable_database():
    import psycopg

    from inves_cog.perception.anomaly.service import write_anomalies
    from inves_cog.perception.attribution.store import Store
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    anomalies, items = _fixture()
    future = _pool(
        "future",
        ["NVDA"],
        [{"ticker": "NVDA", "exposure": "直接", "status": "观察到"}],
        TOSHIBA_START,
        "2026-11-06",
    )
    labels = slot_moment(DAY, "attribution_labels")
    items = [
        *items,
        _news("info-future-1", "NVDA", TOSHIBA_START - timedelta(hours=2), TOSHIBA_START - timedelta(hours=1)),
    ]
    cutoff = _contract()["cutoff"]
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin") as connection:
        connection.execute("BEGIN")
        connection.execute("SET LOCAL ROLE inves_cog_admin")
        ids = [row["anomaly_id"] for row in anomalies] + [future["anomaly_id"]]
        _clear(connection, ids)
        write_anomalies(connection, [_db_anomaly(row) for row in anomalies], generated_at=TOSHIBA_START)
        write_anomalies(connection, [_db_anomaly(future)], generated_at=labels + timedelta(hours=2))
        connection.execute("SET LOCAL ROLE role_perception")
        store = Store(connection)
        client = Fixture()
        run_scheduled(
            slot_moment(DAY, "attribution_candidates"),
            anomalies=[*anomalies, future],
            items=items,
            client=client,
            store=store,
            connection=connection,
            clock=FrozenClock(slot_moment(DAY, "attribution_candidates")),
            trade_date=DAY,
            params_version="b041",
        )
        text, card = _page(connection, "toshiba")
        run_scheduled(
            slot_moment(DAY, "attribution_tracks"),
            anomalies=[*anomalies, future],
            items=items,
            client=client,
            store=store,
            connection=connection,
            clock=FrozenClock(slot_moment(DAY, "attribution_tracks")),
            trade_date=DAY,
            params_version="b041",
        )
        assert _page(connection, "toshiba") == (text, card)
        run_scheduled(
            labels,
            anomalies=[*anomalies, future],
            items=items,
            client=client,
            store=store,
            connection=connection,
            clock=FrozenClock(labels),
            trade_date=DAY,
            params_version="b041",
        )
        connection.commit()
        found = m8_provider(connection)(DAY, cutoff)
    assert "evt-future" not in {row["event_id"] for row in found["events"]}
    assert found["events"]
    asked = json.dumps(client.payloads, default=str)
    assert "late-after-open" not in asked
    assert "late-published-early" not in asked
    linkage = {"toshiba": "假设中", "expired": "假设中"}
    _assert_contract_events(found, linkage)
