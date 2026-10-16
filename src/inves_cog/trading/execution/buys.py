"""Independent allocation passes: core adds, swings, watch positions, then entries."""

from datetime import timedelta

from inves_cog.trading.execution.state import PARAMS, RULE_A, TIERS, above, clamp
from inves_cog.trading.scoring.rules import ENTRY

P, W, A = PARAMS["opening"], PARAMS["swing"], PARAMS["adds"]


def limit(engine, tier, market_values, equity):
    settings = TIERS[tier]
    ceiling = settings["budget"] * settings["budget_buffer"] * equity
    if tier != "attack" and (equity - engine.cash) / equity < PARAMS["budget"]["borrow_below"]:
        attack = TIERS["attack"]
        spare = max(0.0, attack["budget"] * attack["budget_buffer"] * equity - market_values["attack"])
        ceiling += PARAMS["budget"]["borrow_fraction"] * spare
    return ceiling


def first_fraction(tier, certainty, *, reentry, invested, insider_multiplier=1.0):
    delta, bound = P[certainty]
    value = TIERS[tier]["first_lot"] + delta
    value = max(bound, value) if certainty == "low" else min(bound, value)
    # Muse aacea04 L676–684: reentry rounds to 3 decimals before low-investment and insider boosts.
    if reentry:
        value = round(value * P["reentry_multiplier"], 3)
    if invested < P["low_investment"] and certainty != "low":
        value = min(P["max_fraction"], value + P["low_investment_add"])
    if not reentry and insider_multiplier > 1:
        value = min(P["max_fraction"], value * insider_multiplier)
    return value


def insider_boost(events, day):
    lower = day - timedelta(days=P["insider_days"])
    visible = [row for row in events if row.get("code") == "P" and lower <= row["filed"] <= day]
    return (
        P["officer_multiplier"] if any(r.get("officer") for r in visible) else P["other_multiplier"] if visible else 1.0
    )


def add_target(position, score, index, invested):
    first = position["first_fraction"]
    held = index - position["entry_index"]
    required = A["high_days"] if position["certainty"] == "high" or invested < A["low_investment"] else A["other_days"]
    if position["filled_fraction"] < first + A["increment"] - A["fraction_tolerance"]:
        tech = score["tech"]
        pullback = tech.get("dev50") is not None and abs(tech["dev50"]) <= A["pullback_dev50"]
        pullback = pullback and above(tech.get("price_vs_ma200"), 0)
        if pullback or held >= required and score["consec_pass"] >= required:
            return min(A["first_ceiling"], first + A["increment"]), "确认加仓"
    elif position["filled_fraction"] < 1 - A["fraction_tolerance"]:
        if (
            score["state_version"] > position["entry_state"]
            or held >= A["full_held_days"]
            and score["consec_pass"] >= A["full_pass_days"]
        ):
            return 1.0, "确认补满"
    return None


def core_adds(engine, scores, values, equity, sold):
    for ticker, position in engine.positions.items():
        score = scores.get(ticker)
        if not score or not score.get("entry_pass") or score["tier"] is None:
            continue
        tier = score["tier"]
        if position["swing_only"]:
            position.update(
                swing_only=False,
                entry_index=engine.index,
                filled_fraction=min(
                    W["core_conversion_ceiling"],
                    position["shares"] * score["tech"]["price"] / (TIERS[tier]["cap"] * equity),
                ),
            )
        if ticker in sold or "短线过热" in score["red_lines"] or score.get("fund_bad"):
            continue
        if engine.index - position["last_sell_index"] < PARAMS["cooldown_days"]:
            engine.skip(ticker, "M-58", "N7", "核心卖出后冷却期，暂不加仓")
            continue
        if engine.dd12 and tier != "defense" or limit(engine, tier, values, equity) <= values[tier]:
            engine.skip(ticker, "M-40", "N7", "组合闸门或层额度不足，暂不加仓")
            continue
        target = add_target(position, score, engine.index, (equity - engine.cash) / equity)
        if target:
            engine.queue(
                ticker,
                "buy_to",
                "M-40",
                target[1],
                tier=tier,
                fraction=target[0],
                certainty=position["certainty"],
                half=above(score["tech"].get("dev50"), P["overheat_dev50"]),
            )


