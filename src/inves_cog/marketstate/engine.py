"""Pure daily market structure: prices and point-in-time basket metadata only."""

import numpy as np
import pandas as pd

from inves_cog.marketstate.factors import (
    effective_basket_return,
    member_tickers,
    orthogonalize,
    post_return,
    stock_factors,
)
from inves_cog.marketstate.market import five_day, market_flags
from inves_cog.marketstate.regression import fit_predict
from inves_cog.marketstate.rotation import STYLES, number, return_5d, rotation_rows


def active_baskets(baskets, day):
    l2, l3 = {}, {}
    for row in baskets:
        for member in row["members"]:
            if (member.get("effective_from") is None or str(member["effective_from"]) <= str(day)) and (
                member.get("effective_to") is None or str(day) < str(member["effective_to"])
            ):
                if row["level"] == "L2":
                    l2[member["ticker"]] = row
                elif row["level"] == "L3" and member.get("primary"):
                    l3[member["ticker"]] = row
    return l2, l3


def post_factors(returns, post, *, ticker, l2, l3, sector_etf, factors, signal_index):
    result = {"m": post.get("SPY")}
    sector = effective_basket_return(returns, l2, exclude=ticker) if l2 else returns.get(sector_etf)

    def predicted_residual(target, frame, observed, features):
        model = fit_predict(target, frame, signal_index=signal_index)
        if model["alpha"] is None or observed is None or any(v is None for v in features.values()):
            return None
        return observed - model["alpha"] - sum(model["betas"][k] * v for k, v in features.items())

    def member_post(basket):
        members = [t for t in member_tickers(basket, returns.index[signal_index]) if t != ticker]
        vals = [post.get(t) for t in members if post.get(t) is not None]
        return sum(vals) / len(vals) if vals else None

    if "s" in factors:
        observed = member_post(l2) if l2 else post.get(sector_etf)
        result["s"] = predicted_residual(sector, factors[["m"]], observed, {"m": result["m"]})
    if "t" in factors:
        theme = effective_basket_return(returns, l3, exclude=ticker)
        result["t"] = predicted_residual(theme, factors.drop(columns="t"), member_post(l3), result.copy())
    return result


def post_stock_rows(returns, post_history, *, ticker, l2, l3, sector_etf, factors, recent):
    output = []
    positions = range(max(0, len(returns) - 5), len(returns))
    for index, model in zip(positions, recent, strict=True):
        observed = {key: number(v) for key, v in post_history.iloc[index].items()}
        actual = observed.get(ticker)
        features = (
            post_factors(
                returns,
                observed,
                ticker=ticker,
                l2=l2,
                l3=l3,
                sector_etf=sector_etf,
                factors=factors,
                signal_index=index,
            )
            if actual is not None
            else {}
        )
        reason = "missing_post_price" if actual is None else model["null_reason"]
        if actual is not None and any(features.get(k) is None for k in factors.columns):
            reason = "missing_post_factor"
        residual = (
            None if reason else actual - model["alpha"] - sum(model["betas"][k] * features[k] for k in factors.columns)
        )
        output.append({"ret": actual, "resid": residual, "null_reason": reason})
    return output


def stock_rows(returns, post_history, *, ticker, l2, l3, sector_etf, day, cached_factors=None):
    factors, reasons = cached_factors or stock_factors(returns, ticker=ticker, l2=l2, l3=l3, sector_etf=sector_etf)
    target = returns[ticker]
    recent = [fit_predict(target, factors, signal_index=i) for i in range(max(0, len(returns) - 5), len(returns))]
    model = recent[-1]
    row = {
        "trade_date": day,
        "ticker": ticker,
        "session": "close",
        "ret": number(target.iloc[-1]),
        "resid": model["resid"],
        "resid_z": model["resid_z"],
        "sigma": model["sigma"],
        "beta_m": model["betas"].get("m"),
        "beta_s": model["betas"].get("s"),
        "beta_t": model["betas"].get("t"),
        "primary_basket": l3["basket_id"] if l3 else None,
        "factor_set": "+".join(factors.columns),
        "health_codes": sorted(set(reasons + model["health_codes"])),
        "null_reason": ";".join(reasons + ([model["null_reason"]] if model["null_reason"] else [])) or None,
        **five_day([m["resid"] for m in recent], model["sigma"], return_5d(target)),
    }
    post_rows = post_stock_rows(
        returns,
        post_history,
        ticker=ticker,
        l2=l2,
        l3=l3,
        sector_etf=sector_etf,
        factors=factors,
        recent=recent,
    )
    current_post = post_rows[-1]
    post_total = return_5d(post_history[ticker]) if ticker in post_history else None
    reason = current_post["null_reason"]
    residual = current_post["resid"]
    after = {
        **row,
        "session": "post",
        "ret": current_post["ret"],
        "resid": residual,
        "resid_z": residual / model["sigma"] if residual is not None and model["sigma"] else None,
        **five_day([r["resid"] for r in post_rows], model["sigma"], post_total),
        "health_codes": sorted(set(reasons + ([reason] if reason else []))),
        "null_reason": ";".join(reasons + ([reason] if reason else [])) or None,
    }
    proof = {
        "ticker": ticker,
        "trade_date": str(day),
        "y": target.tolist(),
        "factors": {key: factors[key].tolist() for key in factors},
        "model": model,
        "dates": [str(d) for d in returns.index],
    }
    return [row, after], proof


