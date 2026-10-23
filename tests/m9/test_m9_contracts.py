"""Frozen M9 acceptance contracts, committed before implementation."""

from copy import deepcopy
from pathlib import Path

import pytest

from tests.harness.tools.golden import load_golden
from tests.m9.fixtures import clock, event, snapshot

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]


def test_overlay_only_tightens():
    from inves_cog.overlay.rules import generate_overlay
    from inves_cog.trading.execution.contracts import overlay_state

    result = generate_overlay([event()], clock=clock(), version=1, source_asof=clock().now_utc())
    before = deepcopy(result)
    state, rows = overlay_state(
        result,
        clock().now_utc().astimezone(__import__("zoneinfo").ZoneInfo("Asia/Shanghai")).date(),
        asof=clock().now_utc(),
    )
    assert state["status"] == "ok" and rows["WDC"]["cooling_off"] is True
    assert result == before
    for row in rows.values():
        assert row["first_lot_multiplier"] == 1.0 and row["stop_review_eligible"] is False
        assert not {"increase_qty", "sell", "orders", "buy"} & row.keys()
    from inves_cog.overlay.delivery import validate_payload

    for forbidden in ("increase_qty", "sell", "orders", "buy"):
        invalid = deepcopy(result)
        invalid["tickers"]["WDC"][forbidden] = 1
        with pytest.raises(ValueError):
            validate_payload(invalid)


def test_overlay_cooling_rules():
    from inves_cog.overlay.rules import generate_overlay

    def cooling(e):
        return generate_overlay([e], clock=clock(), version=1, source_asof=clock().now_utc())["tickers"]["WDC"][
            "cooling_off"
        ]

    for state in ("市场确认", "基本面核查中"):
        for direction in ("有利", "不利"):
            assert cooling(event(lifecycle=state, direction=direction))
    for state in ("已发现", "假设中", "已衰减·无影响", "已证伪", "条件风险"):
        assert not cooling(event(lifecycle=state))
    assert not cooling(event(mechanism="估值倍数"))
    assert not cooling(event(affected=[{"ticker": "WDC", "exposure": "概念关联"}]))
    assert not cooling(event(lifecycle="已验证·有影响", direction="有利"))
    assert cooling(event(lifecycle="已验证·有影响", next_filing_at="2026-10-21T12:00:00Z"))
    assert not cooling(event(lifecycle="已验证·有影响", next_filing_at="2026-10-20T12:15:00Z"))
    assert not cooling(event(deadline_outcome="条件风险"))
    result = generate_overlay(
        [event(), event(event_id="E2", lifecycle="已证伪")], clock=clock(), version=2, source_asof=clock().now_utc()
    )
    assert result["tickers"]["WDC"]["cooling_off"] is True


def test_overlay_contract(tmp_path):
    from fastapi.testclient import TestClient

    from inves_cog.overlay.api import create_app
    from inves_cog.overlay.delivery import FileDelivery
    from inves_cog.overlay.rules import generate_overlay

    result = generate_overlay([event()], clock=clock(), version=7, source_asof=clock().now_utc())
    assert set(result) == {
        "version",
        "generated_at",
        "source_events_asof",
        "params_version",
        "tickers",
        "market",
        "m8_completeness",
    }
    assert result["params_version"] == "p-2026.10"
    assert "synthetic-E1" in result["tickers"]["WDC"]["reason"]
    delivery = FileDelivery(tmp_path)
    delivery.publish("2026-10-20", result)
    assert (tmp_path / "event_overlay_2026-10-20.json").is_file()
    with TestClient(create_app(delivery)) as client:
        response = client.get("/api/linkage/overlay?date=2026-10-20")
        assert response.status_code == 200 and response.json() == delivery.read("2026-10-20") == result
        assert client.get("/api/linkage/overlay?date=bad").status_code == 422
    stale = generate_overlay([], clock=clock(), version=8, source_asof=None, source_complete=False, previous=result)
    assert stale == result and stale["generated_at"] == result["generated_at"]
    with pytest.raises(ValueError):
        generate_overlay(
            [event(created_at="2026-10-21T00:00:00Z")], clock=clock(), version=8, source_asof="2026-10-21T00:00:00Z"
        )


