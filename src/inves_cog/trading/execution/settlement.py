"""Integer-share settlement helpers; database order writes stay in trading.engine."""

from inves_cog.trading.execution.state import PARAMS, TIERS, new_position


def buy(engine, order, day, price, equity, execution_scores):
    if engine.cash <= 0:
        return None
    ticker, action = order["ticker"], order["action"]
    old = engine.positions.get(ticker)
    existed = old is not None
    tier = order["tier"]
    # Q-M4-10 / Muse aacea04 L334–355: replay only uses execution-day tier; paper uses the plan.
    if engine.mode == "replay_v18" and action in {"buy_to", "buy_watch"}:
        tier = (execution_scores.get(ticker) or {}).get("tier") or tier
    if action == "buy_swing" and old is None:
        return None
    if action == "buy_to":
        desired = order["fraction"] * TIERS[tier]["cap"] * equity
        amount = desired - (old["shares"] * price if old else 0.0)
        if order.get("half"):
            amount *= 0.5
    else:
        amount = order["value"]
    spend = min(amount, engine.cash)
    quantity = int(spend // price)
    planned_quantity = quantity
    if action == "buy_to" and tier != order["tier"]:
        planned_amount = order["fraction"] * TIERS[order["tier"]]["cap"] * equity
        planned_amount -= old["shares"] * price if old else 0.0
        planned_amount *= 0.5 if order.get("half") else 1.0
        planned_quantity = max(0, int(min(planned_amount, engine.cash) // price))
    # Q-M4-9 / Muse aacea04 L316–319, L353–367: compare pre-floor spend, then charge fee.
    if quantity <= 0 or spend < PARAMS["min_spend_fraction"] * equity:
        return None
    cost = quantity * price * PARAMS["cost_rate"]
    engine.cash -= quantity * price + cost
    if old:
        old["avg_cost"] = (old["shares"] * old["avg_cost"] + quantity * price) / (old["shares"] + quantity)
        old["shares"] += quantity
    else:
        visible = execution_scores if engine.mode == "replay_v18" else engine.scores
        version = (visible.get(ticker) or engine.scores.get(ticker) or {}).get("state_version", "")
        old = new_position(shares=quantity, price=price, tier=tier, index=engine.index, state_version=version)
        engine.positions[ticker] = old
    if action == "buy_to":
        fraction = order["fraction"] * (0.5 if order.get("half") else 1.0)
        old["filled_fraction"] = max(old["filled_fraction"], fraction)
        if not existed:
            old.update(first_fraction=order["fraction"], certainty=order.get("certainty", "medium"))
    else:
        old["swing_shares"] += quantity
        old["swing_count"] += 1
        old["last_swing_index"] = engine.index
        if old["shares"] == quantity and action == "buy_watch":
            old.update(swing_only=True, watch_cap=order.get("watch_cap", PARAMS["swing"]["watch_cap"]))
    return {
        "qty": quantity,
        "cost": cost,
        "tier": tier,
        "planned_tier": order["tier"],
        "planned_tier_only_qty": planned_quantity,
    }


def sell(engine, order, day, price):
    ticker = order["ticker"]
    old = engine.positions.get(ticker)
    if old is None:
        return None
    action = order["action"]
    quantity = (
        old["shares"]
        if action == "sell_all"
        else old["swing_shares"]
        if action == "sell_swing"
        else int(old["shares"] * order["fraction"])
    )
    if quantity <= 0:
        return None
    cost = quantity * price * PARAMS["cost_rate"]
    engine.cash += quantity * price - cost
    old["shares"] -= quantity
    if action == "sell_swing":
        # Q-M4-8 / Muse aacea04 L303–309: swing sale does not reset the core-sale cooldown.
        old.update(swing_shares=0, swing_count=0, last_swing_index=engine.index)
    else:
        old["last_sell_index"] = engine.index
        old["swing_shares"] = max(0, old["swing_shares"] - quantity)
    tier = old["tier_now"]
    if old["shares"] <= 0:
        engine.exits[ticker] = (engine.index, order.get("exit_kind", "price"))
        del engine.positions[ticker]
    return {"qty": quantity, "cost": cost, "tier": tier}
