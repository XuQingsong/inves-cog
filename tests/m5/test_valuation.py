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
    from tests.m5.tsm_annual_cases import assert_tsm_annual_build

    assert_tsm_annual_build()
    from tests.m5.a012_cases import assert_a012_historical_split_units

    assert_a012_historical_split_units()
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
    positive_fcf = evaluate("未盈利成长", {**cases()[5]["input"], "cash": 0.5e9, "fcf_ttm": 0.5e9})
    assert positive_fcf["runway_years"] == 1 and positive_fcf["runway_haircut"] is True


@pytest.mark.phase1_blocking
def test_valuation_ignores_price():
    from inves_cog.valuation_v1.calculations import evaluate

    for case in cases():
        a, b = evaluate(case["type"], case["input"]), evaluate(case["type"], {**case["input"], "price": 1e7})
        assert [a[k] for k in ("bear", "neutral", "bull")] == [b[k] for k in ("bear", "neutral", "bull")]
        assert a["p"] != b["p"]


@pytest.mark.phase1_blocking
def test_valuation_monotone_and_stable():
    from tests.m5.review_cases import assert_daily_candidate_trace

    assert_daily_candidate_trace()
    from inves_cog.valuation_v1.calculations import evaluate
    from inves_cog.valuation_v1.lifecycle import ValuationBook

    for c in cases():
        r = evaluate(c["type"], c["input"])
        assert r["bear"] <= r["neutral"] <= r["bull"]
    data = json.loads((ROOT / "tests/fixtures/phase1/m5/lifecycle.json").read_text())
    book = ValuationBook()
    ranges = []
    for d, p, change in zip(data["dates"], data["prices"], data["consensus_changes_pct"], strict=False):
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
    # Strict >3% means an exact endpoint is stable, one float64 step outside is not.
    import math

    for boundary, direction in [(6.6 * 1.03, math.inf), (6.6 * 0.97, -math.inf)]:
        edge_book = ValuationBook()
        edge_book.update("EDGE", date(2026, 10, 9), "稳定", stable(), period="2026-06-30", price=170)
        outside = math.nextafter(boundary, direction)
        edge = edge_book.update(
            "EDGE", date(2026, 10, 12), "稳定", {**stable(), "eps_ntm": outside}, period="2026-06-30", price=170
        )
        assert edge["inputs"]["eps_ntm"] == outside
    missing = evaluate("稳定", {"price": 100})
    assert missing["neutral"] is None and missing["reason"]
    assert missing["confidence"] == "低"
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
    from tests.m5.inputs_cases import assert_schedule

    assert_schedule()
    from inves_cog.valuation_v1.calculations import LABEL, evaluate
    from inves_cog.valuation_v1.shadows import panel, shadow, summarize

    r = evaluate("稳定", stable())
    for out in [r, shadow(r), panel({"ticker": "AAA", "weight_pct": 3, **r}), summarize([])]:
        assert out["label"] == LABEL == "估值参考 v1，不参与仓位"


@pytest.mark.phase1_blocking
def test_type_switch_needs_two_periods():
    from tests.m5.a012_cases import assert_a012_stale_annual_basis

    assert_a012_stale_annual_basis()
    from tests.m5.review_cases import assert_eps_split_comparability

    assert_eps_split_comparability()
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
    from inves_cog.valuation_v1.calculations import evaluate
    from inves_cog.valuation_v1.lifecycle import decompose

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
    from tests.m5.listed_unit_cases import assert_listed_units

    assert_listed_units()
    from tests.m5.coverage_cases import assert_coverage_contract

    assert_coverage_contract()
    from tests.m5.review_cases import assert_pe_reason_recovery

    assert_pe_reason_recovery()
    from tests.m5.inputs_cases import assert_service

    assert_service()
    from inves_cog.valuation_v1.shadows import panel, summarize

    missing = summarize(
        [
            {
                "ticker": "MISSING",
                "valuation_at_risk_pct": None,
                "shadow_suggested_weight_pct": None,
                "greyed": False,
                "weight_pct": None,
            }
        ]
    )
    assert missing["valuation_at_risk_pct"] is None and missing["shadow_weight_pct"] is None
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
    from inves_cog.clock import SystemClock
    from inves_cog.ingest.settings import read_environment
    from inves_cog.valuation_v1.cli import run

    out = run(clock=SystemClock(), values=read_environment(), persist=False)
    assert len(out["ranges"]) == 59
    assert all(r["status"] == "ok" or r.get("reason") for r in out["ranges"])


