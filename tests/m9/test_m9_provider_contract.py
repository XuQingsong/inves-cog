"""Consume the coordinator's actual synthetic JSON through the native M9 entry."""

import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.shadow.pipeline import MemoryOutputs, run_overlay
from tests.m9.test_m9_provider import Database

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def contract():
    return json.loads((ROOT / "docs/phase1/contracts/m8-m9-provider.json").read_text())


@pytest.fixture
def native(monkeypatch, tmp_path):
    from inves_cog.shadow import cli

    store, calls = MemoryOutputs(tmp_path), []

    class Operations:
        def __init__(self, _):
            pass

        def health_rows(self):
            return {}

        def write_health(self, _):
            pass

        def write_job(self, row):
            return 1

    monkeypatch.setattr(cli, "Operations", Operations)
    monkeypatch.setattr(cli, "DatabaseOutputs", lambda **_: store)
    monkeypatch.setattr(
        cli, "connect", lambda values: Database("operations" if values["INVES_COG_DATABASE_URL"] == "ops" else "data")
    )

    def invoke(sample, *, source=None, later=0):
        cutoff = datetime.fromisoformat(sample["cutoff"]) + timedelta(minutes=later)
        payload = deepcopy(sample["output"] if source is None else source)

        def provider(day, at):
            calls.append((str(day), at, deepcopy(payload)))
            return deepcopy(payload)

        result = cli.scheduled(
            clock=FrozenClock(cutoff),
            values={
                "INVES_COG_DATABASE_URL": "ops",
                "INVES_COG_SHADOW_DATABASE_URL": "shadow",
                "INVES_COG_OVERLAY_DATABASE_URL": "overlay",
                "INVES_COG_OVERLAY_DIR": str(tmp_path),
            },
            m8_provider=provider,
        )
        return result, store, calls

    return invoke


def assert_expected(payload, expected):
    for ticker, wanted in expected.items():
        item = payload["tickers"][ticker]
        assert item["cooling_off"] is wanted["cooling_off"]
        assert item["cooling_status"] == wanted["cooling_status"]
        assert item["first_lot_multiplier"] == 1.0 and item["stop_review_eligible"] is False
        assert not {"buy", "sell", "orders", "increase_qty"} & item.keys()
        if "m8_gaps_contains" in wanted:
            assert any(gap["field"] == wanted["m8_gaps_contains"] and gap["reason"] for gap in item["m8_gaps"])
            assert wanted["reason_contains"] in item["reason"]
            assert "该事件不触发冷静期" not in item["reason"]


def test_a1_a3_a4_actual_contract_via_native_provider(contract, native):
    before = deepcopy(contract)
    result, store, calls = native(contract)
    assert result["m9_overlay"]["status"] == "ok"
    assert len(store.overlays) == 1
    payload = store.overlays[0]
    assert_expected(payload, contract["expected_m9"])
    assert payload["m8_completeness"] == {
        "complete": contract["output"]["complete"],
        "source_events_asof": contract["output"]["source_events_asof"],
        "unknown_ticker_count": 2,
        "unknown_tickers": ["AMD", "NVDA"],
    }
    assert calls[0][0] == contract["target"] and calls[0][2] == contract["output"]
    assert contract == before


def test_a2_incomplete_contract_retains_previous_generated_at(contract, native):
    _, store, _ = native(contract)
    previous = deepcopy(store.overlays[0])
    result, store, _ = native(contract, source=contract["incomplete_case"]["output"], later=31)
    assert result["m9_overlay"]["status"] == "degraded"
    assert store.delivery.read("2026-10-21") == previous
    assert len(store.overlays) == 1


def test_a2_first_incomplete_contract_has_no_overlay(contract, native):
    result, store, _ = native(contract, source=contract["incomplete_case"]["output"], later=31)
    assert result["m9_overlay"]["status"] == "degraded"
    assert store.overlays == [] and store.delivery.read("2026-10-21") is None


def test_display_only_gaps_do_not_block_cooling(contract, native):
    source = deepcopy(contract["output"])
    gaps = {name: "synthetic display field unavailable" for name in ("divergence_tag", "dimensions", "systemic_tag")}
    source["missing"]["fields"]["evt-toshiba"] = gaps
    for field in gaps:
        source["events"][0][field] = None
    for affected in source["events"][0]["affected"]:
        affected["divergence_tag"] = None
    _, store, _ = native(contract, source=source)
    assert_expected(store.overlays[0], contract["expected_m9"])
    item = store.overlays[0]["tickers"]["WDC"]
    assert item["divergence_tag"] is None
    assert set(gaps) <= {gap["field"] for gap in item["m8_gaps"]}


@pytest.mark.parametrize("field", ["lifecycle", "mechanism", "exposure", "deadline_outcome", "direction"])
def test_required_provider_gaps_produce_unknown(contract, native, field):
    source = deepcopy(contract["output"])
    event = source["events"][0]
    if field == "direction":
        event["lifecycle"] = "已验证·有影响"
    key = "WDC.exposure" if field == "exposure" else field
    source["missing"]["fields"][event["event_id"]] = {key: "synthetic missing decision field"}
    _, store, _ = native(contract, source=source)
    wanted = {
        "cooling_off": False,
        "cooling_status": "unknown",
        "m8_gaps_contains": field,
        "reason_contains": "冷静期判断未完成",
    }
    assert_expected(store.overlays[0], {"WDC": wanted})
    if field == "exposure":
        assert store.overlays[0]["tickers"]["STX"]["cooling_status"] == "on"


def test_normal_nulls_are_not_reclassified_as_missing(contract, native):
    _, store, _ = native(contract)
    wdc = store.overlays[0]["tickers"]["WDC"]
    assert wdc["cooling_status"] == "on"
    assert "deadline_outcome" not in {gap["field"] for gap in wdc["m8_gaps"]}
    assert store.overlays[0]["tickers"]["STX"]["cooling_status"] == "on"


def test_known_cooling_survives_another_event_gap(contract, native):
    source = deepcopy(contract["output"])
    extra = deepcopy(source["events"][0])
    extra["event_id"] = "synthetic-partial"
    source["events"].append(extra)
    source["missing"]["fields"][extra["event_id"]] = {"mechanism": "synthetic unknown mechanism"}
    _, store, _ = native(contract, source=source)
    wdc = store.overlays[0]["tickers"]["WDC"]
    assert wdc["cooling_status"] == "on" and wdc["cooling_off"]
    assert any(gap["event_id"] == extra["event_id"] for gap in wdc["m8_gaps"])


def test_empty_complete_input_publishes_empty_overlay(tmp_path, contract):
    source = deepcopy(contract["output"])
    source["events"], source["missing"]["fields"] = [], {}
    out = run_overlay(
        clock=FrozenClock(datetime.fromisoformat(contract["cutoff"])),
        target="2026-10-21",
        source=source,
        outputs=MemoryOutputs(tmp_path),
    )
    assert out["status"] == "ok" and out["overlay"]["tickers"] == {}
    assert out["overlay"]["m8_completeness"]["unknown_tickers"] == []
