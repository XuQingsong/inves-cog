"""Rule A interpolation; Q-M3-10 fixes rounding at the book boundary."""

import math

# Muse aacea04 code/paper_trade_2026.py L127–173: book and timing interpolation knots.
CURVES = {
    "gross_margin": [(5, 5), (15, 30), (25, 50), (40, 75), (60, 95)],
    "roe": [(-10, 0), (0, 25), (5, 45), (15, 75), (25, 95)],
    "fcf_margin": [(-10, 0), (0, 30), (5, 55), (10, 75), (20, 95)],
    "fcf_conversion": [(-0.5, 0), (0, 30), (0.5, 60), (1, 85), (1.5, 95)],
    "net_debt_fcf": [(-1, 100), (0, 95), (1, 85), (3, 60), (5, 30), (8, 5)],
    "rev_growth": [(-15, 0), (-5, 15), (0, 35), (5, 50), (10, 65), (20, 82), (35, 95), (60, 100)],
    "rev_accel_pp": [(-20, 5), (-10, 25), (-3, 45), (0, 55), (5, 70), (15, 90)],
    "eps_growth": [(-30, 0), (-10, 20), (0, 40), (10, 60), (25, 80), (50, 95)],
    "gross_margin_change_pp": [(-5, 10), (-2, 35), (0, 55), (2, 75), (5, 95)],
    "pe": [(8, 98), (12, 90), (20, 72), (30, 52), (50, 28), (80, 10), (120, 3)],
    "peg": [(0.5, 95), (1, 78), (1.5, 58), (2.5, 32), (4, 12)],
    "ps": [(0.5, 98), (1, 90), (3, 72), (6, 50), (10, 28), (20, 8)],
    "fcf_yield": [(-2, 0), (0, 12), (1, 32), (3, 58), (5, 78), (8, 95)],
    "price_vs_ma200": [(-15, 5), (-5, 30), (0, 55), (5, 75), (15, 90)],
    "ma50_vs_ma200": [(-10, 5), (-3, 30), (0, 55), (3, 75), (10, 90)],
    "ma200_slope20": [(-2, 10), (-0.5, 35), (0, 55), (0.5, 75), (2, 90)],
    "mom3": [(-20, 5), (-10, 25), (0, 50), (10, 70), (25, 85), (50, 90)],
    "mom6": [(-30, 5), (-15, 25), (0, 50), (15, 70), (40, 85), (80, 90)],
    "vol_ratio": [(0.5, 25), (0.8, 45), (1, 60), (1.2, 75), (1.8, 85)],
    "up_share": [(35, 10), (45, 35), (50, 55), (55, 70), (65, 90)],
    "dev50": [(-15, 25), (-8, 45), (-3, 75), (0, 85), (3, 80), (8, 55), (15, 25), (25, 5)],
    "rsi": [(20, 35), (30, 55), (45, 75), (60, 70), (70, 45), (80, 18), (90, 5)],
    "vol20": [(20, 90), (35, 70), (50, 50), (70, 25), (100, 5)],
    "drawdown252": [(-60, 20), (-40, 35), (-25, 50), (-10, 70), (0, 85)],
}


def finite(value):
    # Muse aacea04 code/factor_framework_v3.py L32–37: None/NaN/Inf are missing; zero is valid.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def interp(value, points):
    # Muse aacea04 code/factor_framework_v3.py L32–37: linear interpolation, endpoint clamping.
    if not finite(value):
        return None
    if value <= points[0][0]:
        return float(points[0][1])
    for (left, low), (right, high) in zip(points, points[1:], strict=False):
        if value <= right:
            return float(low + (high - low) * (value - left) / (right - left))
    return float(points[-1][1])


def weighted_book(items):
    # Muse aacea04 code/factor_framework_v3.py L40–48: reweight usable scores, including zero;
    # an empty book stays None, and only the completed book is rounded (Q-M3-10).
    valid = [(score, weight) for score, weight in items if finite(score)]
    weight = sum(w for _, w in valid)
    # Muse aacea04 factor_framework_v3.py L40–48; Q-M3-10 applies to both extractors.
    return round(sum(score * w for score, w in valid) / weight, 1) if weight else None


def mean_available(values):
    # Muse aacea04 code/paper_trade_2026.py L149–173: equal weights within each timing group;
    # Q-M3-6 specifies this project's missing-input reweighting at that same boundary.
    valid = [value for value in values if finite(value)]
    return sum(valid) / len(valid) if valid else None