def basket_models(returns, post_history, baskets, stock_daily, *, day):
    outputs, themes = [], {}
    market = pd.DataFrame({"m": returns["SPY"]})
    for basket in baskets:
        own = effective_basket_return(returns, basket)
        factors = market.copy()
        basis = basket["factor_basis"]
        if basket["level"] == "L3":
            if basis["kind"] == "l2":
                parent = next(b for b in baskets if b["level"] == "L2" and b["name"] == basis["sector"])
                sector = effective_basket_return(returns, parent)
            else:
                sector = returns[[t for t in basis["tickers"] if t in returns]].mean(axis=1)
            if sector.notna().any():
                factors["s"] = orthogonalize(sector, market)
            themes[basket["basket_id"]] = own
        model = fit_predict(own, factors, signal_index=len(returns) - 1)
        members = set(member_tickers(basket, day))
        residuals = [
            r["resid"]
            for r in stock_daily
            if r["session"] == "close" and r["ticker"] in members and r["resid"] is not None
        ]
        residual = model["resid"]
        same = (
            sum(np.sign(value) == np.sign(residual) for value in residuals) / len(residuals)
            if residuals and residual is not None
            else None
        )
        outputs.append(
            {
                "trade_date": day,
                "basket_id": basket["basket_id"],
                "session": "close",
                "ret_ew": number(own.iloc[-1]),
                "resid": residual,
                "resid_z": model["resid_z"],
                "same_sign_share": same,
                "member_resid_std": float(np.std(residuals, ddof=1)) if len(residuals) >= 2 else None,
                "health_codes": model["health_codes"],
                "null_reason": model["null_reason"],
            }
        )
        own_post = effective_basket_return(post_history, basket)
        observed = {"m": number(post_history["SPY"].iloc[-1])}
        if "s" in factors:
            sector_post = (
                effective_basket_return(post_history, parent)
                if basis["kind"] == "l2"
                else post_history[[t for t in basis["tickers"] if t in post_history]].mean(axis=1)
            )
            sector_model = fit_predict(sector, market, signal_index=len(returns) - 1)
            value = number(sector_post.iloc[-1])
            observed["s"] = (
                value - sector_model["alpha"] - sector_model["betas"]["m"] * observed["m"]
                if (value is not None and sector_model["alpha"] is not None and observed["m"] is not None)
                else None
            )
        actual = number(own_post.iloc[-1])
        reason = "missing_post_price" if actual is None else model["null_reason"]
        if actual is not None and any(v is None for v in observed.values()):
            reason = "missing_post_factor"
        residual = None if reason else actual - model["alpha"] - sum(model["betas"][k] * v for k, v in observed.items())
        residuals = [
            r["resid"]
            for r in stock_daily
            if r["session"] == "post" and r["ticker"] in members and r["resid"] is not None
        ]
        outputs.append(
            {
                **outputs[-1],
                "session": "post",
                "ret_ew": actual,
                "resid": residual,
                "resid_z": residual / model["sigma"] if residual is not None and model["sigma"] else None,
                "same_sign_share": sum(np.sign(v) == np.sign(residual) for v in residuals) / len(residuals)
                if residuals and residual is not None
                else None,
                "member_resid_std": float(np.std(residuals, ddof=1)) if len(residuals) >= 2 else None,
                "health_codes": [reason] if reason else [],
                "null_reason": reason,
            }
        )
    return outputs, themes


