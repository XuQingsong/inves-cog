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


@pytest.mark.parametrize(
    "below_days, depth_atr, fear, quality, expected",
    [(1, 0.5, 0, 80, None), (2, 0.5, 0, 80, 0.5), (1, 1.1, 0, 80, 0.5), (1, 0.5, 3, 80, 0.8), (1, 0.5, 0, 70, 0.8)],
)
def test_a029_breakdown_confirmation(below_days, depth_atr, fear, quality, expected):
    subject = engine({"breakdown_confirm": True})
    subject.positions["NVDA"] = new_position(
        shares=5,
        price=100,
        tier="normal",
        index=0,
        state_version="",
        entry_books={"quality": 80, "growth": 80},
    )
    subject.scores = {
        "NVDA": {
            "tier": "normal",
            "books": {"quality": quality, "growth": 80},
            "red_lines": ["趋势破位"],
            "breakdown_below_days": below_days,
            "breakdown_depth_atr": depth_atr,
            "fear_level": fear,
        }
    }
    subject.queue("NVDA", "sell_frac", "M-55", "破位减仓", fraction=0.8)
    assert (subject.pending[0]["fraction"] if subject.pending else None) == expected


@pytest.mark.parametrize(
    "closes,quality,veto,expected",
    [(2, 90, False, False), (3, 90, False, True), (3, 70, False, False), (3, 90, True, False)],
)
def test_a029_price_reentry_only_replaces_valuation_gate(closes, quality, veto, expected):
    from inves_cog.backtest.policies import allow_price_reentry

    score = {
        "tier": "normal",
        "books": {"quality": quality, "growth": 90, "valuation": 0, "timing": 90},
        "red_lines": [],
        "m32_ok": True,
        "entry_pass": False,
        "overval_veto": veto,
    }
    previous = {"tier_now": "normal", "entry_books": {"quality": 90, "growth": 90}}
    assert allow_price_reentry(score, previous, closes) is expected
    assert score["entry_pass"] is expected


def test_a029_short_hold_audit_uses_exchange_sessions():
    from datetime import date

    from inves_cog.backtest.evaluate import short_hold_sales

    def fill(ticker, side, day):
        return {"ticker": ticker, "side": side, "trade_date": date.fromisoformat(day)}

    trades = [
        fill("AAPL", "buy", "2026-10-30"),
        fill("MSFT", "buy", "2026-10-30"),
        fill("AAPL", "sell", "2026-11-02"),
        fill("MSFT", "sell", "2026-11-03"),
    ]
    assert short_hold_sales(trades) == 1


def test_a029_repaired_state_cannot_replace_newer_or_healthy_state():
    from datetime import date
    from types import SimpleNamespace

    from inves_cog.backtest.tier_repair import repaired_state

    def row(day, codes):
        return SimpleNamespace(filed=date.fromisoformat(day), health_codes=codes)

    original = row("2025-04-30", ["core_field_missing"])
    healthy = row("2025-04-30", ["ok"])
    later = row("2025-05-01", ["ok"])
    assert repaired_state(original, [healthy, later], date(2025, 4, 30)) is healthy
    assert repaired_state(original, [later], date(2025, 4, 30)) is original
    assert repaired_state(later, [healthy], date(2025, 5, 2)) is later
    assert repaired_state(healthy, [row("2025-04-30", ["ni_tag_fallback"])], date(2025, 5, 2)) is healthy


def test_fear_coverage_counts_available_replay_days_from_each_start():
    from datetime import date

    from inves_cog.backtest.evaluate import fear_coverage

    first, second, third = (date(2024, 1, day) for day in (2, 3, 4))
    assert fear_coverage({first, second, third}, {first: 0, second: None}, first, third) == {
        "covered_days": 1,
        "replay_days": 3,
        "coverage_pct": 100 / 3,
    }
    assert fear_coverage({first, second, third}, {first: 0}, second, third)["coverage_pct"] == 0


def test_a029_minimum_hold_restarts_after_add_on_fill(monkeypatch):
    from inves_cog.trading.engine import ExecutionEngine

    subject = engine({"buy_consistency": True})
    subject.positions["NVDA"] = new_position(shares=5, price=100, tier="attack", index=0, state_version="")
    subject.index = 12
    monkeypatch.setattr(ExecutionEngine, "fill", lambda *args, **kwargs: [{"ticker": "NVDA", "side": "buy"}])
    subject.fill(subject.signal_date, {})
    subject.index = 13
    subject.queue("NVDA", "sell_frac", "M-55", "破位减仓", fraction=0.5)
    subject.queue("NVDA", "sell_all", "M-51", "灾难止损")
    assert [order["rule_ids"] for order in subject.pending] == [["M-51"]]
