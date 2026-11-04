"""Opt-in policies for the in-memory backtest engine."""

from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.sells import death
from inves_cog.trading.execution.state import PARAMS, TIERS

FUNDAMENTAL_RED_LINES = {"现金流为负且营收下滑", "营收与EPS同时明显下滑"}


class BacktestEngine(ExecutionEngine):
    def decide(self, day, scores, **kwargs):
        self._stages_before_decision = {ticker: position["stage"] for ticker, position in self.positions.items()}
        if self.flags.get("watch_promote"):
            self.promote_watch_positions(scores, kwargs["prices"])
        return super().decide(day, scores, **kwargs)

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

    def queue(self, ticker, action, rule, label, **values):
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
            if action.startswith("sell") and position and self.index - position["entry_index"] < 10:
                red_exit = rule == "M-50" and FUNDAMENTAL_RED_LINES.intersection((score or {}).get("red_lines", []))
                if rule != "M-51" and not red_exit:
                    if rule in {"M-55", "M-56"}:
                        old_stage = getattr(self, "_stages_before_decision", {}).get(ticker)
                        if old_stage is not None:
                            position["stage"] = old_stage
                    self.flags_counts["minimum_hold_blocked"] = self.flags_counts.get("minimum_hold_blocked", 0) + 1
                    return None
        return super().queue(ticker, action, rule, label, **values)
