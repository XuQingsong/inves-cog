from datetime import date, timedelta

import pytest

from inves_cog.valuation_v1.ceiling_bands import calibrate, classify_band


def panel():
    end = date(2026, 10, 30)
    return [
        {"date": str(end - timedelta(weeks=w)), "ticker": str(i), "m8": value}
        for w in range(53)
        for i, value in enumerate([1, 2, 3, 4, 5])
    ]


def test_calibration_uses_52_visible_fridays_and_weekly_quantiles():
    rows = panel() + [{"date": "2026-11-06", "ticker": "future", "m8": 100000}]
    out = calibrate(rows, as_of=date(2026, 10, 30), source="fixture")
    assert out["sample_count"] == 260
    assert out["week_count"] == 52
    assert out["thresholds"] == pytest.approx({"p60": 3.4, "p80": 4.2})
    assert out["window_start"] == "2025-11-07"


def test_bands_include_threshold_boundaries_and_reject_missing():
    config = calibrate(panel(), as_of=date(2026, 10, 30), source="fixture")
    assert classify_band(3.399, config) == "可信"
    assert classify_band(3.4, config) == "偏高"
    assert classify_band(4.2, config) == "严重透支"
    assert classify_band(None, config) == "不适用"
    assert classify_band(float("nan"), config) == "不适用"


def test_incomplete_or_duplicate_panel_is_not_silently_calibrated():
    with pytest.raises(ValueError, match="52"):
        calibrate(panel()[:10], as_of=date(2026, 10, 30), source="fixture")
    rows = panel()
    with pytest.raises(ValueError, match="duplicate"):
        calibrate(rows + rows[:1], as_of=date(2026, 10, 30), source="fixture")


pytestmark = pytest.mark.phase1_blocking
