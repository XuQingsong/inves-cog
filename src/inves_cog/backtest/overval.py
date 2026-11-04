"""Overvaluation veto: weekly implied-ceiling m8 quintiles from the S&P 500 panel.

Cross-section per Friday: tickers with m8 present, ev > 0, non-financial.
A member is vetoed on decision day D when its m8 on the latest Friday <= D is
in the top quintile (>= 80th percentile) of that Friday's cross-section.
"""

import csv
from bisect import bisect_right
from datetime import date


def load_quintiles(path, financials=None):
    """Load panel csv -> {friday: {"thresh": q80, "m8": {ticker: m8}}}."""
    financials = financials or set()
    by_day = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                m8 = float(r["m8"]) if r.get("m8") else None
                ev = float(r["ev"]) if r.get("ev") else 0.0
            except ValueError:
                continue
            if m8 is None or ev <= 0 or r["ticker"] in financials:
                continue
            by_day.setdefault(date.fromisoformat(r["date"]), {})[r["ticker"]] = m8
    qmap = {}
    for d, m8s in by_day.items():
        vals = sorted(m8s.values())
        thresh = vals[int(0.8 * (len(vals) - 1))] if vals else None
        qmap[d] = {"thresh": thresh, "m8": m8s}
    return qmap, sorted(qmap)


def _friday(qmap, days, day):
    i = bisect_right(days, day) - 1
    return days[i] if i >= 0 else None


def quintile_at(qmap, days, ticker, day):
    """1-5 quintile of the ticker's m8 in the latest week's cross-section, or None."""
    f = _friday(qmap, days, day)
    if f is None:
        return None
    m8 = qmap[f]["m8"].get(ticker)
    if m8 is None:
        return None
    vals = sorted(qmap[f]["m8"].values())
    rank = sum(v <= m8 for v in vals) / len(vals)
    return min(5, int(rank * 5) + 1)


def vetoed(qmap, days, ticker, day):
    """True when the ticker's m8 is in the top quintile of the latest week's panel."""
    f = _friday(qmap, days, day)
    if f is None:
        return False
    m8, thresh = qmap[f]["m8"].get(ticker), qmap[f]["thresh"]
    return m8 is not None and thresh is not None and m8 >= thresh
