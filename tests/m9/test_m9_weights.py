"""New-book weights must scale original subitems, including M11 missing-item reweighting."""

import pytest

from tests.m9.fixtures import snapshot

pytestmark = pytest.mark.phase1_blocking


def test_m9_augmented_books_reweight_original_subitems():
    from inves_cog.shadow.factors import evaluate_factors

    base = snapshot(books={"quality": 50, "growth": 82, "valuation": 10, "timing": 70})
    raw = {
        "rev_growth": 20,
        "rev_accel_pp": None,
        "eps_growth": None,
        "gross_margin_change_pp": None,
        "gross_margin": 25,
        "roe": None,
        "fcf_margin": None,
        "fcf_conversion": None,
        "net_debt_fcf": None,
        "eps_revision_30d_pct": 3,
        "segments": [
            {"revenue_4q": [10, 20, 30, 40], "margin_change_pp": 2, "revenue_yoy_pct": 35},
            {"revenue_4q": [1, 2, 3, 4], "margin_change_pp": -2, "revenue_yoy_pct": -5},
        ],
    }
    rows = {row["factor_id"]: row for row in evaluate_factors(base, raw, day="2027-04-08")}
    assert rows["F-03"]["substituted_value"] == pytest.approx((34 * 82 + 15 * 75) / 49)
    assert rows["F-04"]["substituted_value"] == pytest.approx((21.25 * 50 + 15 * 75) / 36.25)
    assert rows["F-05"]["substituted_value"] == pytest.approx((32 * 82 + 20 * 95) / 52)
    missing = {row["factor_id"]: row for row in evaluate_factors(base, {"eps_revision_30d_pct": 3}, day="2027-04-08")}
    assert missing["F-03"]["substituted_value"] is None
    assert missing["F-03"]["would_pass"] is None
