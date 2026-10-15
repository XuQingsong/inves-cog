"""Market state v5/v6 and five-day explanations, using prices alone."""

import math


def beta_share(resid_5d, total_return_5d):
    if resid_5d is None or total_return_5d is None or abs(total_return_5d) < 0.005:
        return None
    return max(0.0, min(1.0, 1 - abs(resid_5d) / abs(total_return_5d)))


def market_flags(
    *, spy_5d_pct=None, vix_pctile_252=None, down_share_5d_pct=None, vix_term_inverted=None, spy_drawdown_252_pct=None
):
    def le(value, bound):
        return value is not None and value <= bound

    def ge(value, bound):
        return value is not None and value >= bound

    shock = (le(spy_5d_pct, -5) or ge(vix_pctile_252, 80)) and ge(down_share_5d_pct, 70)
    warning = (
        sum([le(spy_5d_pct, -3), ge(vix_pctile_252, 70), ge(down_share_5d_pct, 60)]) >= 2
        or vix_term_inverted is True
        or le(spy_drawdown_252_pct, -10)
    )
    missing = [
        name
        for name, value in {
            "spy_5d_pct": spy_5d_pct,
            "vix_pctile_252": vix_pctile_252,
            "down_share_5d_pct": down_share_5d_pct,
            "vix_term_inverted": vix_term_inverted,
            "spy_drawdown_252_pct": spy_drawdown_252_pct,
        }.items()
        if value is None
    ]
    return {
        "shock_flag": bool(shock),
        "l1_state": "危机" if shock else "警戒" if warning else "正常",
        "null_reason": ";".join("missing:" + key for key in missing) or None,
    }


def five_day(residuals, sigma, total_return):
    complete = len(residuals) == 5 and all(x is not None and math.isfinite(x) for x in residuals)
    total = sum(residuals) if complete else None
    z = total / (sigma * math.sqrt(5)) if total is not None and sigma is not None and sigma > 0 else None
    return {"resid_5d": total, "resid_5d_z": z, "beta_share_5d": beta_share(total, total_return)}
