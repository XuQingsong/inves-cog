"""Portfolio gates, with injected observations rather than wall-clock data access."""

from decimal import Decimal

import numpy as np

from inves_cog.trading.execution.state import PARAMS

P = PARAMS["risk"]


def _versus(equity, peak, percent):
    """Sign of the drawdown against percent, using the money amounts exactly."""
    left = Decimal(str(equity)) * 100
    right = Decimal(str(peak)) * (100 + int(percent))
    return (left > right) - (left < right)


def vix_panic(current, history):
    # Muse aacea04 paper_trade_v18_full30.py L157–163: inclusive window, min120, linear q90.
    values = [float(x) for x in history[-P["vix_window"] :] if x is not None and np.isfinite(x)]
    if current is None:
        return False, {"status": "missing", "threshold": None}
    if len(values) < P["vix_min_observations"]:
        return False, {"status": "insufficient_history", "threshold": None}
    threshold = float(np.quantile(values, P["vix_quantile"], method="linear"))
    return current >= threshold, {"status": "ok", "threshold": threshold}


def update_risk(engine, equity, spy_returns, panic):
    engine.peak_equity = max(engine.peak_equity, equity)
    triggered = _versus(equity, engine.peak_equity, P["dd8_trigger"]) <= 0
    released = _versus(equity, engine.peak_equity, P["dd8_release"]) > 0
    deep = _versus(equity, engine.peak_equity, P["dd12_trigger"]) <= 0
    held = _versus(equity, engine.peak_equity, P["dd12_release"]) < 0
    intents = []
    # Muse aacea04 L402–425: portfolio queue precedes stock queue; keep both when triggered.
    if triggered and not engine.dd8 and not panic:
        engine.dd8 = True
        intents += [
            (ticker, "M-62", P["dd8_sell_fraction"], "回撤刹车减仓")
            for ticker, pos in engine.positions.items()
            if pos["tier_now"] == "attack"
        ]
    if released:
        engine.dd8 = False
    engine.dd12 = deep or (engine.dd12 and held)
    trigger = any(
        value is not None and value <= P[key] for value, key in zip(spy_returns, ("spy_ret1", "spy_ret5"), strict=True)
    )
    if trigger and engine.index - engine.last_swan > P["swan_interval"]:
        engine.last_swan = engine.index
        engine.swan_until = engine.index + P["swan_days"]
        if not panic:
            intents += [
                (ticker, "M-61", P["swan_sell_fraction"], "黑天鹅减仓")
                for ticker, pos in engine.positions.items()
                if pos["tier_now"] == "attack"
            ]
    return intents
