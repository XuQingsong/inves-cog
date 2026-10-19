"""A012 real issuer input regressions exercised through the public build entry."""

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.fundamentals.state import FinState, StateStore
from inves_cog.valuation_v1.lifecycle import ValuationBook
from inves_cog.valuation_v1.service import build
from tests.m5.review_cases import ReviewRepository


def real_build(ticker, *, mutate=None):
    path = Path(__file__).resolve().parents[1] / "fixtures/phase1/m5/a012_real_inputs.json"
    case = next(c for c in json.loads(path.read_text())["cases"] if c["ticker"] == ticker)
    case = deepcopy(case)
    if mutate:
        mutate(case)
    states = [
        FinState(
            **{
                **row,
                "filed": date.fromisoformat(row["filed"]),
                "period_end": date.fromisoformat(row["period_end"]),
            }
        )
        for row in case["states"]
    ]
    source = {
        "states": {ticker: states},
        "store": StateStore(states),
        "bars": {ticker: [{**b, "trade_date": date.fromisoformat(b["trade_date"])} for b in case["bars"]]},
        "consensus": {},
        "baskets": [],
    }
    universe = [case["entity"]]
    if ticker == "TSM":
        peer = next(c for c in json.loads(path.read_text())["cases"] if c["ticker"] == "NVDA")
        peer_states = [
            FinState(
                **{**r, "filed": date.fromisoformat(r["filed"]), "period_end": date.fromisoformat(r["period_end"])}
            )
            for r in peer["states"]
        ]
        source["states"]["NVDA"] = peer_states
        source["store"] = StateStore([*states, *peer_states])
        source["bars"]["NVDA"] = [{**b, "trade_date": date.fromisoformat(b["trade_date"])} for b in peer["bars"]]
        source["baskets"] = [
            {"name": "real-case-peer", "level": "L2", "members": [{"ticker": "TSM"}, {"ticker": "NVDA"}]}
        ]
        universe.append(peer["entity"])
    result = build(
        clock=FrozenClock(datetime(2026, 10, 16, 2, 30, tzinfo=timezone.utc)),
        repository=ReviewRepository(),
        universe=universe,
        as_of=date(2026, 10, 15),
        persist=False,
        book=ValuationBook(),
        source=source,
    )
    return next(r for r in result["ranges"] if r["ticker"] == ticker)


def assert_a012_historical_split_units():
    row = real_build("NVDA")
    # Raw M1 close 128.28 on 2024-07-03 is post 10:1 split; the then-visible
    # 2024-05-29 TTM EPS 17.09 is pre-split. The other raw pair is 2016-11-17.
    expected = (92.39 / 1.52 + 128.28 / 1.709) / 2
    assert row["candidate_inputs"]["own_p50"] == pytest.approx(expected)
    from inves_cog.valuation_v1.pe_units import historical_multiples

    # A same-day pre-split raw close must keep its matching EPS unit; the
    # existing event becomes active only on the first adjusted trading day.
    state = FinState(
        ticker="NVDA",
        extractor="fixed",
        filed=date(2024, 5, 29),
        period_end=date(2024, 4, 28),
        values={"eps_ttm": 17.09},
        field_sources={"eps_ttm": {"components": [{"filed": "2024-05-29", "accn": "real-unit-example"}]}},
    )
    source = {
        "store": StateStore([state]),
        "bars": {
            "NVDA": [
                {"trade_date": date(2024, 6, 7), "close": 1208.88},
                {"trade_date": date(2024, 6, 10), "close": 121.788},
            ]
        },
    }
    fixed, baseline = historical_multiples(source, "NVDA", date(2024, 6, 11))
    assert fixed["own_p50"] == pytest.approx((1208.88 / 17.09 + 121.788 / 1.709) / 2)
    assert fixed["historical_pe_unit_audit"]["changed_samples"] == 1
    assert baseline["own_p50"] != fixed["own_p50"]
    state.filed = date(2024, 8, 28)
    state.values["eps_ttm"] = 1.709
    state.field_sources["eps_ttm"] = {"components": [{"filed": "2024-08-28", "accn": "0001045810-24-000264"}]}
    source = {"store": StateStore([state]), "bars": {"NVDA": [{"trade_date": date(2024, 9, 3), "close": 108}]}}
    fixed, baseline = historical_multiples(source, "NVDA", date(2024, 9, 4))
    assert fixed["own_p50"] == baseline["own_p50"], "Already restated EPS must not be split twice"


def assert_a012_stale_annual_basis():
    row = real_build("TSM")
    # The 2026-09-24 retained 6-K state explicitly anchors the 2025 annual;
    # a later-loaded 20-F state falls back to 2024. Never publish it as current.
    assert row["status"] == "unvalued"
    assert "2025-12-31" in row["reason"] and "2024-12-31" in row["reason"]
    from inves_cog.valuation_v1.pe_units import annual_basis_errors

    path = Path(__file__).resolve().parents[1] / "fixtures/phase1/m5/a012_real_inputs.json"
    case = next(c for c in json.loads(path.read_text())["cases"] if c["ticker"] == "TSM")
    states = [
        FinState(**{**r, "filed": date.fromisoformat(r["filed"]), "period_end": date.fromisoformat(r["period_end"])})
        for r in case["states"]
    ]
    current = max(states, key=lambda s: s.filed)
    assert not annual_basis_errors(current, states, "ANOTHER", date(2026, 10, 15))
    assert not annual_basis_errors(current, [current], "TSM", date(2026, 10, 15))
    future = deepcopy(min(states, key=lambda s: s.filed))
    future.filed = date(2026, 11, 1)
    assert not annual_basis_errors(current, [current, future], "TSM", date(2026, 10, 15))
    # A new quality blocker must also invalidate a previously published range,
    # without a new filing/forecast/month event to accidentally trigger it.
    book = ValuationBook()
    inputs = {"eps_ttm": 7, "pe_p25": 20, "pe_p50": 20, "pe_p75": 20, "fcf_per_share": 5}
    book.update("TSM", date(2026, 10, 14), "稳定", inputs, period="2024-12-31", price=420)
    updated = book.update(
        "TSM",
        date(2026, 10, 15),
        "稳定",
        {**inputs, "valuation_input_errors": annual_basis_errors(current, states, "TSM", date(2026, 10, 15))},
        period="2024-12-31",
        price=422,
    )
    assert updated["status"] == "unvalued" and updated["trigger_audit"]["input_contract_event"]
