"""Risk research rejects unfinished horizons and handles terminal quote truncation."""

from datetime import date

import pytest

pytestmark = pytest.mark.phase1_blocking


def test_drawdown_includes_entry_and_uses_peak_not_entry():
    from inves_cog.backtest.risk_study import max_drawdown

    assert max_drawdown([100, 200, 80, 180]) == pytest.approx(-60)


def test_monthly_weights_half_weight_top_group_and_keep_missing_m():
    from inves_cog.backtest.risk_study import weights

    sample = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "MISSING": None}
    a, b, c = (weights(sample, variant) for variant in ("A", "B", "C"))
    assert "MISSING" in a and "MISSING" in b
    assert "E" not in b
    assert c["E"] / c["A"] == pytest.approx(0.5)
    assert sum(c.values()) == pytest.approx(1)


def test_forward_window_never_fills_an_unfinished_two_year_horizon():
    from inves_cog.backtest.risk_study import horizon_metrics

    prices = {date(2024, 1, 2): 100, date(2024, 1, 3): 90}
    assert horizon_metrics(prices, prices, date(2024, 1, 2), 104) is None
