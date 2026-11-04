"""A029 regression tests for optional execution policies."""

from datetime import datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.trading.execution.state import new_position

pytestmark = pytest.mark.phase1_blocking


def engine(flags):
    from inves_cog.backtest.policies import BacktestEngine

    result = BacktestEngine(clock=FrozenClock(datetime(2026, 10, 30, tzinfo=timezone.utc)), flags=flags)
    result.signal_date = result.clock.today_trade_date()
    return result


def test_a029_death_blocks_watch_buys():
    subject = engine({"buy_consistency": True})
    subject.scores = {"NVDA": {"tier": "normal", "books": {"quality": 0, "growth": 80}}}
    subject.queue("NVDA", "buy_watch", "M-52", "观察波段", value=100, tier="normal")
    assert not subject.pending


def test_a029_minimum_hold_blocks_price_exit_but_keeps_disaster():
    subject = engine({"buy_consistency": True})
    subject.positions["NVDA"] = new_position(shares=5, price=100, tier="attack", index=0, state_version="")
    subject.index = 1
    subject.queue("NVDA", "sell_frac", "M-55", "破位减仓", fraction=0.5)
    subject.queue("NVDA", "sell_all", "M-51", "灾难止损")
    assert [order["rule_ids"] for order in subject.pending] == [["M-51"]]


@pytest.mark.parametrize("gate_pass", [True, False])
def test_a029_watch_promotion_precedes_swing_exit(monkeypatch, gate_pass):
    from inves_cog.trading.engine import ExecutionEngine
    from inves_cog.trading.execution.sells import swing_exit

    subject = engine({"watch_promote": True})
    subject.positions["NVDA"] = new_position(
        shares=5, price=100, tier="attack", index=0, state_version="", swing_only=True, swing_shares=5
    )
    score = {"tier": "attack", "gate_pass": gate_pass, "tech": {"price": 125, "vol20": 1, "dev50": 100}}

    def evaluate_exit(engine, day, scores, **kwargs):
        return swing_exit(engine.positions["NVDA"], scores["NVDA"]["tech"])

    monkeypatch.setattr(ExecutionEngine, "decide", evaluate_exit)
    order = subject.decide(subject.signal_date, {"NVDA": score}, prices={"NVDA": 125})
    position = subject.positions["NVDA"]
    assert position["swing_only"] is (not gate_pass)
    assert position["swing_shares"] == (0 if gate_pass else 5)
    assert (order is None) is gate_pass


def test_a029_ceiling_gate_uses_strictly_previous_friday_and_preserves_other_gates():
    from datetime import date

    from inves_cog.backtest.policies import apply_ceiling_gate

    prior, today = date(2026, 10, 23), date(2026, 10, 30)
    panel = {
        prior: {"m8": {"NVDA": 10, "A": 20, "B": 30, "C": 40, "D": 50}},
        today: {"m8": {"NVDA": 50, "A": 20, "B": 30, "C": 40, "D": 10}},
    }
    score = {
        "tier": "normal",
        "books": {"quality": 100, "growth": 100, "valuation": 0, "timing": 100},
        "red_lines": [],
        "m32_ok": True,
        "entry_pass": False,
        "gate_pass": False,
    }
    assert apply_ceiling_gate(score, panel, [prior, today], "NVDA", today)
    assert score["entry_pass"]
    score["books"]["quality"] = 0
    apply_ceiling_gate(score, panel, [prior, today], "NVDA", today)
    assert not score["entry_pass"]
    assert not apply_ceiling_gate(score, panel, [prior, today], "OUTSIDE", today)
