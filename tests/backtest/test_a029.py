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
