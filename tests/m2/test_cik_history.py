"""A successor registrant must not erase the predecessor's PIT financial history."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.fundamentals.service import FinancialService, MemoryRepository
from tests.m2.test_fundamentals import extract

pytestmark = pytest.mark.phase1_blocking


def test_successor_companyfacts_history_uses_visible_registrant():
    calls = []

    class SEC:
        def companyfacts(self, cik):
            calls.append(str(int(cik)))
            return {"cik": str(int(cik)), "facts": {}}

    repo = MemoryRepository()
    repo.shared_filings["XOM"] = [
        {"accession": "old", "form": "10-K", "filing_date": date(2015, 2, 20), "cik": "0000034088"},
        {"accession": "old-q", "form": "10-Q", "filing_date": date(2026, 5, 1), "cik": "34088"},
        {"accession": "new", "form": "10-Q", "filing_date": date(2026, 8, 3), "cik": "0002115436"},
    ]
    source_at_cutoff = []

    def compute(data, **kwargs):
        source_at_cutoff.append((kwargs["extractor"], kwargs["as_of"], data["cik"]))
        state = extract()
        state.ticker = "XOM"
        state.values["rev_ttm"] = 1e9 if data["cik"] == "34088" else 2e9
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
        cik == "34088" for mode, cutoff, cik in source_at_cutoff if mode == "fixed" and cutoff < date(2026, 7, 1)
    )
    assert calls.count("34088") == 1 and calls.count("2115436") == 1
    calls.clear()
    source_at_cutoff.clear()
    with patch("inves_cog.ingest.fundamentals.service.extract_state", side_effect=compute):
        service.collect_financials(history=False)
    # The existing D9 repair still needs predecessor evidence, once; the daily
    # snapshots themselves remain the current registrant rather than a history rebuild.
    assert calls == ["2115436", "34088"]
    assert all(cik == "2115436" for _, _, cik in source_at_cutoff)


def test_current_financial_source_does_not_follow_nonfinancial_successor_filings():
    calls = []

    class SEC:
        def companyfacts(self, cik):
            calls.append(str(int(cik)))
            return {"cik": str(int(cik)), "facts": {}}

    repo = MemoryRepository()
    repo.shared_filings["XOM"] = [
        {"accession": "old-q", "form": "10-Q", "filing_date": date(2026, 8, 3), "cik": "0000034088"},
        {"accession": "new-8k", "form": "8-K", "filing_date": date(2026, 9, 25), "cik": "0002115436"},
    ]

    def compute(data, **kwargs):
        state = extract()
        state.ticker = "XOM"
        state.values["rev_ttm"] = 1e9 if data["cik"] == "34088" else 2e9
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
        assert service.collect_financials(history=False)["processed_count"] == 1
    assert repo.state_asof("XOM", date(2026, 10, 16), "fixed").values["rev_ttm"] == 1e9
    assert calls == ["34088"]
