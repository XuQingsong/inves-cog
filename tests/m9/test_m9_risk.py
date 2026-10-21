"""Each actual price sell retains its own S10 decision and shock identity."""

import pytest

from tests.m9.fixtures import snapshot

pytestmark = pytest.mark.phase1_blocking


def test_m9_s10_keeps_each_price_order_and_residual_z():
    from inves_cog.shadow.factors import evaluate_factors

    context = {
        "rule_id": "M-51",
        "shock_flag": True,
        "resid_5d_z": -1.0,
        "earnings_reaction_5d": False,
        "s4_triggered": False,
        "m50_triggered": False,
        "new_s1": False,
        "loss_equity_pct": 0.5,
        "price": 100,
        "tier": "attack",
        "shock_id": "synthetic-shock",
        "holding_id": "synthetic-holding",
    }
    values = [
        {**context, "source_order_id": "synthetic-order-1"},
        {**context, "source_order_id": "synthetic-order-2", "m50_triggered": True},
    ]
    row = next(
        row
        for row in evaluate_factors(snapshot(), {"s10_orders": values}, day="2026-10-20")
        if row["factor_id"] == "F-08"
    )
    assert len(row["value"]) == 2
    assert [record["eligible"] for record in row["value"]] == [True, False]
    assert row["value"][0]["source_order_id"] == "synthetic-order-1"
    assert row["value"][0]["shock_id"] == "synthetic-shock"


def test_m9_missing_s1_history_is_unknown_not_clear():
    from inves_cog.shadow.risk_inputs import s1_from_history

    assert s1_from_history([]) is None
    assert s1_from_history([{"rev_accel_pp": -11}, {"rev_accel_pp": -10}]) is True
