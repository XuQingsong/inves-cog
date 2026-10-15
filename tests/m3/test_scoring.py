"""Rule A contracts, independent expectations and frozen owner-provided oracle."""

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from inves_cog.ingest.fundamentals.state import FinState, StateStore
from tests.harness.tools.golden import load_golden

DAY = date(2026, 10, 9)
ROOT = Path(__file__).resolve().parents[2]


def synthetic(index=0):
    return deepcopy(load_golden("m3_books_synthetic.json")["stocks"][index])


def evaluate(row=None, **kwargs):
    from inves_cog.trading.scoring import score_fields

    row = row or synthetic()
    return score_fields(row["input"]["fields"], row["input"]["tech"], signal_date=DAY, **kwargs)


def compare(actual, expected, path="snapshot"):
    for key, value in expected.items():
        target = actual[key]
        if isinstance(value, dict):
            compare(target, value, path + "." + key)
        elif isinstance(value, (float, int)) and not isinstance(value, bool):
            assert target == pytest.approx(value, abs=1e-6), (path, key, target, value)
        else:
            assert target == value, (path, key, target, value)


@pytest.mark.phase1_blocking
def test_interp_points():
    from inves_cog.trading.scoring.curves import interp, weighted_book

    for curve in load_golden("m3_interp_points.json")["curves"]:
        for row in curve["cases"]:
            assert interp(row["x"], curve["breakpoints"]) == pytest.approx(row["expected"], abs=1e-6)
        assert interp(None, curve["breakpoints"]) is None
        assert interp(float("nan"), curve["breakpoints"]) is None
    assert weighted_book([(0, 40), (100, 60)]) == 60
    assert weighted_book([(None, 40), (100, 60)]) == 100
    assert weighted_book([(None, 100)]) is None


@pytest.mark.phase1_blocking
def test_books_synthetic():
    for row in load_golden("m3_books_synthetic.json")["stocks"]:
        compare(evaluate(row), row["expected"])
    sample = synthetic()
    sample["input"]["fields"]["roe"] = None
    result = evaluate(sample)
    assert result["books"]["quality"] is not None
    assert "roe" in result["missing_fields"]


@pytest.mark.phase1_blocking
def test_red_line_boundaries():
    row = synthetic()
    row["input"]["tech"].update(rsi=80, dev50=15)
    assert "短线过热" not in evaluate(row)["red_lines"]
    row["input"]["tech"].update(rsi=80.01, dev50=15.01)
    assert "短线过热" in evaluate(row)["red_lines"]
    for key in ("price_vs_ma200", "ma50_vs_ma200", "mom6"):
        item = synthetic()
        item["input"]["tech"].update(price_vs_ma200=-1, ma50_vs_ma200=-1, mom6=-10.01)
        assert "趋势破位" in evaluate(item)["red_lines"]
        item["input"]["tech"][key] = 0 if key != "mom6" else -10
        assert "趋势破位" not in evaluate(item)["red_lines"]


@pytest.mark.phase1_blocking
def test_tier_reassess_only_on_filing():
    first = evaluate(state_filed=DAY - timedelta(days=10))
    row = synthetic()
    row["input"]["tech"]["vol60"] = 80
    held = evaluate(row, state_filed=DAY - timedelta(days=10), previous=first)
    assert held["tier"] == first["tier"]
    renewed = evaluate(row, state_filed=DAY, previous={**first, "signal_date": DAY - timedelta(days=1)})
    assert renewed["tier"] == "attack"
    assert renewed["tier_changed_on"] == DAY


@pytest.mark.phase1_blocking
def test_m31_m32():
    from inves_cog.trading.scoring.rules import assign_tier, entry_rules

    books = {"quality": 80, "growth": 90, "valuation": 60, "timing": 80}
    fields = {"rev_growth": 80, "fcf_ttm": -100, "cash": 149}
    result = entry_rules(books, fields, "attack", [])
    assert result["m31_adjusted_valuation"] == 65 and result["gate_pass"]
    assert not result["m32_ok"] and not result["entry_pass"]
    fields["cash"] = 150
    assert entry_rules(books, fields, "attack", ["短线过热"])["entry_pass"]
    assert not entry_rules(books, fields, "attack", ["趋势破位"])["entry_pass"]
    assert entry_rules(books, fields, "normal", [])["m31_adjusted_valuation"] is None
    # Q-M3-11 explicitly retains the v18 valuation-zero truthiness exception.
    assert assign_tier({**books, "valuation": 0}, {"rev_growth": 40}, 40) == "normal"
    assert assign_tier({**books, "valuation": 1}, {"rev_growth": 40}, 40) == "attack"


