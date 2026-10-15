"""Split-adjusted technicals, with no implicit forward filling or wall clock."""

import math

import pandas as pd


def technical_series(bars):
    frame = pd.DataFrame(bars).copy().sort_values("trade_date").set_index("trade_date")
    if frame.index.has_duplicates:
        raise ValueError("Duplicate daily bars")
    factor = frame["adj_factor"] if "adj_factor" in frame else 1.0
    close, opening, volume = frame["close"] * factor, frame["open"] * factor, frame["volume"]
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    changes = close.diff()
    gain = changes.where(changes > 0, 0).rolling(14).mean()
    loss = (-changes.where(changes < 0, 0)).rolling(14).mean()
    returns = close.pct_change(fill_method=None)
    # Source contract: daily_tech L86–105; simple RSI rolling means, not Wilder EMA.
    output = pd.DataFrame(
        {
            "price": close,
            "open": opening,
            "price_vs_ma200": (close / ma200 - 1) * 100,
            "ma50_vs_ma200": (ma50 / ma200 - 1) * 100,
            "ma200_slope20": (ma200 / ma200.shift(20) - 1) * 100,
            "mom3": (close / close.shift(63) - 1) * 100,
            "mom6": (close / close.shift(126) - 1) * 100,
            "rsi": 100 - 100 / (1 + gain / loss),
            "dev50": (close / ma50 - 1) * 100,
            "vol_ratio": volume.rolling(20).mean() / volume.rolling(60).mean(),
            "up_share": volume.where(close >= opening, 0).rolling(60).sum() / volume.rolling(60).sum() * 100,
            "vol20": returns.rolling(20).std(ddof=1) * math.sqrt(252) * 100,
            "vol60": returns.rolling(60).std(ddof=1) * math.sqrt(252) * 100,
            "drawdown252": (close / close.rolling(252).max() - 1) * 100,
        }
    )
    return output.replace([float("inf"), -float("inf")], float("nan"))
