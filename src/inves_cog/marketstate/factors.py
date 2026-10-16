"""Price-only factors, effective membership and leave-one-out construction."""

import numpy as np
import pandas as pd

from inves_cog.marketstate.regression import residual_series


def adjusted_returns(frame):
    return (frame["close"] * frame["adj_factor"]).pct_change(fill_method=None)


def post_return(close, post_close):
    if close is None or post_close is None or close <= 0:
        return None
    value = post_close / close - 1
    return value if np.isfinite(value) else None


def basket_return(returns, members, *, exclude=None):
    columns = [ticker for ticker in members if ticker != exclude and ticker in returns]
    if not columns:
        return pd.Series(np.nan, index=returns.index, dtype=float)
    frame = returns[columns]
    minimum = 1 if exclude is not None else 2
    return frame.mean(axis=1).where(frame.notna().sum(axis=1) >= minimum)


def member_tickers(basket, day):
    result = []
    for member in basket["members"]:
        if isinstance(member, str):
            result.append(member)
            continue
        start, end = member.get("effective_from"), member.get("effective_to")
        if (start is None or str(start) <= str(day)) and (end is None or str(day) < str(end)):
            result.append(member["ticker"])
    return result


def effective_basket_return(returns, basket, *, exclude=None):
    output = []
    for day in returns.index:
        current = basket_return(returns.loc[[day]], member_tickers(basket, day), exclude=exclude)
        output.append(current.iloc[0])
    return pd.Series(output, index=returns.index, dtype=float)


def orthogonalize(series, factors):
    return pd.Series(residual_series(series, factors), index=series.index, dtype=float)


def leave_one_out_members(basket, day, ticker):
    return set(member_tickers(basket, day)) - {ticker}


def theme_duplicates_sector(returns, ticker, l2, l3):
    if l2 is None or l3 is None:
        return False
    return all(
        leave_one_out_members(l2, day, ticker) == leave_one_out_members(l3, day, ticker) for day in returns.index
    )


def stock_factors(returns, *, ticker, l2=None, l3=None, sector_etf=None):
    factors = pd.DataFrame({"m": returns["SPY"]})
    reasons = []
    sector = None
    if l2:
        sector = effective_basket_return(returns, l2, exclude=ticker)
    elif sector_etf in returns and sector_etf != "SPY":
        sector = returns[sector_etf]
    else:
        reasons.append("sector_unmapped")
    if sector is not None and sector.notna().any():
        factors["s"] = orthogonalize(sector, factors[["m"]])
    elif l2:
        reasons.append("empty_l2_after_leave_one_out")
    if l3 and theme_duplicates_sector(returns, ticker, l2, l3):
        reasons.append("l3_same_as_l2")
    elif l3:
        theme = effective_basket_return(returns, l3, exclude=ticker)
        if theme.notna().any():
            factors["t"] = orthogonalize(theme, factors.copy())
        else:
            reasons.append("empty_l3_after_leave_one_out")
    return factors, reasons