def in_dip(score):
    tech = score["tech"]
    if any(tech.get(k) is None for k in ("vol20", "dev50", "drawdown252")):
        return False
    return tech["drawdown252"] <= -clamp(tech["vol20"], W["dip_drawdown"]) and tech["dev50"] <= -clamp(
        tech["vol20"], W["dip_dev50"]
    )


def core_swings(engine, scores, values, equity, sold):
    for ticker, position in engine.positions.items():
        score = scores.get(ticker)
        if not score or score.get("tier") not in TIERS or ticker in sold or score.get("fund_bad"):
            continue
        if not score.get("hold_ok") or position["stage"] > 0 or position["swing_count"] >= W["max_lots"]:
            continue
        if engine.index - position["last_swing_index"] < W["interval"] or engine.dd12 and score["tier"] != "defense":
            continue
        if not in_dip(score) or not above(score["tech"].get("price_vs_ma200"), W["core_ma200_floor"]):
            continue
        tier = score["tier"]
        value = W["core_fraction"] * TIERS[tier]["cap"] * equity
        if position["shares"] * score["tech"]["price"] + value <= TIERS[tier]["cap"] * equity and values[
            tier
        ] + value <= limit(engine, tier, values, equity):
            engine.queue(ticker, "buy_swing", "M-60", "波段买入", tier=tier, value=value)


def watch_eligible(score):
    tier = score.get("tier")
    if tier not in TIERS or score.get("fund_bad") or score["hold_score"] < W["watch_hold_min"]:
        return False
    if tier == "attack" and (
        score["hold_score"] < W["attack_hold_min"]
        or score["tech"]["vol20"] > W["attack_vol_ceiling"]
        or not score["runway_ok"]
    ):
        return False
    acceleration = score.get("rev_accel_pp")
    return (acceleration is None or acceleration >= W["accel_floor"]) and in_dip(score)


def stabilized(engine, ticker, score):
    history = engine.history.get(ticker, [])
    if len(history) < W["history_min"]:
        return False
    price = score["tech"]["price"]
    if (price / history[-6] - 1) * 100 < W["ret5_floor"] or price < min(history[-10:]) * W["rebound_fraction"]:
        return False
    if score["tech"]["drawdown252"] > W["deep_drawdown"]:
        return True
    previous = engine.watch_first.get(ticker)
    if (
        previous is None
        or engine.index - previous[0] > W["confirm_max"]
        or price < previous[1] * W["confirm_price_fraction"]
    ):
        engine.watch_first[ticker] = (engine.index, price)
        return False
    if engine.index - previous[0] < W["confirm_min"]:
        return False
    del engine.watch_first[ticker]
    return True


def watch_buys(engine, scores, values, equity):
    count = sum(p["swing_only"] for p in engine.positions.values())
    for ticker, score in scores.items():
        # Muse aacea04 L587–605: legacy watch buys use holding qualification, even when
        # M07 has cleared the entry books. Keep fixed/paper health gates; frozen replay
        # is restricted to its approved US universe and reproduces the original branch.
        legacy_watch = engine.mode == "replay_v18" and ticker in PARAMS["replay_tickers"]
        if (
            ticker in engine.positions
            or (not score.get("tradable", True) and not legacy_watch)
            or not watch_eligible(score)
        ):
            continue
        if (
            count >= W["watch_slots"]
            or engine.index - engine.exits.get(ticker, (-100, None))[0] < PARAMS["cooldown_days"]
        ):
            continue
        tier = score["tier"]
        if engine.dd12 and tier != "defense" or not stabilized(engine, ticker, score):
            continue
        attack, deep = tier == "attack", score["tech"]["price_vs_ma200"] < W["deep_ma200"]
        fraction = (
            W["attack_deep_fraction" if deep else "attack_fraction"]
            if attack
            else W["watch_deep_fraction" if deep else "watch_fraction"]
        )
        value = fraction * equity
        if values[tier] + value <= limit(engine, tier, values, equity):
            engine.queue(
                ticker,
                "buy_watch",
                "M-60",
                "观察波段买入",
                tier=tier,
                value=value,
                watch_cap=W["attack_cap"] if attack else W["watch_cap"],
            )
            count += 1
    for ticker, position in engine.positions.items():
        score = scores.get(ticker)
        if not score or not position["swing_only"] or position["swing_count"] >= W["max_lots"]:
            continue
        sold = any(o["ticker"] == ticker and o["action"].startswith("sell") for o in engine.pending)
        if (
            sold
            or score.get("fund_bad")
            or engine.index - position["last_swing_index"] < W["second_interval"]
            or not above(score["tech"].get("dev50"), -1e-12)
        ):
            continue
        tier = score["tier"]
        value = position["watch_cap"] * equity - position["shares"] * score["tech"]["price"]
        if value > PARAMS["min_spend_fraction"] * equity and values[tier] + value <= limit(
            engine, tier, values, equity
        ):
            engine.queue(ticker, "buy_watch", "M-60", "观察波段加仓", tier=tier, value=value)


