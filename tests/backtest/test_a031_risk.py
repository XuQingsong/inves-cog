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


def test_portfolio_initializes_when_first_prior_week_arrives_not_next_month():
    from datetime import date
    from inves_cog.backtest.risk_study import PriceSeries, monthly_portfolio
    ds=[date(2018,1,2),date(2018,1,5),date(2018,1,8),date(2018,1,9)]
    spy=PriceSeries(ds,[100]*4)
    stock=PriceSeries(ds,[100,100,100,200])
    result=monthly_portfolio({date(2018,1,5):{'A':1}},{'A':stock},spy,date(2018,1,1),'A')
    assert result['rebalances'][0]['date']==date(2018,1,8)
    assert result['curve'][-1]['equity']==2
