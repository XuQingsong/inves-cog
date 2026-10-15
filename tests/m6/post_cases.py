"""Session coverage and review validation assertions, attached to existing test names."""

from datetime import date, timedelta

import numpy as np
import pytest


def assert_post_outputs():
    from inves_cog.marketstate.engine import calculate

    first = date(2025, 1, 1)
    tickers = ["SPY", "A", "B", "C"]
    bars = []
    for j, ticker in enumerate(tickers):
        price = 100.0
        for i in range(200):
            price *= 1 + 0.004 * np.sin(i / (3 + j)) + 0.001 * j
            bars.append(
                {
                    "ticker": ticker,
                    "trade_date": first + timedelta(days=i),
                    "close": price,
                    "adj_factor": 1.0,
                    "post_close": price * (1 + 0.001 * np.cos(i / (4 + j))),
                }
            )
    basket = {
        "basket_id": "test",
        "level": "L2",
        "name": "test",
        "members": [{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}],
        "factor_basis": {"kind": "market"},
        "benchmark": "SPY",
    }
    day = first + timedelta(days=199)
    result = calculate(bars, [basket], [], day=day, tickers=["A", "B", "C"], sic_etfs={})
    assert {r["session"] for r in result["baskets"]} == {"close", "post"}
    assert {r["session"] for r in result["rotation"]} == {"close", "post"}
    after = [r for r in result["daily"] if r["ticker"] == "A" and r["session"] == "post"][0]
    assert after["resid"] is not None and after["resid_5d"] is not None
    missing_bars = [{**r, "post_close": None} for r in bars]
    missing = calculate(missing_bars, [basket], [], day=day, tickers=["A", "B", "C"], sic_etfs={})
    assert all(
        r["resid"] is None and "missing_post_price" in r["health_codes"]
        for r in missing["daily"]
        if r["session"] == "post"
    )
    assert all(r["ret_ew"] is None for r in missing["baskets"] if r["session"] == "post")
    assert all(r["ret"] is None for r in missing["rotation"] if r["session"] == "post")


def assert_review_edits(clock):
    from inves_cog.perception.graph.review import ReviewQueue

    queue = ReviewQueue(clock=clock, rows=[{"relation_id": "edit", "status": "候选", "exposure_usd": 123}])
    with pytest.raises(ValueError):
        queue.review(["edit"], action="modify", edits={"edit": {"unrecognized_field": True}})
    with pytest.raises(ValueError):
        queue.review(["edit"], action="modify", edits={"edit": {"exposure_usd": -1}})
    queue.review(["edit"], action="modify", edits={"edit": {"direction": "负", "strength": "强"}})
    assert queue.candidates()[0]["direction"] == "负"
