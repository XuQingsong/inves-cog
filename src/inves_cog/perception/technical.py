"""Price-structure technicals on adjusted daily closes (perception reference only).

Trend shape (5 states), Wilder RSI(14), and signals within the last 10
sessions. Pure functions; callers supply adjusted closes oldest -> newest.
"""

SHAPES = ("多头排列", "空头排列", "多头回调", "空头反弹", "震荡", "数据不足")


def wilder_rsi(closes, period=14):
    """Wilder-smoothed RSI of the last close, or None if history is short."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def _ma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def technicals(closes, volumes=None):
    """closes/volumes: adjusted values oldest -> newest.

    Returns {"shape", "rsi", "rsi_state", "signals"}; signals is a list of
    Chinese labels observed in the last 10 sessions.
    """
    n = len(closes)
    if n < 30:
        return {"shape": "数据不足", "rsi": wilder_rsi(closes), "rsi_state": _rsi_state(wilder_rsi(closes)), "signals": []}
    ma20, ma50, ma200 = _ma(closes, 20), _ma(closes, 50), _ma(closes, 200)
    prev_ma50 = sum(closes[-60:-10]) / 50 if n >= 60 else None
    close = closes[-1]
    if ma200 is None or prev_ma50 is None:
        shape = "数据不足"
    elif close > ma20 > ma50 > ma200 and ma50 > prev_ma50:
        shape = "多头排列"
    elif close < ma20 < ma50 < ma200 and ma50 < prev_ma50:
        shape = "空头排列"
    elif ma50 > ma200 and close < ma50:
        shape = "多头回调"
    elif ma50 < ma200 and close > ma50:
        shape = "空头反弹"
    else:
        shape = "震荡"
    rsi = wilder_rsi(closes)
    signals = []
    look = min(10, n - 1)
    for back in range(look, 0, -1):
        i = n - back
        window = closes[max(0, i - 20) : i]
        if len(window) < 5:
            continue
        if closes[i] > max(window):
            if volumes and len(volumes) > i:
                avg = sum(volumes[max(0, i - 20) : i]) / max(1, len(volumes[max(0, i - 20) : i]))
                if avg and volumes[i] >= 1.5 * avg:
                    signals.append("放量突破 20 日新高")
            else:
                signals.append("突破 20 日新高")
        if closes[i] < min(window):
            signals.append("跌破 20 日新低")
        a50 = sum(closes[max(0, i - 49) : i + 1])
        b50 = sum(closes[max(0, i - 50) : i])
        a200 = sum(closes[max(0, i - 199) : i + 1])
        b200 = sum(closes[max(0, i - 200) : i])
        if i >= 200 and i - 1 >= 199:
            if b50 / 50 < b200 / 200 <= a50 / 50:
                signals.append("金叉")
            if b50 / 50 > b200 / 200 >= a50 / 50:
                signals.append("死叉")
    return {"shape": shape, "rsi": rsi, "rsi_state": _rsi_state(rsi), "signals": signals}


def _rsi_state(rsi):
    if rsi is None:
        return "暂缺"
    if rsi >= 70:
        return "超买"
    if rsi <= 30:
        return "超卖"
    return "中性"
