"""A-007 D-33: a plan explains actual constraints and excludes zero-value intents."""

import pytest

from tests.m4.test_execution import DAY, NEXT, engine, position, signal

pytestmark = pytest.mark.phase1_blocking


def test_plan_zero_amount_becomes_explained_skip():
    e = engine()
    e.positions["AAA"] = position(shares=1000)
    e.decide(DAY, {"AAA": signal(entry_pass=False)}, prices={"AAA": 100})
    e.queue("AAA", "buy_to", "M-40", "确认加仓", tier="normal", fraction=0.1)
    plan = e.plan(NEXT)
    assert plan["orders"] == [] and e.pending == []
    skip = next(s for s in plan["skips"] if s["ticker"] == "AAA")
    assert skip["n_code"] == "N7" and "目标" in skip["reason_zh"]
    control = engine()
    control.decide(DAY, {"BBB": signal(ticker="BBB")}, prices={"BBB": 100})
    assert control.plan(NEXT)["orders"][0]["notional_est"] > 0


def test_plan_skip_identifies_one_actual_gate():
    e = engine()
    e.peak_equity = 2_000_000
    e.dd12 = True
    e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100})
    assert any("12%" in s["reason_zh"] for s in e.skips)
    assert all("或" not in s["reason_zh"] for s in e.skips)
    e = engine()
    e.peak_equity = 2_000_000
    e.positions["AAA"] = position(filled_fraction=0.1, first_fraction=0.4)
    e.index = 20
    e.dd12 = True
    e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100})
    assert any("12%" in s["reason_zh"] and "M-40" in s["rule_ids"] for s in e.skips)