def entries(engine, scores, values, equity):
    candidates = []
    existing = set(engine.positions) | {o["ticker"] for o in engine.pending if o["action"] == "buy_to"}
    for ticker, score in scores.items():
        if ticker in existing or not score.get("tradable", True) or score.get("tier") not in TIERS:
            continue
        if score.get("entry_pass") and "短线过热" in score["red_lines"]:
            engine.skip(ticker, "M-18", "N4", "短线过热，不追高")
            continue
        last_index, last_kind = engine.exits.get(ticker, (-100, None))
        if engine.index - last_index < PARAMS["cooldown_days"]:
            if score.get("entry_pass"):
                engine.skip(ticker, "M-58", "N7", "核心卖出后冷却期，暂不开仓")
            continue
        if (
            score.get("entry_pass")
            and "短线过热" not in score["red_lines"]
            and score["hold_score"] >= PARAMS["entry_hold_min"]
        ):
            candidates.append((False, score.get("rank_score") or 0, ticker))
        elif (
            last_kind == "price"
            and score.get("hold_ok")
            and score["tier"] in {"normal", "attack"}
            and above(score["tech"].get("dev50"), 0)
            and (score["books"].get("timing") or 0) >= 50
            and (score["books"].get("valuation") or 0) >= ENTRY[score["tier"]][2] - 10
        ):
            candidates.append((True, (score.get("rank_score") or 0) - 3, ticker))
    # Muse aacea04 L649–671: sort each candidate source separately by (rank,ticker), then attack first.
    candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)
    candidates.sort(key=lambda c: c[0])
    candidates.sort(key=lambda c: scores[c[2]]["tier"] != "attack")
    counts = {tier: sum(p["tier_now"] == tier for p in engine.positions.values()) for tier in TIERS}
    planned = dict(values)
    for reentry, _, ticker in candidates:
        score, tier = scores[ticker], scores[ticker]["tier"]
        slots = sum(o["action"] == "buy_to" for o in engine.pending) + len(engine.positions)
        constrained = counts[tier] >= TIERS[tier]["max_positions"] or slots >= RULE_A["max_positions"]
        constrained |= engine.dd12 and tier != "defense"
        constrained |= tier == "defense" and not reentry and score["hold_score"] < PARAMS["defensive_hold_min"]
        if constrained:
            engine.skip(ticker, "M-34", "N7", "组合只数或闸门约束，暂不开仓")
            continue
        fraction = first_fraction(
            tier,
            score["certainty"],
            reentry=reentry,
            invested=(equity - engine.cash) / equity,
            insider_multiplier=insider_boost(engine.insiders.get(ticker, []), engine.signal_date),
        )
        notional = fraction * TIERS[tier]["cap"] * equity
        if planned[tier] + notional > limit(engine, tier, planned, equity):
            engine.skip(ticker, "M-35", "N7", "层买入额度不足，暂不开仓")
            continue
        engine.queue(
            ticker,
            "buy_to",
            "M-34",
            "回补买入" if reentry else "试仓买入",
            tier=tier,
            fraction=fraction,
            certainty=score["certainty"],
            half=above(score["tech"].get("dev50"), P["overheat_dev50"]),
            rule_ids=["M-34", "M-35", "M-36", "M-37"],
        )
        planned[tier] += notional
        counts[tier] += 1
