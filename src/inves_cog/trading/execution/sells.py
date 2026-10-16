"""Ordered, short-circuit stock exits; portfolio risk is separately queued."""

from inves_cog.trading.execution.state import PARAMS, above, below, clamp

P, W = PARAMS["sell"], PARAMS["swing"]


def decision(rule, action, label, **values):
    return {"rule_ids": [rule], "reason_zh": rule + " " + label, "action": action, "label": label, **values}


def death(position, score):
    tier = position["tier_now"]
    books = score["books"]
    red = {"现金流为负且营收下滑", "营收与EPS同时明显下滑"}
    return (
        bool(red.intersection(score.get("red_lines", [])))
        or below(books.get("quality"), P["death_quality"][tier])
        or below(books.get("growth"), P["death_growth"][tier])
        or score.get("fund_bad", False)
        or tier == "attack"
        and (below(score.get("rev_growth"), 0) or not score.get("runway_ok", True))
    )


def swing_exit(position, tech):
    vol, dev, price = (tech.get(k) for k in ("vol20", "dev50", "price"))
    if position.get("swing_only"):
        if vol is not None and dev is not None and dev >= clamp(vol, W["take_profit"]):
            return decision("M-52", "sell_swing", "波段卖出")
        if price is not None and price <= W["stop_fraction"] * position["avg_cost"]:
            return decision("M-52", "sell_all", "全部卖出", exit_kind="price")
        return None
    bounds = W["attack_take_profit"] if position["tier_now"] == "attack" else W["take_profit"]
    if position["swing_shares"] > 0 and vol is not None and dev is not None and dev >= clamp(vol, bounds):
        return decision("M-53", "sell_swing", "波段卖出")
    return None


def trend_exit(position, score, index, panic):
    tier, stage = position["tier_now"], position["stage"]
    books, tech = score["books"], score["tech"]
    broken = score.get("consec_below200", 0) >= P["below_days"][tier]
    if tier == "normal":
        broken |= "趋势破位" in score.get("red_lines", []) or score.get("consec_tim35", 0) >= P["normal_timing_days"]
    if tier == "attack":
        broken |= score.get("consec_tim30", 0) >= P["attack_timing_days"]
    alert = (
        tier == "normal"
        and score.get("state_version", "") > position["entry_state"]
        and (
            below(books.get("quality"), P["normal_alert_quality"])
            or below(books.get("growth"), P["normal_alert_growth"])
        )
        and below(tech.get("dev50"), 0)
    )
    if not panic and broken and stage < 2 and index - position["entry_index"] >= P["minimum_age"]:
        position["stage"] = 2
        return decision("M-55", "sell_frac", "破位减仓", fraction=P["broken_fraction"][tier])
    if not panic and alert and stage == 0:
        position.update(stage=1, clear_streak=0)
        return decision("M-56", "sell_frac", "警戒减仓", fraction=P["normal_alert_fraction"])
    if stage > 0:
        clear = not alert and above(tech.get("price_vs_ma200"), 0) and score.get("entry_pass")
        position["clear_streak"] = position.get("clear_streak", 0) + 1 if clear else 0
        if position["clear_streak"] >= P["clear_days"][tier]:
            position.update(stage=0, clear_streak=0)
    return None


def sell_signal(position, score, *, index, panic):
    # Muse aacea04 L439–512: M50→51→52→53→54→55→56; M57 recovers state only.
    tier, tech = position["tier_now"], score["tech"]
    price = tech.get("price")
    if price is not None:
        position["peak_price"] = max(position["peak_price"], price)
    if death(position, score):
        return decision("M-50", "sell_all", "全部卖出", exit_kind="fundamental")
    if (
        tier == "attack"
        and price is not None
        and price <= P["disaster_peak_fraction"] * position["peak_price"]
        and below(tech.get("price_vs_ma200"), 0)
    ):
        return decision("M-51", "sell_all", "全部卖出", exit_kind="price")
    swing = swing_exit(position, tech)
    if swing or position.get("swing_only"):
        return swing
    if (
        tier == "attack"
        and price is not None
        and price >= P["double_price"] * position["avg_cost"]
        and (below(tech.get("dev50"), P["double_dev50"]) or below(score["books"].get("timing"), P["double_timing"]))
        and index - position["last_sell_index"] >= P["profit_interval"]
        and position["stage"] == 0
    ):
        return decision("M-54", "sell_frac", "分批止盈", fraction=P["profit_fraction"])
    return trend_exit(position, score, index, panic)
