"""M4 acceptance names and behavioral contracts, written before implementation."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2026, 1, 9)
NEXT = date(2026, 1, 12)
CLOCK = FrozenClock(datetime(2026, 1, 12, 13, tzinfo=timezone.utc))


def signal(**changes):
    row = {
        "ticker": "AAA",
        "signal_date": DAY,
        "tier": "normal",
        "certainty": "high",
        "books": {"quality": 80, "growth": 80, "valuation": 60, "timing": 80},
        "tech": {"price": 100, "price_vs_ma200": 10, "dev50": 1, "vol20": 30, "drawdown252": -1},
        "rank_score": 80,
        "hold_score": 80,
        "hold_ok": True,
        "fund_bad": False,
        "entry_pass": True,
        "tradable": True,
        "red_lines": [],
        "runway_ok": True,
        "consec_pass": 20,
        "consec_below200": 0,
        "consec_tim35": 0,
        "consec_tim30": 0,
        "state_version": "2025-11-01",
        "rev_growth": 20,
        "rev_accel_pp": 2,
    }
    row.update(changes)
    return row


def engine(cash=1_000_000):
    from inves_cog.trading.engine import ExecutionEngine

    return ExecutionEngine(clock=CLOCK, initial_cash=cash)


def position(**changes):
    from inves_cog.trading.execution.state import new_position

    row = new_position(shares=100, price=100, tier="normal", index=0, state_version="2025-10-01")
    row.update(changes)
    return row


def test_order_reason_tokens():
    from inves_cog.trading.execution.contracts import validate_order

    sample = {"rule_ids": ["M-34", "M-35"], "reason_zh": "M-34 四账过线，按层级首笔开仓"}
    validate_order(sample)
    for bad in (["V-01"], [], ["M-35", "估值区间"]):
        with pytest.raises(ValueError):
            validate_order({**sample, "rule_ids": bad})
    for bad in ("目标价 200", "悲观情景", "p=0.5", "估值区间", "M-35 neutral"):
        with pytest.raises(ValueError):
            validate_order({**sample, "reason_zh": bad})


def test_orders_only_from_engine():
    from inves_cog.trading import engine as module

    assert "INSERT INTO trading.orders" in Path(module.__file__).read_text()
    for path in (ROOT / "src/inves_cog").rglob("*.py"):
        if path != Path(module.__file__):
            assert "INSERT INTO trading.orders" not in path.read_text()
    migration = (ROOT / "migrations/phase1_m4_0001_paper_ledger_orders_plan.sql").read_text()
    assert "role_trading" in migration and "REVOKE" in migration
    assert "GRANT INSERT" not in migration.replace("GRANT INSERT, UPDATE, DELETE ON", "")


def test_fill_timing_and_cost():
    e = engine(5000)
    e.pending = [
        {
            "ticker": "AAA",
            "signal_date": DAY,
            "trade_date": NEXT,
            "action": "buy_to",
            "fraction": 1,
            "tier": "normal",
            "label": "试仓买入",
            "certainty": "high",
            "rule_ids": ["M-35"],
            "reason_zh": "M-35 按首笔比例开仓",
        }
    ]
    assert e.fill(DAY, {"AAA": 100}) == []
    e.fill(NEXT, {"AAA": 100})
    assert all(isinstance(t["qty"], int) for t in e.trades)
    assert e.trades[0]["cost"] == pytest.approx(e.trades[0]["qty"] * 100 * 0.001)
    e = engine(5000)
    e.pending = [
        {
            "ticker": "AAA",
            "signal_date": DAY,
            "trade_date": NEXT,
            "action": "buy_watch",
            "value": 5000,
            "tier": "normal",
            "label": "观察波段买入",
            "rule_ids": ["M-60"],
            "reason_zh": "M-60 已止跌开观察波段仓",
        }
    ]
    e.fill(NEXT, {"AAA": 100})
    assert e.cash == pytest.approx(-5)  # Q-M4-9: fees are charged after integer shares.
    assert "cash_negative" in e.health_codes


def test_membership_asof():
    from inves_cog.trading.execution.contracts import members_asof

    members = [{"ticker": "OLD", "listed_on": "2000-01-01"}, {"ticker": "NEW", "listed_on": "2026-01-12"}]
    assert members_asof(members, DAY) == ["OLD"]
    assert members_asof(members, NEXT) == ["OLD", "NEW"]
    # Muse's watch branch ignores entry books cleared by M07; paper retains health gates.
    from inves_cog.trading.engine import ExecutionEngine

    weak = signal(
        ticker="META",
        entry_pass=False,
        tradable=False,
        extractor="legacy",
        books={"quality": None, "growth": None, "valuation": None, "timing": 30},
        tech={**signal()["tech"], "price": 110, "price_vs_ma200": -15, "dev50": -10, "drawdown252": -25},
    )
    for mode, permitted in (("replay_v18", True), ("paper", False)):
        e = ExecutionEngine(clock=CLOCK, mode=mode)
        e.decide(DAY, {"META": weak}, prices={"META": 110}, history={"META": [100] * 20 + [110]})
        assert any(o["action"] == "buy_watch" for o in e.pending) == permitted


def test_sell_priority():
    from inves_cog.trading.execution.sells import sell_signal

    s = signal(books={"quality": 30, "growth": 30, "valuation": 20, "timing": 10}, consec_below200=10)
    assert sell_signal(position(), s, index=20, panic=False)["rule_ids"] == ["M-50"]
    safe = signal(consec_below200=3)
    assert sell_signal(position(), safe, index=20, panic=False)["rule_ids"] == ["M-55"]
    assert sell_signal(position(), signal(), index=20, panic=False) is None


def test_panic_gate_scope():
    from inves_cog.trading.execution.sells import sell_signal

    assert sell_signal(position(), signal(consec_below200=3), index=20, panic=True) is None
    assert sell_signal(position(), signal(fund_bad=True), index=20, panic=True)["rule_ids"] == ["M-50"]
    s = signal(tier="attack", tech={**signal()["tech"], "price": 50, "price_vs_ma200": -10})
    assert sell_signal(position(tier_now="attack", peak_price=100), s, index=20, panic=True)["rule_ids"] == ["M-51"]
    s = signal(tech={**signal()["tech"], "dev50": 15})
    assert sell_signal(position(swing_shares=20), s, index=20, panic=True)["rule_ids"] == ["M-53"]


def test_cooldown_m58():
    e = engine()
    e.positions["AAA"] = position(last_sell_index=15, filled_fraction=0.1, first_fraction=0.4)
    e.index = 20
    e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100})
    assert not any(o["action"] == "buy_to" for o in e.pending)
    assert any("M-58" in s["rule_ids"] for s in e.skips)
    # Q-M4-8: a valid swing buy uses its own interval, independent of a recent core sale.
    e = engine()
    e.positions["AAA"] = position(last_sell_index=19, filled_fraction=0.2)
    e.index = 20
    s = signal(entry_pass=False, tech={**signal()["tech"], "dev50": -6, "drawdown252": -20})
    e.decide(DAY, {"AAA": s}, prices={"AAA": 100})
    assert any(o["action"] == "buy_swing" for o in e.pending)


def test_overlay_cooling_skip_and_cancel():
    e = engine()
    e.decide(DAY, {"AAA": signal(), "BBB": signal(ticker="BBB")}, prices={"AAA": 100, "BBB": 100})
    overlay = json.loads((ROOT / "tests/fixtures/phase1/m4/overlay.json").read_text())
    plan = e.plan(NEXT, overlay=overlay)
    assert [c["ticker"] for c in plan["cancels"]] == ["AAA"]
    assert any(o["ticker"] == "BBB" for o in plan["orders"])
    assert any("increase" in error for error in plan["overlay"]["errors"])
    e.fill(NEXT, {"AAA": 1, "BBB": 100})
    assert not any(t["ticker"] == "AAA" for t in e.trades)


def test_overlay_missing_marked():
    for overlay, status in ((None, "missing"), ({"generated_at": "2026-01-12T10:00:00Z"}, "stale")):
        e = engine()
        e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100})
        plan = e.plan(NEXT, overlay=overlay)
        assert plan["overlay"]["status"] == status
        assert plan["published"] and plan["orders"]


def test_plan_unpublished_low_coverage():
    e = engine()
    e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100})
    plan = e.plan(NEXT, tradable=100, with_bars=94)
    assert not plan["published"] and not plan["orders"]
    assert plan["unpublished_reason"] == "data_coverage_below_95"
    assert engine().plan(NEXT, tradable=100, with_bars=95)["published"]


def test_plan_json_contract():
    e = engine()
    s = signal(entry_pass=False, red_lines=["短线过热"])
    e.decide(DAY, {"AAA": signal(), "NO": {**s, "ticker": "NO"}}, prices={"AAA": 100, "NO": 100})
    plan = e.plan(NEXT)
    assert set(
        (
            "trade_date",
            "signal_date",
            "rule_set",
            "params_version",
            "overlay",
            "data_coverage",
            "published",
            "unpublished_reason",
            "orders",
            "cancels",
            "skips",
            "holdings",
            "portfolio",
        )
    ) <= set(plan)
    assert plan["rule_set"] == "A" and all(s["ticker"] != "NO" for s in plan["skips"])
    json.dumps(plan, default=str, allow_nan=False)
    # K04: a pending watch opening also consumes one of M-34's twelve portfolio slots.
    case = json.loads((ROOT / "tests/fixtures/phase1/m4/capacity_synthetic.json").read_text())
    candidates = {t: signal(ticker=t, tier=tier) for tier in ("attack", "normal") for t in case[tier]}
    control = engine()
    control.decide(DAY, candidates, prices={t: 100 for t in candidates})
    assert len({o["ticker"] for o in control.pending}) == 12
    candidates[case["watch"]] = signal(
        ticker=case["watch"],
        entry_pass=False,
        tech={**signal()["tech"], "price_vs_ma200": -15, "dev50": -8, "drawdown252": -25},
    )
    with_watch = engine()
    with_watch.decide(
        DAY, candidates, prices={t: 100 for t in candidates}, history={case["watch"]: case["watch_history"]}
    )
    with_watch.fill(NEXT, {t: 100 for t in candidates})
    assert len(with_watch.positions) <= 12, "K04: pending watch opening is omitted from the M-34 slot count"


def test_vix_missing_not_panic():
    from inves_cog.trading.execution.risk import vix_panic

    assert vix_panic(None, [20] * 252)[0] is False
    assert vix_panic(30, [20] * 119)[0] is False
    assert vix_panic(20, [20] * 120)[0] is True
    assert vix_panic(19, [20] * 120)[0] is False


@pytest.fixture(scope="session")
def replay():
    from inves_cog.trading.execution.replay import run_frozen

    return run_frozen()


@pytest.mark.phase1_replay
def test_v18_replay(replay):
    assert replay["return_pct"] == pytest.approx(49.45, abs=1)
    assert replay["max_drawdown_pct"] == pytest.approx(-12.64, abs=0.5)
    assert replay["comparison"]["match_rate"] >= 0.95
    assert not replay["comparison"]["differences"]


@pytest.mark.phase1_replay
def test_amd_entry_2026_01_12(replay):
    buys = [t for t in replay["trades"] if t["ticker"] == "AMD" and str(t["trade_date"]) == "2026-01-12"]
    assert buys and buys[0]["side"] == "buy" and buys[0]["qty"] > 0
    assert buys[0]["signal_date"] == date(2026, 1, 9)


@pytest.mark.phase1_live
def test_paper_live_smoke():
    from inves_cog.clock import SystemClock
    from inves_cog.ingest.settings import read_environment
    from inves_cog.trading.execution.cli import run_daily

    result = run_daily(clock=SystemClock(), values=read_environment(), persist=False)
    (ROOT / "handoff/M4/live-plan.json").write_text(
        json.dumps(result, default=str, ensure_ascii=False, indent=2) + "\n"
    )
    assert result["published"] and result["rule_set"] == "A"
    assert result["score_source"] == "trading.daily_scores"
    assert result["data_coverage"]["pct"] >= 95
    assert set(result["portfolio"]["tier_usage"]) == {"defense", "normal", "attack"}


for _name, _function in list(globals().items()):
    if _name.startswith("test_") and _name not in {
        "test_v18_replay",
        "test_amd_entry_2026_01_12",
        "test_paper_live_smoke",
    }:
        globals()[_name] = pytest.mark.phase1_blocking(_function)
