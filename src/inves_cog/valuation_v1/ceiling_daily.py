"""Auditable EV reverse valuation, independent of all trading decisions."""

from inves_cog.valuation.ceiling import cap_multiplier, implied_m
from inves_cog.valuation_v1.ceiling_bands import classify_band, finite


def calculate_ceiling(data, *, day, kind, tier, bands, asof=None):
    method = {"周期": "cyclical", "金融": "financial"}.get(kind, "growth")
    missing = []
    r = 0.10 if tier == "进攻" or method == "cyclical" else 0.07 if tier == "防守" else 0.08
    if tier is None:
        missing.append("rule_a_tier")
    row = dict(
        ticker=data["ticker"],
        trade_date=str(day),
        method=method,
        r=r,
        m=None,
        m_r_minus_1=None,
        m_r_plus_1=None,
        fcf_m=None,
        quality="高",
        band="不适用",
        band_rule=bands["version"],
        missing=missing,
        asof=str(asof or day),
        evidence={},
        ev=None,
        next_profit=None,
        implied_terminal_profit=None,
    )
    row["evidence"] = {
        k: data.get(k) for k in ("rev_growth", "rev_accel_pp", "gross_margin", "roic", "financial_filed")
    }
    if str(bands["calibration_date"]) > str(day):
        missing.append("band_calibration_not_visible")
    if not data.get("financial_filed") or str(data["financial_filed"])[:10] > str(day):
        missing.append("visible_financial_state")
        return row
    for key in ("price", "diluted_shares", "net_debt"):
        if finite(data.get(key)) is None or key != "net_debt" and data[key] <= 0:
            missing.append(key)
    if data.get("listed_unit_blockers"):
        missing.append("listing_units")
    if any(k in missing for k in ("price", "diluted_shares", "net_debt", "listing_units")):
        return row
    row["ev"] = ev = data["price"] * data["diluted_shares"] + data["net_debt"]
    if ev <= 0:
        missing.append("positive_enterprise_value")
        return row
    if method in {"cyclical", "financial"}:
        row["evidence"]["method_reason"] = "周期股" if method == "cyclical" else "金融股"
        return row
    ni, rev, margin = (finite(data.get(k)) for k in ("ni_ttm", "rev_ttm", "op_margin_ttm"))
    if ni is None or rev is None or margin is None:
        missing.extend(k for k in ("ni_ttm", "rev_ttm", "op_margin_ttm") if finite(data.get(k)) is None)
        return row
    # Same disclosed operating-profit convention as the accepted PIT panel.
    nopat = rev * margin / 100 * 0.82
    row["evidence"].update(normalized_profit=nopat, tax_rate_proxy=0.18)
    growth = finite(data.get("rev_growth"))
    forward = finite(data.get("fy1_eps"))
    if forward is not None and forward > 0:
        profit = forward * data["diluted_shares"]
        row["evidence"]["profit_basis"] = "visible_FY1_consensus"
    else:
        if growth is None:
            missing.append("rev_growth")
            return row
        profit = nopat * (1 + max(-0.2, min(0.5, growth / 100)))
        row["evidence"]["profit_basis"] = "normalized_TTM_revenue_growth_proxy"
        missing.append("FY1_consensus")
    row["next_profit"] = profit
    m = implied_m(ev / profit, r) if profit > 0 else None
    if ni <= 0 or nopat <= 0 or profit <= 0 or m is None or m > 40:
        row.update(method="loss", r=0.10, implied_terminal_profit=ev / cap_multiplier(10, 0.10))
        row["evidence"].update(terminal_profit_5y=ev / cap_multiplier(5, 0.10), method_reason="亏损或隐含倍数超过40")
        return row
    row.update(m=m, m_r_minus_1=implied_m(ev / profit, r - 0.01), m_r_plus_1=implied_m(ev / profit, r + 0.01))
    fcf = finite(data.get("fcf_ttm"))
    if fcf is None:
        missing.append("fcf_ttm")
        row["quality"] = "低"
    else:
        ratio = fcf / ni if ni > 0 else None
        row["evidence"]["fcf_net_profit_ratio"] = ratio
        if ratio is not None and ratio < 0.5:
            row["quality"] = "低"
            row["fcf_m"] = implied_m(ev / fcf, r) if fcf > 0 else None
    if "band_calibration_not_visible" not in missing:
        row["band"] = classify_band(m, bands)
    return row
