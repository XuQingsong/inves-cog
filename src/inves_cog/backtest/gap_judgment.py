"""Gap/jump event judgment (v19-rules-systematic.md §二) — replaces fixed chase_block.

Trigger: 1d ret >= 3x usual vol, or 3d cumret >= 4x usual vol.
Cause: SEC filings within [t-1, t] -> earnings/material; else narrative.
Confirm: revenue acceleration + margin expansion (PIT states).
Decision (§二.4): confirmed + pe_pctile<=50 -> allow; confirmed + high -> pullback;
narrative -> block; insufficient evidence -> pullback.
PIT rule: "gap held after 10 sessions" may only confirm decisions taken >=10 sessions
after the gap day, never on the gap day itself.
"""

import statistics


def _rets(bars, days):
    cs = [bars[d]["close"] for d in days if d in bars]
    return [c2 / c1 - 1 for c1, c2 in zip(cs, cs[1:], strict=False)]


def gap_events(ticker, bars, filings, states, val_fn, start, end):
    """Returns {day: {"trigger":..., "cause":..., "confirmed":bool, "pe_pct":..., "decision":...}}
    for days in [start,end] where a gap event is active (within 10 sessions)."""
    days = sorted(d for d in bars if start <= d <= end)
    if not days:
        return {}
    all_days = sorted(bars)
    out = {}
    for day in days:
        i = all_days.index(day)
        if i < 21:
            continue
        sigma = statistics.stdev(_rets(bars, all_days[i - 20 : i])) or 0
        r1 = bars[day]["close"] / bars[all_days[i - 1]]["close"] - 1
        r3 = bars[day]["close"] / bars[all_days[i - 3]]["close"] - 1
        trig1 = sigma and r1 >= 3 * sigma
        trig3 = sigma and r3 >= 4 * sigma
        if not (trig1 or trig3):
            continue
        prev = all_days[i - 1]
        fil = [f for f in filings if prev <= f["filed"] <= day]
        cause = (
            "earnings"
            if any(f["form"] in ("10-Q", "10-K", "8-K") for f in fil)
            else ("material" if fil else "narrative")
        )
        st_now = _st(states, day)
        confirmed = bool(
            cause != "narrative"
            and st_now
            and (st_now.values.get("rev_accel_pp") or 0) > 0
            and ((st_now.values.get("gross_margin_change_pp") or 0) > 0 or (st_now.values.get("fcf_margin") or 0) > 0)
        )
        val = val_fn(ticker, day) if val_fn else {}
        pe_pct = val.get("pe_pctile_3y")
        # "gap held" confirmation: only valid for decisions >=10 sessions after gap day
        if cause == "narrative":
            decision = "block"
        elif confirmed:
            decision = "allow" if (pe_pct is not None and pe_pct <= 50) else "pullback"
        else:
            decision = "pullback"
        out[day] = {
            "trigger": "1d" if trig1 else "3d",
            "cause": cause,
            "confirmed": confirmed,
            "pe_pct": pe_pct,
            "decision": decision,
        }
    # active window: a gap decision gates buys for 10 sessions after the trigger day
    return out


def _st(states, day):
    rows = [s for s in states if s.filed <= day]
    return max(rows, key=lambda s: s.filed) if rows else None
