"""Cross-sectional rotation groups with independent volatility denominators."""

import math

import numpy as np

SECTORS = "XLK XLF XLV XLE XLI XLU XLY XLP XLB XLRE XLC SMH IGV KRE".split()
STYLES = {"iwm_qqq": ("IWM", "QQQ"), "mtum_vlue": ("MTUM", "VLUE"), "rsp_spy": ("RSP", "SPY")}


def number(value):
    return float(value) if value is not None and np.isfinite(value) else None


def return_5d(series):
    return number((1 + series.iloc[-5:]).prod(min_count=5) - 1) if len(series) >= 5 else None


def rotation_rows(returns, basket_series, *, day, session="close", post_returns=None, post_baskets=None):
    groups = {("index", t): returns[t] for t in ["SPY", "QQQ", "IWM"] if t in returns}
    groups.update({("sector", t): returns[t] for t in SECTORS if t in returns})
    groups.update(
        {("style", name): returns[a] - returns[b] for name, (a, b) in STYLES.items() if a in returns and b in returns}
    )
    groups.update({("l3", name): series for name, series in basket_series.items()})
    post_groups = {}
    if post_returns is not None:
        post_groups = {
            (kind, key): (
                post_returns[key]
                if kind in {"index", "sector"}
                else post_returns[STYLES[key][0]] - post_returns[STYLES[key][1]]
            )
            for kind, key in groups
            if kind != "l3" and (key in post_returns or kind == "style")
        }
        post_groups.update({("l3", k): v for k, v in (post_baskets or {}).items()})
    result = []
    for (kind, identifier), series in groups.items():
        sigma = number(series.iloc[-121:-1].std(ddof=1)) if series.iloc[-121:-1].count() >= 60 else None
        selected = series if session == "close" else post_groups.get((kind, identifier))
        ret = number(selected.iloc[-1]) if selected is not None else None
        five = return_5d(selected) if selected is not None else None
        z = ret / sigma if ret is not None and sigma and sigma > 0 else None
        z5 = five / (sigma * math.sqrt(5)) if five is not None and sigma and sigma > 0 else None
        reason = (
            "missing_post_price"
            if session == "post" and ret is None
            else "insufficient_history"
            if sigma is None
            else None
        )
        result.append(
            {
                "trade_date": day,
                "session": session,
                "group_kind": kind,
                "group_id": identifier,
                "ret": ret,
                "z": z,
                "ret_5d": five,
                "z_5d": z5,
                "rank": None,
                "rank_5d": None,
                "health_codes": [reason] if reason else [],
                "null_reason": reason,
            }
        )
    for kind in {row["group_kind"] for row in result}:
        for field, target in [("z", "rank"), ("z_5d", "rank_5d")]:
            valid = sorted(
                [r for r in result if r["group_kind"] == kind and r[field] is not None],
                key=lambda r: (-r[field], r["group_id"]),
            )
            for rank, row in enumerate(valid, 1):
                row[target] = rank
    return result
