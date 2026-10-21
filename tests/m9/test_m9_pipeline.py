"""Pipeline acceptance uses labelled snapshots; no live source or production connection."""

from copy import deepcopy
from datetime import date, datetime

import pytest
import yaml

from inves_cog.clock import FrozenClock
from tests.m9.fixtures import event, snapshot

pytestmark = pytest.mark.phase1_blocking


def test_m9_missing_source_keeps_original_overlay_timestamp(tmp_path):
    from inves_cog.shadow.pipeline import MemoryOutputs, run_overlay

    store = MemoryOutputs(tmp_path)
    clock = FrozenClock(datetime.fromisoformat("2026-10-20T12:15:00Z"))
    complete = {"complete": True, "source_events_asof": clock.now_utc().isoformat(), "events": [event()]}
    first = run_overlay(clock=clock, target="2026-10-20", source=complete, outputs=store)
    old = deepcopy(first["overlay"])
    later = FrozenClock(datetime.fromisoformat("2026-10-20T12:20:00Z"))
    out = run_overlay(clock=later, target="2026-10-20", source={"complete": False}, outputs=store)
    assert out["status"] == "degraded" and out["overlay"] == old and len(store.overlays) == 1
    assert store.delivery.read("2026-10-20") == old


def test_m9_shadow_pipeline_has_all_59_and_source_links(tmp_path):
    from inves_cog.shadow.pipeline import MemoryOutputs, run_shadows

    names = [row["ticker"] for row in yaml.safe_load(open("config/universe.yaml"))["stocks"]]
    assert len(names) == 59
    bundle = {
        "kind": "synthetic",
        "target": "2026-10-20",
        "scores": {},
        "factor_inputs": {},
        "observations": {},
        "m8": {"events": []},
        "plan": {"plan_id": "synthetic-plan", "orders": []},
    }
    bundle["scores"]["LITE"] = snapshot(ticker="LITE")
    bundle["factor_inputs"]["LITE"] = {
        "ps": 30,
        "rev_growth": 60,
        "pe": None,
        "prev_eps_ttm": -1,
        "prev_net_margin_pct": -3,
        "fcf_yield": 0,
    }
    bundle["observations"]["WDC"] = {
        "holding_id": "synthetic-position",
        "holding": True,
        "eps_change_pct": -6,
        "close": 90,
        "ma50": 100,
        "source_order_ids": ["synthetic-order"],
    }
    bundle["m8"]["events"] = [event(lifecycle="已验证·有影响")]
    store = MemoryOutputs(tmp_path)
    clock = FrozenClock(datetime.fromisoformat("2026-10-20T12:20:00Z"))
    out = run_shadows(clock=clock, target="2026-10-20", bundle=bundle, tickers=names, outputs=store)
    assert len(out["factors"]) == 59 * 8
    assert all(len([row for row in out["factors"] if row["ticker"] == ticker]) == 8 for ticker in names)
    assert any(
        row["ticker"] == "LITE" and row["factor_id"] == "F-01" and row["value"] is not None for row in out["factors"]
    )
    assert all(row["gap_detail"]["null_reason"] for row in out["factors"] if row["value"] is None)
    x1 = next(row for row in out["signals"] if row["signal"] == "X1")
    assert x1["condition_detail"]["source_order_ids"] == ["synthetic-order"]
    assert out["source_kind"] == "synthetic" and out["business_orders_written"] == 0
    again = run_shadows(clock=clock, target="2026-10-20", bundle=bundle, tickers=names, outputs=store)
    assert not [row for row in again["signals"] if row["signal"] == "X1"]


def test_m9_schedule_uses_native_window_plan_and_premarket_dependencies():
    from inves_cog.shadow.scheduling import due_stages

    summer = FrozenClock(datetime.fromisoformat("2026-10-20T12:05:00Z"))
    winter = FrozenClock(datetime.fromisoformat("2026-11-03T13:05:00Z"))
    assert due_stages(summer, premarket_ready=True, plan_ready=False, source_ready=True) == ["overlay"]
    assert due_stages(winter, premarket_ready=True, plan_ready=True, source_ready=True) == ["overlay", "shadows"]
    assert due_stages(summer, premarket_ready=False, plan_ready=True, source_ready=True) == ["shadows"]
    assert due_stages(summer, premarket_ready=True, plan_ready=True, source_ready=False) == ["shadows"]
    before = FrozenClock(datetime.fromisoformat("2026-11-03T12:05:00Z"))
    after = FrozenClock(datetime.fromisoformat("2026-10-20T12:30:00Z"))
    for clock in (before, after):
        # FR20 runs shadows after the actual plan; only overlay publication owns the 08:30 deadline.
        assert due_stages(clock, premarket_ready=True, plan_ready=True, source_ready=True) == ["shadows"]


def test_m9_extra_factors_and_signal_boundary_contracts():
    from inves_cog.shadow.factors import evaluate_factors
    from inves_cog.shadow.signals import generate_signals

    base = snapshot()
    raw = {
        "eps_revision_30d_pct": 3,
        "cap": 0.08,
        "vol60": None,
        "vol20": 100,
        "plan_buy_amount": 1000,
        "segments": [
            {"revenue_4q": [10, 20, 30, 40], "margin_change_pp": 2, "revenue_yoy_pct": 20},
            {"revenue_4q": [1, 2, 3, 4], "margin_change_pp": -2, "revenue_yoy_pct": -5},
        ],
        "valuation_shadow": {"vt1": True, "vt2": False, "version": "M5-original"},
    }
    rows = {row["factor_id"]: row for row in evaluate_factors(base, raw, day="2027-04-08")}
    assert rows["F-03"]["value"] == 75
    assert rows["F-04"]["value"] == 75
    assert rows["F-05"]["value"] == 82
    assert rows["F-06"]["value"]["cap_eff"] == 0.04 and rows["F-06"]["substituted_value"] == 500
    assert rows["F-07"]["value"]["version"] == "M5-original"
    prior = {row["factor_id"]: row for row in evaluate_factors(base, raw, day="2027-04-07")}
    assert prior["F-03"]["value"] is None and prior["F-03"]["gap_detail"]["null_reason"] == "快照不足"
    obs = {
        "WDC": {
            "base_opening_order": True,
            "source_order_ids": ["synthetic-opening"],
            "actual_watchlist_wave_buy": True,
            "divergence_tag": "情绪性折价",
        }
    }
    signals = generate_signals([event()], obs, day="2026-10-20", seen=set())
    assert {row["signal"] for row in signals} == {"X2", "X3", "X4"}
    x4 = next(row for row in signals if row["signal"] == "X4")
    assert x4["condition_detail"]["status"] == "快照不足"


def test_m9_snapshot_rejects_future_and_unlabelled_history():
    from inves_cog.shadow.inputs import validate_snapshot

    cutoff = datetime.fromisoformat("2026-10-20T12:15:00Z")
    with pytest.raises(ValueError):
        validate_snapshot({"target": "2026-10-20"}, cutoff=cutoff, target=date(2026, 10, 20))
    row = {
        "kind": "synthetic",
        "target": "2026-10-20",
        "source_events_asof": cutoff.isoformat(),
        "m8": {"complete": True, "source_events_asof": "2026-10-21T00:00:00Z"},
    }
    with pytest.raises(ValueError):
        validate_snapshot(row, cutoff=cutoff, target=date(2026, 10, 20))
    row["m8"] = {"complete": False}
    row["scores"] = {"SYNTH": {"observed_at": "2026-10-21T00:00:00Z"}}
    with pytest.raises(ValueError):
        validate_snapshot(row, cutoff=cutoff, target=date(2026, 10, 20))
