"""B-032: the 2026-10-20 null reasons follow the existing price rules.

The natural market_structure job wrote 1,289 rows per session. 1,253 of them
carry a null reason. These examples keep that classification attached to the
code path. They do not fill in a price or lower the 60-day window.
"""

from datetime import date, timedelta

import numpy as np
import pytest

CLOSE_COUNTS = {
    "missing_current_return": 1087,
    "sector_unmapped;missing_current_return": 141,
    "l3_same_as_l2": 23,
    "insufficient_history": 2,
}
POST_COUNTS = {
    "missing_post_price": 1089,
    "sector_unmapped;missing_post_price": 141,
    "l3_same_as_l2": 23,
}
OBJECTS = 1289


def _bars(tickers, days, *, adj_factor=1.0, post_close=True, blank_last_factor=False, blank_post=False):
    first = date(2024, 1, 2)
    rows = []
    for j, ticker in enumerate(tickers):
        price = 100.0
        for i in range(days):
            price *= 1 + 0.004 * np.sin(i / (3 + j)) + 0.001
            last = i == days - 1
            factor = None if blank_last_factor and last else adj_factor
            post = None if blank_post or not post_close else price * 1.001
            rows.append(
                {
                    "ticker": ticker,
                    "trade_date": first + timedelta(days=i),
                    "close": price,
                    "adj_factor": factor,
                    "post_close": post,
                }
            )
    return rows, first + timedelta(days=days - 1)


def _basket(level, names, basis=None):
    return {
        "basket_id": level.lower(),
        "level": level,
        "name": level,
        "members": [{"ticker": name, "primary": True} for name in names],
        "factor_basis": basis or {"kind": "market"},
        "benchmark": "SPY",
    }


def _daily(result, ticker, session):
    return next(row for row in result["daily"] if row["ticker"] == ticker and row["session"] == session)


@pytest.mark.phase1_blocking
def test_published_null_counts_match_one_session():
    assert sum(CLOSE_COUNTS.values()) == OBJECTS - 36
    assert sum(POST_COUNTS.values()) == OBJECTS - 36
    assert POST_COUNTS["missing_post_price"] == (
        CLOSE_COUNTS["missing_current_return"] + CLOSE_COUNTS["insufficient_history"]
    )


@pytest.mark.phase1_blocking
def test_close_without_adjustment_is_missing_current_return_not_a_filled_price():
    from inves_cog.marketstate.engine import calculate

    bars, day = _bars(["SPY", "A", "B", "C"], 200, blank_last_factor=True)
    result = calculate(bars, [_basket("L2", ["A", "B", "C"])], [], day=day, tickers=["A"], sic_etfs={})
    row = _daily(result, "A", "close")
    assert row["ret"] is None
    assert row["resid"] is None
    assert row["null_reason"] == "missing_current_return"


@pytest.mark.phase1_blocking
def test_missing_post_price_replaces_the_close_reason():
    from inves_cog.marketstate.engine import calculate

    bars, day = _bars(["SPY", "A", "B", "C"], 200, blank_post=True)
    result = calculate(bars, [_basket("L2", ["A", "B", "C"])], [], day=day, tickers=["A"], sic_etfs={})
    close = _daily(result, "A", "close")
    post = _daily(result, "A", "post")
    assert close["resid"] is not None and close["null_reason"] is None
    assert post["ret"] is None and post["resid"] is None
    assert post["null_reason"] == "missing_post_price"


@pytest.mark.phase1_blocking
def test_unmapped_name_keeps_sector_reason_beside_the_missing_return():
    from inves_cog.marketstate.engine import calculate

    bars, day = _bars(["SPY", "WIDE"], 80, blank_last_factor=True)
    result = calculate(bars, [], [], day=day, tickers=["WIDE"], sic_etfs={})
    row = _daily(result, "WIDE", "close")
    assert row["null_reason"] == "sector_unmapped;missing_current_return"
    assert row["resid"] is None


@pytest.mark.phase1_blocking
def test_same_theme_and_sector_still_keeps_a_residual():
    from inves_cog.marketstate.engine import calculate

    bars, day = _bars(["SPY", "A", "B", "C"], 200)
    baskets = [
        _basket("L2", ["A", "B", "C"]),
        _basket("L3", ["A", "B", "C"], {"kind": "l2", "sector": "L2"}),
    ]
    result = calculate(bars, baskets, [], day=day, tickers=["A"], sic_etfs={})
    row = _daily(result, "A", "close")
    assert row["null_reason"] == "l3_same_as_l2"
    assert row["ret"] is not None and row["resid"] is not None


@pytest.mark.phase1_blocking
def test_short_history_stays_insufficient_without_lowering_the_window():
    from inves_cog.marketstate.engine import calculate

    bars, day = _bars(["SPY", "A", "B", "C"], 20)
    result = calculate(bars, [_basket("L2", ["A", "B", "C"])], [], day=day, tickers=["A"], sic_etfs={})
    row = _daily(result, "A", "close")
    assert row["null_reason"] == "insufficient_history"
    assert row["resid"] is None
