"""Opt-in policies for the in-memory backtest engine."""

from bisect import bisect_left

from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.sells import death
from inves_cog.trading.execution.state import PARAMS, TIERS
from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY, EXCLUDED

FUNDAMENTAL_RED_LINES = {"现金流为负且营收下滑", "营收与EPS同时明显下滑"}


class BacktestEngine(ExecutionEngine):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.price_exit_recovery = {}

    def decide(self, day, scores, **kwargs):
        self._stages_before_decision = {ticker: position["stage"] for ticker, position in self.positions.items()}
        if self.flags.get("watch_promote"):
            self.promote_watch_positions(scores, kwargs["prices"])
        if self.flags.get("reentry_after_price_exit"):
            scores = self.apply_reentry(scores)
        return super().decide(day, scores, **kwargs)

    def apply_reentry(self, scores):
        adjusted = dict(scores)
        for ticker, recovery in self.price_exit_recovery.items():
            score = dict(scores.get(ticker) or {})
            above = (score.get("tech", {}).get("price_vs_ma200") or 0) > 0
            recovery["closes"] = recovery["closes"] + 1 if above else 0
            if allow_price_reentry(score, recovery["position"], recovery["closes"]):
                adjusted[ticker] = score
        return adjusted

    def promote_watch_positions(self, scores, prices):
        equity = self.equity(prices)
        if equity is None or equity <= 0:
            return
        for ticker, position in self.positions.items():
            score = scores.get(ticker) or {}
            tier = score.get("tier")
            if not position.get("swing_only") or not score.get("gate_pass") or tier not in TIERS:
                continue
            fraction = min(
                PARAMS["swing"]["core_conversion_ceiling"],
                position["shares"] * prices[ticker] / (TIERS[tier]["cap"] * equity),
            )
            position.update(
                swing_only=False,
                swing_shares=0,
                swing_count=0,
                tier_now=tier,
                tier_entry=tier,
                filled_fraction=fraction,
                first_fraction=fraction,
            )
            self.flags_counts["watch_promoted"] = self.flags_counts.get("watch_promoted", 0) + 1

    def fill(self, day, opening, execution_scores=None, **kwargs):
        previously_held = dict(self.positions)
        fills = super().fill(day, opening, execution_scores, **kwargs)
        if self.flags.get("buy_consistency"):
            for fill in fills:
                position = self.positions.get(fill["ticker"])
                if fill["side"] == "buy" and position is not None:
                    position["last_buy_index"] = self.index
        if self.flags.get("breakdown_confirm"):
            for fill in fills:
                ticker = fill["ticker"]
                if fill.get("rule_ids") == ["M-55"] and ticker in self.positions:
                    self.positions[ticker]["breakdown_half_done"] = True
        if self.flags.get("reentry_after_price_exit"):
            for fill in fills:
                ticker = fill["ticker"]
                if fill["side"] == "buy":
                    self.price_exit_recovery.pop(ticker, None)
                elif ticker not in self.positions and ticker in previously_held:
                    self.price_exit_recovery.pop(ticker, None)
                    price_rules = {"M-51", "M-52", "M-55", "M-64"}
                    if fill.get("exit_kind") == "price" or price_rules.intersection(fill["rule_ids"]):
                        previous = previously_held[ticker]
                        score = self.scores.get(ticker) or {}
                        if score.get("books") and not fundamentals_weakened(previous, score):
                            self.price_exit_recovery[ticker] = {"position": previous, "closes": 0}
        if self.flags.get("breakdown_confirm") or self.flags.get("reentry_after_price_exit"):
            for ticker in self.positions.keys() - previously_held.keys():
                score = self.scores.get(ticker) or {}
                self.positions[ticker]["entry_books"] = dict(score.get("books") or {})
        return fills

    def restore_sell_stage(self, ticker, position):
        old_stage = getattr(self, "_stages_before_decision", {}).get(ticker)
        if old_stage is not None:
            position["stage"] = old_stage

    def confirm_breakdown(self, ticker, values):
        position = self.positions[ticker]
        score = self.scores[ticker]
        if fundamentals_weakened(position, score) or (score.get("fear_level") or 0) >= 3:
            return values
        if score.get("breakdown_below_days", 0) < 2 and (score.get("breakdown_depth_atr") or 0) <= 1:
            self.restore_sell_stage(ticker, position)
            self.flags_counts["breakdown_delayed"] = self.flags_counts.get("breakdown_delayed", 0) + 1
            return None
        if not position.get("breakdown_half_done"):
            return {**values, "fraction": 0.5, "breakdown_first_half": True}
        return values

    def queue(self, ticker, action, rule, label, **values):
        score = self.scores.get(ticker) or {}
        if action.startswith("buy") and score.get("overval_veto"):
            return None
        if action == "buy_to" and score.get("price_reentry"):
            values["price_reentry"] = True
        if self.flags.get("buy_consistency"):
            position = self.positions.get(ticker)
            score = self.scores.get(ticker)
            if action.startswith("buy") and score:
                tier = values.get("tier") or (position or {}).get("tier_now") or score.get("tier")
                if tier and death({"tier_now": tier}, score):
                    self.flags_counts["buy_consistency_blocked"] = (
                        self.flags_counts.get("buy_consistency_blocked", 0) + 1
                    )
                    return None
            if action.startswith("sell") and position and self.index - position.get("last_buy_index", position["entry_index"]) < 10:
                red_exit = rule == "M-50" and FUNDAMENTAL_RED_LINES.intersection((score or {}).get("red_lines", []))
                if rule != "M-51" and not red_exit:
                    if rule in {"M-55", "M-56"}:
                        self.restore_sell_stage(ticker, position)
                    self.flags_counts["minimum_hold_blocked"] = self.flags_counts.get("minimum_hold_blocked", 0) + 1
                    return None
        if rule == "M-55" and self.flags.get("breakdown_confirm"):
            values = self.confirm_breakdown(ticker, values)
            if values is None:
                return None
        return super().queue(ticker, action, rule, label, **values)


