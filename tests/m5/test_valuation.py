"""Acceptance contracts precede the independent valuation implementation."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from tests.harness.tools.golden import load_golden

ROOT = Path(__file__).resolve().parents[2]


def cases():
    return load_golden("m5_valuation_synthetic.json")["cases"]


def stable():
    return deepcopy(cases()[0]["input"])


@pytest.mark.phase1_blocking
def test_valuation_synthetic():
    from tests.m5.inputs_cases import assert_inputs

    assert_inputs()
    from inves_cog.valuation_v1.calculations import evaluate, pe_percentiles

    for case in cases():
        actual = evaluate(case["type"], case["input"])
        for k, v in case["expected"].items():
            if k in ("note", "price_after_drop", "p_after_drop"):
                continue
            if isinstance(v, dict):
                for sk, sv in v.items():
                    assert actual["details"][k][sk] == pytest.approx(sv, abs=1e-6)
            elif isinstance(v, bool) or isinstance(v, str):
                assert actual[k] == v
            elif isinstance(v, list):
                assert actual[k] == pytest.approx(v, abs=1e-6)
            else:
                assert actual[k] == pytest.approx(v, abs=0.00051 if k in ("implied_growth", "delta_g") else 1e-6)
        assert actual["status"] == "ok"
    rows = [{"date": date(2016 + i // 100, 1, 1), "close": i + 1, "eps_ttm": 1} for i in range(1000)]
    rows += [
        {"date": date(2025, 1, 1), "close": 1e9, "eps_ttm": 0},
        {"date": date(2027, 1, 1), "close": 1e9, "eps_ttm": 1},
    ]
    p = pe_percentiles(rows, date(2026, 1, 1))
    assert p["pe_p50"] == 500.5 and p["eligible_count"] == 1000 and p["trim_each"] == 25
    fallback = pe_percentiles(rows[-2:], date(2026, 1, 1), peer_p50=[20, 40, None])
    assert fallback["pe_p50"] == 30 and fallback["insufficient_pe_history"]
    assert pe_percentiles([], date(2026, 1, 1))["pe_p50"] is None


@pytest.mark.phase1_blocking
def test_growth_valuation_v11():
    from inves_cog.valuation_v1.calculations import evaluate

    r = evaluate("成长", cases()[1]["input"])
    assert r["neutral"] == pytest.approx(6 * 1.35 * 1.2625 * 1.175 * 22.5 / 1.1**3)
    assert r["details"]["neutral"]["exit_pe"] == 22.5
    assert evaluate("成长", {**cases()[1]["input"], "pe_p90": 20})["neutral"] < r["neutral"]
    assert evaluate("未盈利成长", {**cases()[5]["input"], "cash": 0.5e9})["confidence"] == "低"


@pytest.mark.phase1_blocking
def test_valuation_ignores_price():
    from inves_cog.valuation_v1.calculations import evaluate

    for case in cases():
        a, b = evaluate(case["type"], case["input"]), evaluate(case["type"], {**case["input"], "price": 1e7})
        assert [a[k] for k in ("bear", "neutral", "bull")] == [b[k] for k in ("bear", "neutral", "bull")]
        assert a["p"] != b["p"]


@pytest.mark.phase1_blocking
def test_valuation_monotone_and_stable():
    from inves_cog.valuation_v1.calculations import evaluate
    from inves_cog.valuation_v1.lifecycle import ValuationBook

    for c in cases():
        r = evaluate(c["type"], c["input"])
        assert r["bear"] <= r["neutral"] <= r["bull"]
    data = json.loads((ROOT / "tests/fixtures/phase1/m5/lifecycle.json").read_text())
    book = ValuationBook()
    ranges = []
    for d, p, change in zip(data["dates"], data["prices"], data["consensus_changes_pct"]):
        r = book.update(
            "AAA",
            date.fromisoformat(d),
            "稳定",
            {**stable(), "eps_ntm": 6.6 * (1 + change / 100)},
            period="2026-06-30",
            price=p,
        )
        ranges.append(tuple(r[k] for k in ("bear", "neutral", "bull")))
    assert len(set(ranges)) == 1
    missing = evaluate("稳定", {"price": 100})
    assert missing["neutral"] is None and missing["reason"]
    assert evaluate("困境", {"price": 1})["reason"] == "不估值：亏损且无增长"


@pytest.mark.phase1_replay
def test_trading_without_valuation():
    from inves_cog.valuation_v1.calculations import evaluate
    from tests.m4.test_execution import DAY, NEXT, engine, signal

    def orders(enabled):
        e = engine()
        if enabled:
            evaluate("稳定", stable())
        e.decide(DAY, {"AAA": signal()}, prices={"AAA": 100}, history={"AAA": [100] * 200})
        return json.dumps(e.plan(NEXT), sort_keys=True, default=str).encode()

    assert orders(True) == orders(False)


@pytest.mark.phase1_blocking
def test_valuation_schema_revoke():
    from inves_cog.valuation_v1.repository import WRITE_TABLES
    from tests.harness.tools.permissions import assert_no_select, assert_no_write

    assert_no_select("role_trading", "valuation_v1")
    assert_no_write("role_valuation", "trading")
    assert WRITE_TABLES == {"ranges", "position_panel", "shadow_rules"}
    sql = (ROOT / "migrations/phase1_m5_0001_valuation_ranges_panel_shadow.sql").read_text()
    assert "FROM role_trading" in sql
    for table in WRITE_TABLES:
        assert "valuation_v1." + table in sql


@pytest.mark.phase1_blocking
def test_valuation_label():
    from inves_cog.valuation_v1.calculations import LABEL, evaluate
    from inves_cog.valuation_v1.shadows import panel, shadow, summarize

    r = evaluate("稳定", stable())
    for out in [r, shadow(r), panel({"ticker": "AAA", "weight_pct": 3, **r}), summarize([])]:
        assert out["label"] == LABEL == "估值参考 v1，不参与仓位"


@pytest.mark.phase1_blocking
def test_type_switch_needs_two_periods():
    from inves_cog.valuation_v1.lifecycle import TypeHistory, classify

    h = TypeHistory()
    assert h.observe("2025-12-31", "稳定") == "稳定"
    assert h.observe("2026-03-31", "成长") == "稳定"
    assert h.observe("2026-03-31", "成长") == "稳定"
    assert h.observe("2026-06-30", "成长") == "成长"
    assert h.override("金融", who="reviewer", reason="verified industry") == "金融"
    assert h.audit[-1]["old"] == "成长"
    assert classify({"ticker": "JPM", "sic": 6021}) == "金融"
    assert classify({"ticker": "V", "sic": 6021, "ni_ttm": 10, "rev_growth": 5}) == "稳定"
    assert classify({"ni_ttm": -1, "rev_growth": 20}) == "未盈利成长"
    assert classify({"ni_ttm": -1, "rev_growth": 10}) == "困境"
    assert classify({"ni_ttm": 1, "subindustry": "存储"}) == "周期"
    assert classify({"ni_ttm": 1, "rev_cagr_3y": 20, "rev_growth": 20}) == "成长"


@pytest.mark.phase1_blocking
def test_change_decomposition_sums():
    from inves_cog.valuation_v1.lifecycle import decompose
    from inves_cog.valuation_v1.calculations import evaluate

    a = stable()
    b = {**a, "eps_ntm": 7, "eps_ttm": 6.5, "pe_p50": 28}
    out = decompose("稳定", a, "稳定", b)
    assert list(out) == ["类型/方法", "一致预期", "财报", "倍数"]
    assert sum(out.values()) == pytest.approx(evaluate("稳定", b)["neutral"] - evaluate("稳定", a)["neutral"])
    out = decompose("稳定", a, "成长", cases()[1]["input"])
    assert out["类型/方法"] != 0 and all(out[k] == 0 for k in ["一致预期", "财报", "倍数"])


@pytest.mark.phase1_blocking
def test_pending_review_over_25pct():
    from inves_cog.valuation_v1.lifecycle import ValuationBook

    b = ValuationBook()
    a = b.update("AAA", date(2026, 10, 9), "稳定", stable(), period="2026-06-30", price=170)
    new = {**stable(), "eps_ntm": 20}
    r = b.update("AAA", date(2026, 10, 12), "稳定", new, period="2026-06-30", price=180)
    assert r["pending_review"] and r["neutral"] == a["neutral"] and r["proposed"]["neutral"] > 1.25 * a["neutral"]
    ok = b.update("AAA", date(2026, 10, 13), "稳定", new, period="2026-09-30", price=180)
    assert not ok["pending_review"] and ok["neutral"] > a["neutral"]


@pytest.mark.phase1_blocking
def test_implied_growth_no_solution():
    from inves_cog.valuation_v1.calculations import evaluate

    r = evaluate("成长", {**cases()[1]["input"], "price": 1e10})
    assert r["implied_growth"] is None and "无法反解" in r["implied_reason"]
    r = evaluate("成长", cases()[2]["input"])
    assert r["implied_exceeds_cap"] and r["implied_growth"] > 60


@pytest.mark.phase1_blocking
def test_position_panel():
    from inves_cog.valuation_v1.shadows import panel, summarize

    rows = []
    for c in load_golden("m5_valuation_synthetic.json")["valuation_position_panel"]:
        out = panel({"ticker": c["ticker"], **c["input"]})
        rows.append(out)
        for k, v in c["expected"].items():
            if isinstance(v, bool):
                assert out[k] is v
            else:
                assert out[k] == pytest.approx(v, abs=0.00051)
    total = summarize(rows)
    assert total["valuation_at_risk_pct"] == pytest.approx(sum(r["valuation_at_risk_pct"] for r in rows))
    assert total["shadow_weight_pct"] == pytest.approx(
        sum(r["shadow_suggested_weight_pct"] for r in rows if not r["greyed"])
    )


@pytest.mark.phase1_blocking
def test_shadow_rules_no_orders():
    from inves_cog.valuation_v1.shadows import shadow

    missing = shadow({"type": "成长", "confidence": "低", "p": None, "delta_g": None})
    assert missing["vt1"] is None and missing["vt2"] is None and missing["v3_trim_flag"] is None
    from inves_cog.valuation_v1.shadows import shadow

    r = {"p": 1.31, "confidence": "高", "type": "稳定", "version": "x"}
    # K01 official answer: delta-g coordinates, not the current-price p curve.
    for dg, expected in [(-30, 95), (-10, 95), (-5, 82.5), (0, 70), (5, 55), (10, 40), (17.5, 25), (25, 10), (90, 10)]:
        actual = shadow({**r, "type": "成长", "delta_g": dg, "p": 0.001})
        assert actual["v1_score"] == expected
    unavailable = shadow({**r, "type": "成长", "delta_g": None, "p": 0})
    assert unavailable["v1_score"] is None and unavailable["v1_reason"]
    a = shadow(r)
    assert a["vt1"] and a["vt2"] and a["v3_trim_flag"] and a["v2_coef"] == 0
    assert not shadow(r, seen_versions={"x"})["v3_trim_flag"]
    assert not shadow({**r, "confidence": "低"})["vt1"]
    assert shadow({**r, "p": -0.1, "bear": 80}, bear_30d=100)["v2_coef"] == 0
    assert shadow({**r, "p": -0.1, "bear": 95}, bear_30d=100)["v2_coef"] == 1
    assert shadow({**r, "p": 0.5})["v1_score"] == 70
    assert not any(k in a for k in ("orders", "actions", "intent"))


@pytest.mark.phase1_live
def test_valuation_live_smoke():
    from inves_cog.valuation_v1.cli import run
    from inves_cog.clock import SystemClock
    from inves_cog.ingest.settings import read_environment

    out = run(clock=SystemClock(), values=read_environment(), persist=False)
    assert len(out["ranges"]) == 59
    assert all(r["status"] == "ok" or r.get("reason") for r in out["ranges"])