@pytest.mark.phase1_blocking
def test_sanity_gate_flags_extreme_neutral_ratio():
    """neutral/price outside [0.2, 5] marks the row 输入可疑; bands are kept."""
    from inves_cog.valuation_v1.calculations import mark_price
    from inves_cog.valuation_v1.shadows import shadow

    base = {
        "ticker": "X",
        "type": "周期",
        "status": "ok",
        "bear": 4.0,
        "neutral": 6.7,
        "bull": 10.1,
        "p": None,
        "inputs": {},
    }
    out = mark_price(deepcopy(base), 290.0)
    assert out["sanity"] == "输入可疑" and "0.02" in out["sanity_reason"]
    assert out["bear"] == 4.0 and out["bull"] == 10.1  # bands kept
    assert not shadow(out)["vt1"] and not shadow(out)["vt2"]  # gated out of shadow

    ok = mark_price(deepcopy(base), 8.0)  # neutral/price = 0.84 in-band
    assert "sanity" not in ok

    hi = mark_price(deepcopy({**base, "neutral": 1300.0, "bear": 540.0, "bull": 2500.0}), 215.0)
    assert hi["sanity"] == "输入可疑" and "6.05" in hi["sanity_reason"]


@pytest.mark.phase1_blocking
def test_sanity_flag_renders_unavailable_not_verdict():
    from inves_cog.web.brief import valuation_card
    from inves_cog.web.investor_html import _valuation

    row = {
        "status": "ok",
        "neutral": 6.7,
        "payload": {
            "bear": 4.0,
            "bull": 10.1,
            "sanity": "输入可疑",
            "sanity_reason": "中性档为现价的 0.02 倍，阈值 0.2–5",
        },
    }
    card = valuation_card(row, None, 290.0)
    text = _valuation(card)
    assert "估值暂不可用" in text and "输入数据待核" in text and "0.02" in text
    assert "高估" not in text and "低估" not in text


@pytest.mark.phase1_blocking
def test_finstate_selection_fixed_latest_filed_period_tiebreak():
    """state_asof reads fixed only; latest filed wins; period_end breaks ties."""
    from datetime import date

    from inves_cog.ingest.fundamentals.state import FinState, StateStore

    legacy = FinState("WDC", "legacy", date(2026, 10, 23), date(2026, 10, 2), values={"ni_ttm": 8_008e6})
    fixed_old = FinState("WDC", "fixed", date(2026, 10, 20), date(2026, 10, 2), values={"ni_ttm": 1})
    fixed_new_a = FinState("WDC", "fixed", date(2026, 10, 23), date(2026, 7, 3), values={"ni_ttm": 2})
    fixed_new_b = FinState("WDC", "fixed", date(2026, 10, 23), date(2026, 10, 2), values={"ni_ttm": 10_021e6})
    store = StateStore([legacy, fixed_old, fixed_new_a, fixed_new_b])
    got = store.state_asof("WDC", date(2026, 11, 9), "fixed")
    assert got is fixed_new_b  # latest filed; period_end breaks the filed tie
    assert store.state_asof("WDC", date(2026, 11, 9), "legacy") is legacy
    assert store.state_asof("WDC", date(2026, 10, 21), "fixed") is fixed_old  # PIT: new not yet filed


@pytest.mark.phase1_blocking
def test_structural_break_post_window_and_oneoff_flag():
    """断点后正常化窗口 + 一次性项目标记（WDC 形态）。"""
    from datetime import date, timedelta

    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.inputs import financial_inputs

    entity = {"ticker": "WDC", "sic": "3572", "sector": "storage"}
    q = []
    # quarterly states; ni_ttm grows then spikes (spin-off gain in the 07-03 derived Q4)
    for i, ni in enumerate([200e6, 250e6, 300e6, 1_182e6, 1_842e6, 3_205e6, 10_021e6, 10_500e6]):
        pe = date(2025, 3, 28) + timedelta(days=91 * i)
        q.append(
            FinState(
                "WDC",
                "fixed",
                pe + timedelta(days=20),
                pe,
                values={"ni_ttm": ni, "rev_ttm": 11_000e6, "eps_ttm": ni / 384e6},
            )
        )
    # annual rows: pre-break loss year + post-break gain year
    for pe, ni in [(date(2024, 6, 28), -798e6), (date(2025, 6, 27), 1_889e6), (date(2026, 7, 3), 9_424e6)]:
        q.append(
            FinState(
                "WDC", "fixed", pe + timedelta(days=45), pe, form="10-K", values={"ni_ttm": ni, "rev_ttm": 13_000e6}
            )
        )
    st = q[-1]
    out = financial_inputs(st, q, entity)
    assert out.get("normalization_note") == "周期正常化历史不足（断点 2025-02-21 后仅 6 季）"
    assert out["normal_net_margin"] is None  # 不硬算：断点后不足 8 季不出周期估值
    assert out.get("oneoff_note") and "2026" in out["oneoff_note"]


