"""Rule-based tier assignment (v19-rules-systematic.md §一).

Slow variables only — PIT fundamentals (filed <= as_of) + 252-day vol/beta/maxDD.
Re-evaluated only on new filings; a tier change requires two consecutive
quarterly evaluations satisfying the new tier; hysteresis: defense entry vol<28,
exit vol>33. Output: per-ticker tier history (date, tier, driving metrics).
"""

import statistics
from datetime import timedelta


def _asof(states, day):
    rows = [s for s in states if s.filed <= day]
    return max(rows, key=lambda s: s.filed) if rows else None


def _risk_metrics(bars, spy, day):
    """252-day annualized vol (%), beta vs SPY, 1y max drawdown (%)."""
    closes = [(d, r["close"]) for d, r in sorted(bars.items()) if day - timedelta(days=365) <= d <= day]
    if len(closes) < 60:
        return None
    rets = [c2 / c1 - 1 for (_, c1), (_, c2) in zip(closes, closes[1:], strict=False)]
    vol = statistics.stdev(rets) * (252**0.5) * 100 if len(rets) > 2 else None
    spy_c = [spy[d]["close"] for d, _ in closes if d in spy]
    srets = [s2 / s1 - 1 for s1, s2 in zip(spy_c, spy_c[1:], strict=False)]
    beta = None
    if len(srets) == len(rets) and len(rets) > 2 and statistics.stdev(srets):
        cov = statistics.covariance(rets, srets)
        beta = cov / (statistics.variance(srets) or 1e-9)
    peak, maxdd = closes[0][1], 0.0
    for _, c in closes:
        peak = max(peak, c)
        maxdd = min(maxdd, 100 * (c / peak - 1))
    return {
        "vol252": round(vol, 1) if vol else None,
        "beta": round(beta, 2) if beta else None,
        "maxdd_1y": round(maxdd, 1),
    }


def _eval_tier(st, risk, prev_tier):
    if not st or not risk or risk["vol252"] is None:
        return prev_tier or "normal", {}
    v = st.values
    growth = v.get("rev_growth") or 0
    fcf_pos = v.get("fcf_pos_quarters")
    vol, beta = risk["vol252"], risk["beta"] or 1.0
    attack = (
        growth >= 30
        or (v.get("fcf_ttm") or 0) < 0
        or (fcf_pos is not None and fcf_pos < 6)
        or (vol >= 45 and growth >= 15)
    )
    defense_entry, defense_exit = vol < 28, vol > 33
    defense = (
        (defense_entry or (prev_tier == "defense" and not defense_exit))
        and beta < 0.9
        and (fcf_pos is None or fcf_pos >= 8)
        and (v.get("fcf_margin") or 0) >= 8
        and growth < 30
    )
    tier = "attack" if attack else ("defense" if defense else "normal")
    return tier, {
        "vol252": vol,
        "beta": beta,
        "rev_growth": growth,
        "fcf_margin": v.get("fcf_margin"),
        "fcf_pos": fcf_pos,
    }


def tier_history(ticker, bars, spy, states):
    """Returns [{date, tier, metrics}] — one row per filing-driven evaluation,
    with the two-consecutive-eval confirmation applied."""
    eval_days = sorted({s.filed for s in states if getattr(s, "ticker", ticker) == ticker})
    hist, pending, prev = [], None, "normal"
    for d in eval_days:
        tier, metrics = _eval_tier(_asof(states, d), _risk_metrics(bars, spy, d), prev)
        if tier != prev:
            if pending == tier:
                prev = tier
                pending = None
            else:
                pending = tier
                tier = prev
        else:
            pending = None
        hist.append({"date": d, "tier": prev, **metrics})
    return hist


def day_tier_map(hist, start, end):
    """Expand quarterly evals to a {date: tier} lookup (PIT: tier valid from eval date)."""
    out = {}
    for h in hist:
        out[h["date"]] = h["tier"]
    return out