def apply_ceiling_gate(score, panel, fridays, ticker, day):
    """Replace the valuation gate using the latest strictly earlier Friday."""
    index = bisect_left(fridays, day) - 1
    if index < 0 or score.get("tier") not in ENTRY:
        return False
    week = panel[fridays[index]]
    values = week["m8"]
    if ticker not in values:
        return False
    if "ceiling_gate_cutoff" not in week:
        ranked = sorted(values.values())
        # Include ties at the boundary in the overextended group.
        week["ceiling_gate_cutoff"] = ranked[len(ranked) - (len(ranked) + 4) // 5]
    score["ceiling_gate_overextended"] = values[ticker] >= week["ceiling_gate_cutoff"]
    gate = not score["ceiling_gate_overextended"] and nonvaluation_gate(score)
    score["gate_pass"] = gate
    score["entry_pass"] = gate and bool(score.get("m32_ok")) and not EXCLUDED.intersection(score.get("red_lines", ()))
    return True


def nonvaluation_gate(score):
    return all(
        score["books"].get(key) is not None and score["books"][key] >= threshold
        for key, threshold in zip(BOOK_KEYS, ENTRY[score["tier"]], strict=True)
        if key != "valuation"
    )


def allow_price_reentry(score, previous, closes):
    if (
        closes < 3
        or score.get("tier") not in ENTRY
        or score.get("entry_pass")
        or score.get("overval_veto")
        or score.get("ceiling_gate_overextended")
        or score.get("tradable") is False
        or not score.get("m32_ok")
        or EXCLUDED.intersection(score.get("red_lines", ()))
        or not nonvaluation_gate(score)
        or fundamentals_weakened(previous, score)
        or death({"tier_now": score["tier"]}, score)
    ):
        return False
    score.update(entry_pass=True, price_reentry=True)
    return True


def fundamentals_weakened(position, score):
    if (FUNDAMENTAL_RED_LINES | {"流动性偏紧"}).intersection(score.get("red_lines", ())):
        return True
    thresholds = PARAMS["sell"]
    tier = position["tier_now"]
    entry = position.get("entry_books", {})
    for book in ("quality", "growth"):
        value = score["books"].get(book)
        if value is None:
            continue
        if value <= thresholds[f"death_{book}"][tier] + 5:
            return True
        original = entry.get(book)
        if original is not None and original - value >= 10:
            return True
    return False


def breakdown_depth_atr(rows, close, deviation):
    """Distance below MA200 in units of 14-session mean true range."""
    if len(rows) != 15 or close is None or deviation is None or not -100 < deviation < 0:
        return None
    ranges = []
    for previous, current in zip(rows[:-1], rows[1:], strict=True):
        high, low, prior = current.get("high"), current.get("low"), previous.get("close")
        if None in (high, low, prior):
            return None
        ranges.append(max(high - low, abs(high - prior), abs(low - prior)))
    atr = sum(ranges) / 14
    return (close / (1 + deviation / 100) - close) / atr if atr > 0 else None