@pytest.mark.phase1_blocking
def test_stale_books_are_null():
    timeline = json.loads((ROOT / "tests/fixtures/phase1/m3/timeline.json").read_text())
    current = evaluate(period_end=DAY - timedelta(days=timeline["stale_days"][0]))
    assert current["books"]["quality"] is not None
    old = evaluate(period_end=DAY - timedelta(days=timeline["stale_days"][1]))
    assert all(old["books"][key] is None for key in ("quality", "growth", "valuation"))
    assert old["books"]["timing"] is not None and not old["entry_pass"]
    assert json.loads(json.dumps(old["books"]))["quality"] is None
    assert evaluate(health_codes=["q4_missing"], extractor="legacy")["books"]["quality"] is not None
    assert evaluate(health_codes=["q4_missing"])["books"]["quality"] is None
    assert evaluate(health_codes=["extreme_value_verified"])["books"]["quality"] is not None


@pytest.mark.phase1_blocking
def test_split_suspect_valuation_null():
    result = evaluate(health_codes=["split_suspect"])
    assert result["books"]["valuation"] is None and result["books"]["quality"] is not None
    assert evaluate()["books"]["valuation"] is not None


@pytest.mark.phase1_blocking
def test_pit_filed_date():
    from inves_cog.trading.scoring import score_day

    row = synthetic()
    past = FinState("SYN", "fixed", DAY, DAY, values=row["input"]["fields"])
    future = FinState("SYN", "fixed", DAY + timedelta(days=1), DAY, values={"rev_ttm": None})
    store = StateStore([past, future])
    calls = []

    def lookup(*args):
        calls.append(args)
        return store.state_asof(*args)

    result = score_day("SYN", DAY, tech=row["input"]["tech"], state_asof=lookup)
    assert result["books"]["quality"] == row["expected"]["books"]["quality"]
    assert calls == [("SYN", DAY, "fixed")]


@pytest.mark.phase1_blocking
def test_foreign_filers_not_tradable():
    for ticker in ("ASML", "ARM", "TSM", "SKHY", "NOK"):
        result = evaluate(ticker=ticker)
        assert not result["tradable"] and result["books"]["timing"] is not None
    assert evaluate(ticker="AMD")["tradable"]


@pytest.mark.phase1_blocking
def test_rule_set_a_locked():
    assert evaluate(rule_set="A")["rule_set"] == "A"
    with pytest.raises(ValueError):
        evaluate(rule_set="A+")


@pytest.mark.phase1_blocking
def test_v18_constants():
    from inves_cog.trading.scoring.rules import load_rule_a

    params = load_rule_a(ROOT / "config/params/rule_a_v18.yaml")
    assert [v["cap"] for v in params["tiers"].values()] == [0.12, 0.12, 0.08]
    assert [v["first_lot"] for v in params["tiers"].values()] == [0.5, 0.4, 0.3]
    assert [v["budget"] for v in params["tiers"].values()] == [0.3, 0.3, 0.4]


@pytest.mark.phase1_blocking
def test_no_tracker_stops_in_rule_a(tmp_path):
    from inves_cog.trading.scoring.rules import load_rule_a

    raw = (ROOT / "config/params/rule_a_v18.yaml").read_text()
    assert load_rule_a(ROOT / "config/params/rule_a_v18.yaml")
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(raw + "\ntracker_fixed_stops: [-8, -12, -18]\n")
    with pytest.raises(ValueError):
        load_rule_a(invalid)


@pytest.mark.phase1_replay
def test_scores_match_muse():
    from tests.m3.replay_support import compare_frozen

    result = compare_frozen()
    assert result["states"] == 600 and result["mismatches"] == []