def test_shadow_signals_no_orders():
    from inves_cog.shadow.repository import WriteRepository
    from tests.harness.tools.permissions import assert_no_select, assert_no_write

    assert_no_select("role_trading", "perception_shadow")
    assert_no_write("role_shadow", "trading")
    assert WriteRepository.allowed_tables == {
        "perception_shadow.signals",
        "factor_shadow.registry",
        "factor_shadow.daily",
        "factor_shadow.f02_state",
    }
    sql = (ROOT / "migrations/phase1_m9_0001_overlay_shadow.sql").read_text()
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA perception_shadow FROM role_trading" in sql
    with pytest.raises(ValueError):
        WriteRepository(None).write("trading.orders", {})


def test_factor_shadow_no_orders():
    from inves_cog.shadow.factors import evaluate_factors
    from inves_cog.shadow.repository import WriteRepository
    from tests.harness.tools.permissions import assert_no_select, assert_no_write

    assert_no_select("role_trading", "factor_shadow")
    assert_no_write("role_shadow", "trading")
    original = snapshot()
    rows = evaluate_factors(original, {}, day="2026-10-20")
    assert len(rows) == 8 and original == snapshot()
    assert {row["factor_id"] for row in rows} == {f"F-{i:02}" for i in range(1, 9)}
    assert all(row["value"] is None and row["would_pass"] is None and row["gap_detail"]["null_reason"] for row in rows)
    assert all("orders" not in row for row in rows)
    with pytest.raises(ValueError):
        WriteRepository(None).write("trading.ledger", {})


def test_x1_once_per_event():
    from inves_cog.shadow.signals import generate_signals

    obs = {
        "WDC": {
            "holding_id": "synthetic-position-1",
            "holding": True,
            "eps_change_pct": -5,
            "close": 90,
            "ma50": 100,
            "source_order_ids": ["synthetic-plan-1"],
        }
    }
    rows = generate_signals([event(lifecycle="已验证·有影响")], obs, day="2026-10-20", seen=set())
    x1 = [row for row in rows if row["signal"] == "X1"]
    assert len(x1) == 1 and x1[0]["event_id"] == "synthetic-E1"
    assert all(x1[0]["condition_detail"]["conditions"].values())
    assert x1[0]["condition_detail"]["evidence_ids"] == ["synthetic-info-1"]
    assert x1[0]["shadow_action"] == "减1/3"
    repeated = generate_signals([event(lifecycle="已验证·有影响")], obs, day="2026-10-21", seen={x1[0]["signal_key"]})
    assert not [row for row in repeated if row["signal"] == "X1"]
    obs["WDC"]["holding_id"] = "synthetic-position-2"
    assert any(
        row["signal"] == "X1"
        for row in generate_signals(
            [event(lifecycle="已验证·有影响")], obs, day="2026-10-21", seen={x1[0]["signal_key"]}
        )
    )
    obs["WDC"]["eps_change_pct"] = None
    assert not [
        row
        for row in generate_signals([event(lifecycle="已验证·有影响")], obs, day="2026-10-21", seen=set())
        if row["signal"] == "X1"
    ]


def test_f01_values():
    from inves_cog.shadow.factors import f01

    for case in load_golden("m9_factor_shadow.json")["f01_growth_adjusted_valuation"]:
        result = f01(case["input"])
        for key, value in case["expected"].items():
            if key == "note":
                continue
            assert result[key] is None if value is None else result[key] == pytest.approx(value, abs=1e-6)


