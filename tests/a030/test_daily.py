from datetime import date

import pytest

from inves_cog.valuation.ceiling import cap_multiplier, dyn_pe
from inves_cog.valuation_v1.ceiling_daily import calculate_ceiling

BANDS = {"version": "fixture", "calibration_date": "2026-01-01", "thresholds": {"p60": 3, "p80": 5}}
DAY = date(2026, 10, 30)


def inputs(**updates):
    return dict(
        ticker="TEST",
        price=30,
        diluted_shares=100,
        net_debt=100,
        ni_ttm=200,
        rev_ttm=1000,
        op_margin_ttm=20,
        rev_growth=10,
        fcf_ttm=50,
        financial_filed="2026-09-01",
        **updates,
    )


def test_ev_normalized_profit_cash_quality_and_rate_sensitivity():
    row = calculate_ceiling(inputs(), day=DAY, kind="稳定", tier="防守", bands=BANDS)
    assert row["r"] == 0.07
    assert row["ev"] == 3100
    assert row["next_profit"] == pytest.approx(200 * 0.82 * 1.1)
    assert dyn_pe(row["m"], 0.07) == pytest.approx(row["ev"] / row["next_profit"])
    assert row["m_r_minus_1"] < row["m"] < row["m_r_plus_1"]
    assert row["fcf_m"] > row["m"]
    assert row["quality"] == "低"


def test_missing_debt_or_future_financial_is_not_silently_zeroed():
    for changed in ({"net_debt": None}, {"financial_filed": "2026-10-31"}):
        data = inputs()
        data.update(changed)
        row = calculate_ceiling(data, day=DAY, kind="稳定", tier=None, bands=BANDS)
        assert row["m"] is None
        assert row["missing"]


def test_loss_and_nonapplicable_methods_do_not_create_risk_band():
    data = inputs()
    data.update(ni_ttm=-20, op_margin_ttm=-2)
    loss = calculate_ceiling(data, day=DAY, kind="未盈利成长", tier=None, bands=BANDS)
    assert loss["method"] == "loss"
    assert loss["r"] == 0.10
    assert loss["implied_terminal_profit"] == pytest.approx(3100 / cap_multiplier(10, 0.1))
    for kind, method in [("周期", "cyclical"), ("金融", "financial")]:
        out = calculate_ceiling(inputs(), day=DAY, kind=kind, tier="进攻", bands=BANDS)
        assert out["method"] == method
        assert out["band"] == "不适用"


def test_calibration_from_future_cannot_be_used_for_historical_label():
    out = calculate_ceiling(inputs(), day=date(2025, 1, 1), kind="稳定", tier=None, bands=BANDS)
    assert out["band"] == "不适用"
    assert "band_calibration_not_visible" in out["missing"]


pytestmark = pytest.mark.phase1_blocking
