"""Selection diagnostics preserve the real entry guards and PIT missingness."""

import pytest

pytestmark = pytest.mark.phase1_blocking


def score(**kwargs):
    return dict(
        tier="attack",
        books=dict(quality=90, growth=90, valuation=10, timing=90),
        m31_adjusted_valuation=35,
        m32_ok=True,
        tradable=True,
        red_lines=[],
        tech={"price_vs_ma200": 10},
        **kwargs,
    )


def test_diagnostics_use_effective_m31_valuation_and_independent_guards():
    from inves_cog.backtest.selection_gap import score_blockers

    s = score()
    assert "valuation" not in score_blockers(s)
    s["m32_ok"] = False
    s["red_lines"] = ["趋势破位"]
    assert {"m32", "redline"} <= set(score_blockers(s))


def test_relax_one_gate_never_supplies_missing_book_or_removes_redline():
    from inves_cog.backtest.selection_gap import relax_book

    s = score()
    s["books"]["quality"] = None
    s["red_lines"] = ["趋势破位"]
    relaxed = relax_book(s, "valuation", 0)
    assert not relaxed["entry_pass"]
    assert relaxed["books"]["quality"] is None
    assert s["books"]["valuation"] == 10


def test_foreign_issuer_is_explained_separately_from_missing_financial_books():
    from inves_cog.backtest.selection_gap import score_blockers

    s = score()
    s.update(ticker="TSM", tradable=False)
    assert "foreign_issuer" in score_blockers(s)
