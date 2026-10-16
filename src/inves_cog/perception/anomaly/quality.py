"""Data-quality gates that run before a name is allowed to count."""

import numpy as np


def trailing_z(values, minimum):
    prior = [value for value in values[-121:-1] if value is not None and np.isfinite(value)]
    current = values[-1] if values else None
    if len(prior) < minimum or current is None or not np.isfinite(current):
        return None
    sigma = float(np.std(prior, ddof=1))
    if sigma == 0:
        return None
    return current / sigma


def same_sign_share(member_returns, basket_return):
    if basket_return is None or basket_return == 0:
        return None
    usable = [value for value in member_returns.values() if value not in (None, 0) and np.isfinite(value)]
    if not usable:
        return None
    return sum(np.sign(value) == np.sign(basket_return) for value in usable) / len(usable)


def stale_tickers(bars):
    blocked = set()
    for ticker, bar in (bars or {}).items():
        closes = bar.get("closes") or []
        if len(closes) >= 3 and closes[-1] == closes[-2] == closes[-3]:
            blocked.add(ticker)
    return blocked


def adjust_daily(daily, bars, split_abs):
    adjusted = []
    for row in daily:
        bar = (bars or {}).get(row["ticker"]) or {}
        copied = dict(row)
        raw = bar.get("raw_ret", row.get("ret"))
        if bar.get("adj_changed") and raw is not None and abs(raw) > split_abs:
            copied["ret"] = bar.get("adj_ret")
            copied["resid"] = None
            copied["resid_z"] = None
        adjusted.append(copied)
    return adjusted


def thin_names(session, bars, share):
    if session != "post":
        return set()
    found = set()
    for ticker, bar in (bars or {}).items():
        volumes = bar.get("volumes") or []
        post = bar.get("post_volume")
        prior = volumes[-21:-1] if len(volumes) >= 21 else volumes[:-1]
        if post is None or not prior:
            continue
        if post < share * float(np.mean(prior)):
            found.add(ticker)
    return found
