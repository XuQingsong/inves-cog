"""Chase-v2 staged entry (v19-rules-systematic.md §二.4b).

Trigger on the signal day: 5d ret >= 2 x (60d daily vol x sqrt(5)) OR 1d gap >= 3 x vol.
Categories: confirmed+reasonable (growth-adj P/E = trailing P/E / max(rev_growth%,5)
<= own 3y median) -> 1/2; confirmed+stretched -> 1/3; insufficient -> 1/3; narrative -> 0.
Chase-tranche stop: close < pre-gap close -> sell staged shares.
PIT: all decisions use data up to the decision day only.
"""

import statistics


def vol60(bars, day):
    """60-day daily-return stdev through `day`."""
    days = sorted(d for d in bars if d <= day)[-61:]
    if len(days) < 30:
        return None
    rets = [bars[d2]["close"] / bars[d1]["close"] - 1 for d1, d2 in zip(days, days[1:])]
    return statistics.stdev(rets) if len(rets) > 5 else None


def chase_trigger(bars, day):
    """Returns (triggered, pre_gap_close) or None."""
    days = sorted(d for d in bars if d <= day)
    if len(days) < 7:
        return None
    v = vol60(bars, day)
    if not v:
        return None
    r5 = bars[day]["close"] / bars[days[-6]]["close"] - 1
    r1 = bars[day]["close"] / bars[days[-2]]["close"] - 1
    if r5 >= 2 * v * (5 ** 0.5) or r1 >= 3 * v:
        return True, bars[days[-2]]["close"]
    return None


def category(gap_ev, val):
    """confirmed+reasonable / confirmed+stretched / insufficient / narrative."""
    if not gap_ev:
        return "insufficient"
    if gap_ev.get("cause") == "narrative":
        return "narrative"
    if not gap_ev.get("confirmed"):
        return "insufficient"
    pe_pct = val.get("pe_pctile_3y") if val else None
    return "reasonable" if (pe_pct is not None and pe_pct <= 50) else "stretched"


def tranche(category_name):
    return {"reasonable": 0.5, "stretched": 1 / 3, "insufficient": 1 / 3, "narrative": 0.0}[category_name]