def test_f02_values():
    from inves_cog.shadow.factors import f02

    for case in load_golden("m9_factor_shadow.json")["f02_inflection_quality"]:
        assert f02(case["input"])["f02_score"] == pytest.approx(case["expected"]["f02_score"], abs=1e-6)


def test_f02_shadow_hysteresis():
    from inves_cog.shadow.hysteresis import step_hysteresis

    state = {}
    sequence = load_golden("m9_factor_shadow.json")["f02_hysteresis"]["sequence"]
    for obs in sequence:
        state, result = step_hysteresis(state, {**obs, "filing_id": str(obs["day"]), "quality_line": 45})
        assert state["active"] is obs["b2_active"]
        expected = obs["expected_action"]
        assert result["action"] == (
            "entry" if expected == "buy" else "half" if "1/2" in expected else "close" if "清仓" in expected else "none"
        )
    before = deepcopy(state)
    again, result = step_hysteresis(state, {**sequence[-1], "filing_id": "120", "quality_line": 45})
    assert again == before and result["action"] == "none"


def test_single_factor_substitution():
    from inves_cog.shadow.substitution import substitute

    base = snapshot()
    result = substitute(base, factor_id="F-01", book="valuation", value=34.0)
    assert result["would_pass"] is True and result["n_code"] == "N9"
    assert result["books"]["valuation"] == 34 and result["books"]["quality"] == 55
    assert base == snapshot()
    assert substitute(snapshot(m32_ok=False), factor_id="F-01", book="valuation", value=65)["would_pass"] is False
    assert substitute(snapshot(m32_ok=None), factor_id="F-01", book="valuation", value=65)["would_pass"] is None
    assert substitute(base, factor_id="F-01", book="valuation", value=29)["would_pass"] is False
    assert substitute(base, factor_id="F-01", book="valuation", value=None)["would_pass"] is None


def test_factor_versioning():
    from inves_cog.shadow.registry import Registry

    registry = Registry()
    first = registry.register("F-01", {"definition": "first"}, at=clock().now_utc())
    registry.record(
        {"date": "2026-10-20", "ticker": "SYNTH", "factor_id": "F-01", "version": first["version"], "value": 2}
    )
    old = deepcopy(registry.daily)
    assert registry.register("F-01", {"definition": "first"}, at=clock().now_utc()) == first
    second = registry.register("F-01", {"definition": "new"}, at=clock().now_utc())
    assert second["version"] != first["version"] and registry.daily == old
    assert len(registry.initial_definitions()) == 8
    assert all(row["status"] == "影子计算" for row in registry.initial_definitions())


def test_s10_eligibility_shadow():
    from inves_cog.shadow.factors import s10

    inp = {
        "rule_id": "M-51",
        "shock_flag": True,
        "resid_5d": -1.0,
        "sigma_5d": 1.0,
        "earnings_reaction_5d": False,
        "s4_triggered": False,
        "m50_triggered": False,
        "new_s1": False,
        "loss_equity_pct": 1.49,
        "price": 100,
        "tier": "attack",
        "systemic_event_tag": "关税 / 贸易",
        "shock_id": "synthetic-shock",
        "holding_id": "synthetic-position",
    }
    result = s10(inp)
    assert result["eligible"] is True and result["secondary_price"] == pytest.approx(91)
    for key, value in [
        ("shock_flag", False),
        ("resid_5d", -1.01),
        ("earnings_reaction_5d", True),
        ("new_s1", True),
        ("s4_triggered", True),
        ("m50_triggered", True),
        ("loss_equity_pct", 1.5),
    ]:
        assert s10({**inp, key: value})["eligible"] is False
    for rule in ("M-50", "S4", "M-56"):
        assert s10({**inp, "rule_id": rule})["eligible"] is False
    assert s10({**inp, "shock_flag": None})["eligible"] is None
    assert s10({**inp, "already_reviewed": True})["eligible"] is False
    assert s10({**inp, "systemic_event_tag": "无"})["eligible"] is True