@pytest.mark.phase1_blocking
def test_break_unvalued_e2e_payload_notes_render():
    """断点不足 8 季 → 周期行 unvalued，notes 进 payload.inputs，页面出原因。"""
    from datetime import date, timedelta

    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.calculations import calculate, mark_price
    from inves_cog.valuation_v1.inputs import financial_inputs
    from inves_cog.web.brief import valuation_card

    entity = {"ticker": "WDC", "sic": "3572", "sector": "storage"}
    q = [
        FinState(
            "WDC",
            "fixed",
            pe - timedelta(days=3),
            pe,
            values={"ni_ttm": ni, "rev_ttm": 11_000e6, "eps_ttm": 25.8},
        )
        for pe, ni in [
            (date(2025, 10, 3), 1_182e6),
            (date(2026, 1, 2), 1_842e6),
            (date(2026, 4, 3), 3_205e6),
            (date(2026, 10, 2), 10_021e6),
            (date(2026, 10, 10), 10_500e6),
        ]
    ]
    for pe, ni in [(date(2024, 6, 28), -798e6), (date(2025, 6, 27), 1_889e6), (date(2026, 7, 3), 9_424e6)]:
        q.append(
            FinState(
                "WDC", "fixed", pe + timedelta(days=45), pe, form="10-K", values={"ni_ttm": ni, "rev_ttm": 13_000e6}
            )
        )
    inputs = financial_inputs(q[-1], q, entity)
    row = calculate("周期", inputs)
    row = mark_price(row, 289.0)
    assert row["status"] == "unvalued"
    # service appends normal_margin_reason for 周期 rows
    row["reason"] = "; ".join(filter(None, [row["reason"], inputs.get("normal_margin_reason")]))
    assert "周期正常化历史不足" in row["reason"]
    payload = dict(row)  # repository 存 jsonb(row)
    assert payload["inputs"].get("normalization_note")
    assert payload["inputs"].get("oneoff_note")
    card = valuation_card(
        {"neutral": None, "payload": payload, "status": "unvalued", "bear": None, "bull": None, "text": row["reason"]},
        None,
        289.0,
    )
    card["text"] = row["reason"]
    from inves_cog.web.brief import short_unvalued_text

    assert "周期正常化历史不足" in short_unvalued_text(card["text"])


@pytest.mark.phase1_blocking
def test_oneoff_single_quarter_thresholds():
    """单季口径一次性项目：跳变需 >3×前 7 季中位且 >40% TTM；亏损季前后盈利且 >25% TTM。"""
    from datetime import date, timedelta

    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.inputs import financial_inputs

    entity = {"ticker": "GRW", "sic": "3572", "sector": "storage"}

    def mk(ticker, pe, ni, form="10-Q"):
        return FinState(
            ticker, "fixed", pe + timedelta(days=20), pe, form=form, values={"ni_ttm": ni, "rev_ttm": 10_000e6}
        )

    dates = [date(2025, 1, 3) + timedelta(days=91 * i) for i in range(8)]

    # 稳定增长：TTM 差分均匀，既未超中位 3 倍也未占 TTM 40% → 不标
    steady = [
        mk("GRW", pe, ni)
        for pe, ni in zip(dates, [100e6, 150e6, 205e6, 265e6, 330e6, 400e6, 475e6, 555e6], strict=True)
    ]
    assert financial_inputs(steady[-1], steady, entity).get("oneoff_note") is None

    # 单季尖峰：末季差分 680 > 3×中位 20 且 > 40%×900 → 标末季
    spike = [
        mk("GRW", pe, ni)
        for pe, ni in zip(dates, [100e6, 120e6, 140e6, 160e6, 180e6, 200e6, 220e6, 900e6], strict=True)
    ]
    out = financial_inputs(spike[-1], spike, entity)
    assert out.get("oneoff_note") == f"疑似一次性项目（{dates[-1]}）"

    # 尖峰但占 TTM 不足 40% → 不标
    small = [
        mk("GRW", pe, ni)
        for pe, ni in zip(dates, [100e6, 120e6, 140e6, 160e6, 180e6, 200e6, 220e6, 300e6], strict=True)
    ]
    assert financial_inputs(small[-1], small, entity).get("oneoff_note") is None

    # 亏损季被盈利季夹住且 |亏损| > 25% TTM → 标该亏损季
    dip = [
        mk("GRW", pe, ni)
        for pe, ni in zip(dates, [400e6, 430e6, 330e6, 360e6, 390e6, 410e6, 430e6, 450e6], strict=True)
    ]
    out = financial_inputs(dip[-1], dip, entity)
    assert out.get("oneoff_note") == f"疑似一次性项目（{dates[2]}）"

    # 亏损额未达 25% TTM → 不标
    mild = [
        mk("GRW", pe, ni)
        for pe, ni in zip(dates, [400e6, 430e6, 390e6, 410e6, 430e6, 450e6, 470e6, 490e6], strict=True)
    ]
    assert financial_inputs(mild[-1], mild, entity).get("oneoff_note") is None
