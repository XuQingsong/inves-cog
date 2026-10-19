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
        source["bars"]["NVDA"] = [
            {**b, "trade_date": date.fromisoformat(b["trade_date"])} for b in peer["bars"]
        ]
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


def assert_a012_stale_annual_basis():
    row = real_build("TSM")
    # The 2026-09-24 retained 6-K state explicitly anchors the 2025 annual;
    # a later-loaded 20-F state falls back to 2024. Never publish it as current.
    assert row["status"] == "unvalued"
    assert "2025-12-31" in row["reason"] and "2024-12-31" in row["reason"]
