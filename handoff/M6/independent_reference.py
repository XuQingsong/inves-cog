"""Owner-runnable reference: raw prices -> factors -> OLS using independent QR.

No imports from the production marketstate computation package.
Use a read-only PostgreSQL connection with dict rows and call verify(connection).
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd


def regression(y, features, index):
    raw = features[max(0, index - 120) : index]
    target = y[max(0, index - 120) : index]
    valid = np.isfinite(raw).all(axis=1) & np.isfinite(target)
    if valid.sum() < 60:
        return None
    design = np.column_stack((np.ones(valid.sum()), raw[valid]))
    if np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    q, r = np.linalg.qr(design, mode="reduced")
    coefficients = np.linalg.solve(r, q.T @ target[valid])
    residuals = target[valid] - design @ coefficients
    sigma = np.sqrt(residuals @ residuals / (len(residuals) - design.shape[1]))
    return coefficients, sigma, int(valid.sum())


def residuals(y, features):
    output = np.full(len(y), np.nan)
    for index in range(len(y)):
        model = regression(y, features, index)
        if model and np.isfinite(y[index]) and np.isfinite(features[index]).all():
            output[index] = y[index] - np.r_[1, features[index]] @ model[0]
    return output


def members(basket, day, exclude=None):
    return [
        r["ticker"]
        for r in basket["members"]
        if r["ticker"] != exclude
        and (not r.get("effective_from") or str(r["effective_from"]) <= str(day))
        and (not r.get("effective_to") or str(day) < str(r["effective_to"]))
    ]


def mean_basket(frame, basket, exclude):
    result = []
    for day, row in frame.iterrows():
        names = [t for t in members(basket, day, exclude) if t in frame]
        available = row[names].dropna()
        result.append(float(available.mean()) if len(available) else np.nan)
    return np.array(result)


def one(frame, baskets, ticker, day):
    l2 = next(b for b in baskets if b["level"] == "L2" and ticker in members(b, day))
    l3 = next(
        b
        for b in baskets
        if b["level"] == "L3" and any(r["ticker"] == ticker and r.get("primary") for r in b["members"])
    )
    market = frame[["SPY"]].to_numpy()
    sector = mean_basket(frame, l2, ticker)
    s = residuals(sector, market)
    stage2 = np.column_stack((market, s))
    theme = mean_basket(frame, l3, ticker)
    t = residuals(theme, stage2)
    features = np.column_stack((stage2, t))
    target = frame[ticker].to_numpy()
    model = regression(target, features, len(frame) - 1)
    assert model is not None
    coefficients, sigma, nobs = model
    return {
        "resid": float(target[-1] - np.r_[1, features[-1]] @ coefficients),
        "alpha": float(coefficients[0]),
        "betas": coefficients[1:].tolist(),
        "sigma": float(sigma),
        "nobs": nobs,
        "l2": l2["basket_id"],
        "l3": l3["basket_id"],
    }


def verify(connection):
    days = [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]
    baskets = connection.execute("SELECT * FROM graph.baskets WHERE level IN ('L2','L3')").fetchall()
    needed = sorted({"SPY"} | {r["ticker"] for b in baskets for r in b["members"]})
    bars = connection.execute(
        "SELECT ticker,trade_date,close,adj_factor FROM ingest.bars_daily "
        "WHERE ticker=ANY(%s) AND trade_date BETWEEN %s AND %s",
        (needed, days[0] - timedelta(days=800), days[-1]),
    ).fetchall()
    data = pd.DataFrame(bars)
    data["adjusted"] = data["close"] * data["adj_factor"]
    prices = data.pivot(index="trade_date", columns="ticker", values="adjusted").sort_index()
    checks = []
    for day in days:
        frame = prices.loc[:day].pct_change(fill_method=None).tail(421)
        for ticker in ["WDC", "AMD", "ANET"]:
            reference = one(frame, baskets, ticker, day)
            actual = connection.execute(
                "SELECT resid,beta_m,beta_s,beta_t,sigma FROM marketstate.daily "
                "WHERE trade_date=%s AND ticker=%s AND session='close'",
                (day, ticker),
            ).fetchone()
            error = abs(reference["resid"] - actual["resid"])
            checks.append(
                {
                    "ticker": ticker,
                    "trade_date": str(day),
                    "reference": reference,
                    "actual": actual,
                    "absolute_error": error,
                    "within_1e_6": error < 1e-6,
                }
            )
    return {
        "method": (
            "independent raw adjusted prices, membership, leave-one-out, "
            "rolling QR orthogonalization and QR stock regression"
        ),
        "checks": checks,
        "max_error": max(r["absolute_error"] for r in checks),
    }
