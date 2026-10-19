"""TSM's public build entry must consume only the optional aligned annual basis."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest


def assert_tsm_annual_build():
    from inves_cog.clock import FrozenClock
    from inves_cog.ingest.fundamentals.fx import FXBook
    from inves_cog.ingest.fundamentals.state import StateStore
    from inves_cog.ingest.fundamentals.valuation_annual import attach_valuation_annual
    from inves_cog.valuation_v1.service import build
    from tests.m2.tsm_valuation_cases import carrier, recording
    from tests.m5.review_cases import ReviewRepository

    repo = ReviewRepository(peers=True)
    data, tsm = recording(), carrier()
    attach_valuation_annual(tsm, data["facts"], filing=data["filing"], fx=FXBook(data["fx"]), as_of=tsm.filed)
    from inves_cog.valuation_v1.listed_units import historical_eps

    assert historical_eps(tsm, "TSM", date(2026, 10, 15)) == pytest.approx(2.1043409144073206 * 5)
    original = deepcopy(vars(tsm))
    day = date(2026, 10, 15)
    source = repo.inputs(day, ["AAA", "BBB"])
    source["states"] = {"TSM": [tsm], "BBB": [repo.states[1]]}
    source["store"] = StateStore([tsm, repo.states[1]])
    source["bars"]["TSM"] = source["bars"].pop("AAA")
    source["consensus"]["TSM"] = []
    source["baskets"][0]["members"][0]["ticker"] = "TSM"
    output = build(
        clock=FrozenClock(datetime(2026, 10, 16, 2, 30, tzinfo=timezone.utc)),
        repository=repo,
        universe=[{"ticker": "TSM", "sector": "半导体制造", "foreign": True}, {"ticker": "BBB", "sector": "test"}],
        as_of=day,
        persist=False,
        source=source,
    )
    row = output["ranges"][0]
    assert row["status"] == "ok", row
    assert row["inputs"]["financial_period"] == "2025-12-31"
    assert row["inputs"]["eps_ttm"] == pytest.approx(2.1043409144073206 * 5)
    assert row["inputs"]["fcf_ttm"] == pytest.approx(32224511368.36515)
    assert row["inputs"]["diluted_shares"] == 25930600000 / 5
    assert row["inputs"]["fcf_per_share"] == pytest.approx(32224511368.36515 / (25930600000 / 5))
    assert row["source_evidence"]["financial"]["valuation_annual_basis"]["known_at"] == "2026-04-17"
    assert row["inputs"]["annual_sequence"][-1]["period_end"] == "2025-12-31"
    assert vars(tsm) == original, "Projection must not modify the Rule A source"