def market_row(returns, macro, tickers, rotation, *, day):
    vix = {}
    for row in macro:
        key = (row["series_id"], row["observation_date"])
        if row["observation_date"] <= day and row["value"] is not None:
            vix[key] = row["value"]

    def value(d):
        return vix.get(("VIX_CBOE", d), vix.get(("VIXCLS", d)))

    current, term = value(day), vix.get(("VIX3M_CBOE", day))
    prior = [value(d) for d in returns.index[-253:-1]]
    percentile = (
        sum(x <= current for x in prior) / 252 * 100
        if len(prior) == 252 and all(x is not None for x in prior) and current is not None
        else None
    )
    compounded = (1 + returns["SPY"]).cumprod()
    drawdown = (
        number((compounded.iloc[-1] / compounded.iloc[-252:].max() - 1) * 100) if len(compounded) >= 252 else None
    )
    changes = [return_5d(returns[t]) for t in set(tickers) if t in returns]
    valid = [x for x in changes if x is not None]
    breadth = sum(x < 0 for x in valid) / len(valid) * 100 if valid else None
    spy = return_5d(returns["SPY"])
    spy = spy * 100 if spy is not None else None
    inverted = term < current if term is not None and current is not None else None
    flags = market_flags(
        spy_5d_pct=spy,
        vix_pctile_252=percentile,
        down_share_5d_pct=breadth,
        vix_term_inverted=inverted,
        spy_drawdown_252_pct=drawdown,
    )
    sectors = [r["z"] for r in rotation if r["group_kind"] == "sector" and r["z"] is not None]
    styles = {
        key: next((r["z"] for r in rotation if r["group_kind"] == "style" and r["group_id"] == key), None)
        for key in STYLES
    }
    return {
        "trade_date": day,
        "spy_5d_pct": spy,
        "vix": current,
        "vix_pctile_252": percentile,
        "down_share_5d_pct": breadth,
        "vix3m": term,
        "vix_term_inverted": inverted,
        "spy_drawdown_252_pct": drawdown,
        "sector_spread_z": max(sectors) - min(sectors) if len(sectors) >= 2 else None,
        "style_spread_z": styles,
        **flags,
    }


def calculate(bars, baskets, macro, *, day, tickers, sic_etfs):
    data = pd.DataFrame(bars)
    data = data[data["trade_date"] <= day]
    adjusted = (
        data.assign(adjusted=data["close"] * data["adj_factor"])
        .pivot(index="trade_date", columns="ticker", values="adjusted")
        .sort_index()
    )
    returns = adjusted.pct_change(fill_method=None).iloc[-421:]
    if day not in returns.index:
        raise ValueError("Requested signal day has no price row; cannot relabel the latest available day")
    data["post_ret"] = [post_return(r["close"], r["post_close"]) for r in data.to_dict("records")]
    post_history = data.pivot(index="trade_date", columns="ticker", values="post_ret").reindex(returns.index)
    l2, l3 = active_baskets(baskets, day)
    daily, proofs, cache = [], [], {}
    for ticker in sorted(set(tickers)):
        if ticker not in returns:
            returns[ticker] = np.nan
        sector = sic_etfs.get(ticker)
        cached = None
        if ticker not in l2:
            if sector not in cache:
                cache[sector] = stock_factors(returns, ticker=ticker, sector_etf=sector)
            cached = cache[sector]
        rows, proof = stock_rows(
            returns,
            post_history,
            ticker=ticker,
            l2=l2.get(ticker),
            l3=l3.get(ticker),
            sector_etf=sector,
            day=day,
            cached_factors=cached,
        )
        daily.extend(rows)
        if ticker in {"WDC", "AMD", "ANET"}:
            proofs.append(proof)
    basket_rows, themes = basket_models(returns, post_history, baskets, daily, day=day)
    rotation = rotation_rows(returns, themes, day=day)
    post_themes = {b["basket_id"]: effective_basket_return(post_history, b) for b in baskets if b["level"] == "L3"}
    rotation.extend(
        rotation_rows(returns, themes, day=day, session="post", post_returns=post_history, post_baskets=post_themes)
    )
    market = market_row(returns, macro, tickers, [r for r in rotation if r["session"] == "close"], day=day)
    return {"daily": daily, "baskets": basket_rows, "rotation": rotation, "market": market, "proofs": proofs}
