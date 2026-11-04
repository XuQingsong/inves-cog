"""Per-ticker-day valuation inputs for backtest output + gap_judgment decisions.

EV = market cap + net debt; EBIT = op_margin_ttm x rev_ttm. Forward P/E from
consensus is not available historically (coverage starts 2026-10-17) — we use the
trailing P/E percentile vs the ticker's own 3-year history instead.
"""

from datetime import timedelta


def _state_asof(states, day):
    rows = [s for s in states if s.filed <= day]
    return max(rows, key=lambda s: s.filed) if rows else None


def valuation_inputs(ticker, day, price_hist, states):
    """price_hist: {date: bar} sorted mapping; states: FinState list (PIT)."""
    st = _state_asof(states, day)
    close = price_hist.get(day, {}).get("close") if day in price_hist else None
    out = {"ticker": ticker, "day": day}
    v = st.values if st else {}
    if not st or close is None or not v.get("shares"):
        return {**out, "missing": True}
    mcap = close * v.get("shares")
    ev = mcap + (v.get("net_debt") or 0)
    ebit = (v.get("op_margin_ttm") or 0) / 100 * (v.get("rev_ttm") or 0)
    ni = v.get("ni_ttm") or 0
    pe = mcap / ni if ni > 0 else None
    # trailing P/E percentile vs own 3y (bars window, same current eps base is not
    # PIT-exact per day — approximated by price/st.eps within the window)
    window = [r for d, r in price_hist.items() if day - timedelta(days=3 * 365) <= d <= day]
    if pe and v.get("eps_ttm") and len(window) > 60:
        pes = [r["close"] * v.get("shares") / ni for r in window if ni > 0]
        below = sum(1 for p in pes if p <= pe)
        pe_pct = 100 * below / len(pes)
    else:
        pe_pct = None
    prev = _state_asof(states, day - timedelta(days=365))
    pv = prev.values if prev else {}
    return {
        **out,
        "missing": False,
        "ev_ebit": round(ev / ebit, 2) if ebit > 0 else None,
        "fcf_yield": round(100 * (v.get("fcf_ttm") or 0) / mcap, 2),
        "pe_trailing": round(pe, 1) if pe else None,
        "pe_pctile_3y": round(pe_pct, 1) if pe_pct is not None else None,
        "fcf_ni_divergence": round((v.get("fcf_ttm") or 0) - ni),
        "net_debt_yoy": round((v.get("net_debt") or 0) - (pv.get("net_debt") or 0)) if prev else None,
        "shares_yoy": round(100 * ((v.get("shares") or 0) / pv.get("shares") - 1), 2)
        if prev and pv.get("shares")
        else None,
        "rev_accel_pp": v.get("rev_accel_pp"),
    }
