"""A019: delayed settlement, durable terminal states and unchanged v18 capacity."""

from datetime import date, datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.state import new_position

pytestmark = pytest.mark.phase1_blocking
FRIDAY = date(2026, 1, 9)
MONDAY = date(2026, 1, 12)
TUESDAY = date(2026, 1, 13)
CLOCK = FrozenClock(datetime(2026, 1, 14, 13, tzinfo=timezone.utc))


def engine(mode="paper"):
    value = ExecutionEngine(clock=CLOCK, initial_cash=100_000, mode=mode)
    value.signal_date = FRIDAY
    return value


def queue(eng, action="buy_to", **extra):
    values = {"tier": "normal", "fraction": 0.5, "certainty": "high", **extra}
    eng.queue("AAA", action, "M-40", "确认加仓", **values)
    return eng.pending[-1]


def test_p2_missing_session_uses_its_open_and_does_not_fill_twice():
    from inves_cog.trading.execution.service import settle_through

    e = engine()
    e.settled_dates = {FRIDAY}
    queue(e)
    inputs = {"bars": {"AAA": {MONDAY: {"open": 10}, TUESDAY: {"open": 99}}}}
    settle_through(e, TUESDAY, inputs)
    assert len(e.trades) == 1
    assert e.trades[0]["trade_date"] == MONDAY and e.trades[0]["fill_price"] == 10
    assert e.trades[0]["execution_note"] == "补撮合（计划延误）"
    assert MONDAY in e.settled_dates and TUESDAY in e.settled_dates
    settle_through(e, TUESDAY, inputs)
    assert len(e.trades) == 1


def test_p2_missing_open_blocks_advancement_instead_of_losing_the_day():
    from inves_cog.trading.execution.service import settle_through

    e = engine()
    e.settled_dates = {FRIDAY}
    queue(e)
    settle_through(e, TUESDAY, {"bars": {"AAA": {TUESDAY: {"open": 99}}}})
    assert not e.trades and MONDAY not in e.settled_dates and TUESDAY not in e.settled_dates
    assert len(e.pending) == 1


def test_p5_three_equivalent_intents_have_unique_ids_and_two_superseded():
    e = engine()
    old = queue(e)
    newer = queue(e)
    newest = queue(e)
    assert len({o["order_id"] for o in (old, newer, newest)}) == 3
    assert e.pending == [newest]
    assert [o["status"] for o in e.terminal_orders] == ["superseded", "superseded"]
    assert all("新意向" in o["reason_zh"] for o in e.terminal_orders)


def test_p5_different_action_and_ticker_are_preserved():
    e = engine()
    queue(e)
    queue(e, "buy_swing", value=500)
    e.queue("BBB", "buy_to", "M-35", "首笔买入", tier="normal", fraction=0.5)
    assert len(e.pending) == 3


def test_p4_failed_settlement_gets_terminal_reason():
    e = engine()
    queue(e, "sell_all")  # No position exists, so there is no executable quantity.
    e.fill(MONDAY, {"AAA": 10})
    assert not e.pending
    assert e.terminal_orders[0]["status"] == "expired"
    assert "未满足成交约束" in e.terminal_orders[0]["reason_zh"]


@pytest.mark.parametrize("status", ["filled", "canceled", "expired", "superseded"])
def test_p4_terminal_status_is_written_by_the_single_order_writer(status):
    e = engine()
    order = queue(e)
    e.record_terminal(order, status, "可核查的终态原因")
    rows = []

    class Connection:
        def execute(self, sql, args):
            rows.append((sql, args))

    e.persist_orders(Connection(), e.terminal_orders)
    assert rows[0][1][-2] == status and "可核查" in rows[0][1][11]
    restored = engine()
    restored.restore(e.snapshot())
    assert restored.order_lifecycle[-1]["status"] == status


def test_p6_old_pending_skip_and_independent_swing_explanations():
    e = engine()
    old = queue(e)
    e.signal_date = TUESDAY
    e.skip("AAA", "M-40", "N7", "层买入额度已满，暂不加仓")
    plan = e.plan(date(2026, 1, 14))
    assert "另有 1 月 12 日待成交单" in plan["skips"][0]["reason_zh"]
    assert plan["orders"][0]["order_id"] == old["order_id"]
    e = engine()
    queue(e, "buy_swing", value=500)
    e.skip("AAA", "M-58", "N7", "核心卖出后冷却期，暂不加仓")
    plan = e.plan(MONDAY)
    assert "核心加仓暂停（冷却期）" in plan["explanations"]["AAA"]
    assert "波段仓按独立规则买入" in plan["explanations"]["AAA"]


def test_p7_preserve_source_v18_capacity_formula_and_show_13_plus_1():
    e = engine()
    e.positions = {
        str(i): new_position(shares=10, price=10, tier="normal", index=0, state_version="x") for i in range(13)
    }
    e.positions["AAA"] = e.positions.pop("0")
    e.last_prices = {ticker: 10 for ticker in e.positions}
    queue(e)
    plan = e.plan(MONDAY)
    assert plan["portfolio"]["slot_count"] == {
        "holdings": 13,
        "buy_to_pending": 1,
        "total": 14,
        "held_additions": 1,
        "limit": 12,
    }
    assert plan["portfolio"]["slot_count_note"] == "持仓 13 + 加仓挂单 1 = 14"


def test_replay_mode_keeps_both_frozen_rule_intents():
    e = engine("replay_v18")
    queue(e, "sell_frac", fraction=0.25)
    queue(e, "sell_frac", fraction=0.3)
    assert len(e.pending) == 2  # Frozen v18 can issue two distinct same-day sell signals.
