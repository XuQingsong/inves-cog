"""Health severity and explicit missing-field explanations."""

BLOCKING = {
    "no_bar",
    "stale_fundamentals",
    "revenue_tag_gap",
    "q4_missing",
    "companyfacts_lag",
    "core_field_missing",
    "implausible_value",
}


def health_row(state, *, foreign=False, latest_8k_202=None):
    codes = set(state.health_codes)
    missing = [key for key in ("rev_ttm", "eps_ttm", "shares") if state.values.get(key) is None]
    if missing:
        codes.add("core_field_missing")
    blocked = codes & BLOCKING
    reasons = sorted(blocked)
    if "implausible_value" in codes:
        reasons.append(str(state.field_sources.get("implausible_value", {})))
    if "extreme_value_verified" in codes:
        reasons.append(str(state.field_sources.get("extreme_value_verified", {})))
    if missing:
        reasons.append("Missing core fields: " + ", ".join(missing))
    if foreign:
        reasons.append("Foreign filer is excluded from trading")
    return {
        "ticker": state.ticker,
        "latest_period_end": state.period_end,
        "latest_filed": state.filed,
        "latest_8k_202": latest_8k_202,
        "health_codes": sorted(codes - {"ok"}) or ["ok"],
        "can_score": not blocked,
        "can_trade": not blocked and not foreign,
        "reason": "; ".join(reasons) or None,
    }
