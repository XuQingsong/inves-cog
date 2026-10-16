"""Registered predecessor facts supplement fixed history without replacing current facts."""

from copy import deepcopy
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.fundamentals.service import FinancialService, MemoryRepository
from tests.m2.test_fundamentals import extract, input_facts

pytestmark = pytest.mark.phase1_blocking


def test_successor_companyfacts_history_uses_visible_registrant():
    calls, inputs = [], []
    records = {
        "34088": [{"filed": "2015-02-20", "val": 1e9, "accn": "old"}],
        "2115436": [{"filed": "2026-08-03", "val": 2e9, "accn": "new"}],
    }

    class SEC:
        def companyfacts(self, cik):
            key = str(int(cik))
            calls.append(key)
            return {"cik": key, "facts": {"us-gaap": {"Revenues": {"units": {"USD": deepcopy(records[key])}}}}}

    repo = MemoryRepository()
    repo.shared_filings["XOM"] = [
        {"accession": "old", "form": "10-K", "filing_date": date(2015, 2, 20), "cik": "0000034088"},
        # SEC publishes the same accession under both CIKs. The local index may retain the old CIK.
        {"accession": "new", "form": "10-Q", "filing_date": date(2026, 8, 3), "cik": "34088"},
        {"accession": "8k", "form": "8-K", "filing_date": date(2026, 9, 25), "cik": "0002115436"},
    ]

    def compute(data, **kwargs):
        inputs.append((kwargs["extractor"], deepcopy(data)))
        state = extract()
        state.ticker = "XOM"
        visible = [
            r for r in data["facts"]["us-gaap"]["Revenues"]["units"]["USD"] if r["filed"] <= str(kwargs["as_of"])
        ]
        state.values["rev_ttm"] = max(visible, key=lambda r: r["filed"])["val"] if visible else None
        return state

    service = FinancialService(
        clock=FrozenClock(datetime(2026, 10, 16, 1, tzinfo=timezone.utc)),
        repository=repo,
        sec=SEC(),
        llm=None,
        universe=[{"ticker": "XOM", "foreign": False, "sector": "能源"}],
        ciks={"XOM": "0002115436"},
    )
    with patch("inves_cog.ingest.fundamentals.service.extract_state", side_effect=compute):
        assert service.collect_financials()["processed_count"] == 1
    assert repo.state_asof("XOM", date(2015, 2, 20), "fixed").values["rev_ttm"] == 1e9
    assert repo.state_asof("XOM", date(2026, 10, 16), "fixed").values["rev_ttm"] == 2e9
    assert all(
        data["facts"]["us-gaap"]["Revenues"]["units"]["USD"] == records["2115436"]
        for mode, data in inputs
        if mode == "legacy"
    )
    assert calls == ["2115436", "34088"]
    assert all(
        not r.get("d9_only")
        for mode, data in inputs
        if mode == "fixed"
        for r in data["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    )
    calls.clear()
    with patch("inves_cog.ingest.fundamentals.service.extract_state", side_effect=compute):
        service.collect_financials(history=False)
    assert calls == ["2115436", "34088"]


def test_current_and_historical_quarters_survive_registered_cik_merge():
    full = input_facts()
    pieces = {}
    for cik, newer in [("34088", False), ("2115436", True)]:
        data = deepcopy(full)
        data["cik"] = cik
        for node in data["facts"]["us-gaap"].values():
            for unit, rows in node["units"].items():
                node["units"][unit] = [r for r in rows if (r["filed"] >= "2026-08-01") == newer]
        pieces[cik] = data

    class SEC:
        def companyfacts(self, cik):
            return deepcopy(pieces[str(int(cik))])

    repo = MemoryRepository()
    repo.shared_filings["XOM"] = [
        {"accession": "prior", "form": "10-Q", "filing_date": date(2026, 5, 2), "cik": "34088"},
        {"accession": "shared", "form": "10-Q", "filing_date": date(2026, 8, 1), "cik": "34088"},
    ]
    service = FinancialService(
        clock=FrozenClock(datetime(2026, 10, 16, 1, tzinfo=timezone.utc)),
        repository=repo,
        sec=SEC(),
        llm=None,
        universe=[{"ticker": "XOM", "foreign": False, "sector": "能源"}],
        ciks={"XOM": "2115436"},
    )
    assert service.collect_financials()["processed_count"] == 1
    for cutoff in [date(2026, 5, 2), date(2026, 8, 1)]:
        expected = extract(full, as_of=cutoff)
        actual = repo.state_asof("XOM", cutoff, "fixed")
        for key in ("rev_ttm", "ni_ttm", "eps_ttm"):
            assert actual.values[key] == expected.values[key]
