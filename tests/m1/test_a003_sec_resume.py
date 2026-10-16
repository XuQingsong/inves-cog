"""A single SEC issuer failure must not restart or terminate the whole universe."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.http import SourceError
from inves_cog.ingest.pipeline import Pipeline

pytestmark = pytest.mark.phase1_blocking


class Repository:
    def __init__(self):
        self.cursors = {}

    def get_cursor(self, key):
        return deepcopy(self.cursors.get(key))

    def set_cursor(self, key, value, stamp):
        self.cursors[key] = deepcopy(value)

    def filings(self, ticker):
        return {}

    def closes(self, ticker):
        return []

    def write(self, *args, **kwargs):
        pass

    def info_signature(self, key):
        return None

    def supersede_fallback(self, *args):
        pass


def pipeline(monkeypatch, collect):
    p = Pipeline.__new__(Pipeline)
    p.clock = FrozenClock(datetime(2026, 10, 17, 0, 50, tzinfo=timezone.utc))
    p.repo, p.sec, p.stocks, p.values, p.day_override = Repository(), object(), ["ONE", "TWO"], {}, None
    monkeypatch.setattr("inves_cog.ingest.pipeline.cik_mapping", lambda sec: {"ONE": "1", "TWO": "2"})
    monkeypatch.setattr("inves_cog.ingest.pipeline.collect_submissions", collect)
    return p


def test_sec_issuer_failure_isolated_and_next_run_only_resumes_failed_issuer(monkeypatch):
    calls = []
    failing = {"ONE"}

    def collect(sec, *, ticker, **kwargs):
        calls.append(ticker)
        if ticker in failing:
            raise SourceError("recorded connection interruption", error_code="ReadTimeout")
        return []

    p = pipeline(monkeypatch, collect)
    result = p.submissions()
    assert calls == ["ONE", "TWO"]
    assert result["status"] == "degraded" and not result["source_success"]
    assert result["failed_companies"][0]["ticker"] == "ONE"
    checkpoint = p.repo.cursors["sec-submissions-progress"]
    assert checkpoint["completed"] == ["TWO"]
    assert checkpoint["failures"]["ONE"]["error_code"] == "ReadTimeout"
    calls.clear()
    failing.clear()
    result = p.submissions()
    assert calls == ["ONE"]
    assert result["completed_companies"] == 2 and result["source_success"]
    assert result["failed_companies"] == []
    calls.clear()
    p.submissions()
    assert calls == []


def test_sec_document_failure_is_inside_company_boundary(monkeypatch):
    calls = []

    class SEC:
        def get(self, url):
            raise SourceError("recorded body transport failure", error_code="ConnectTimeout")

    def collect(sec, *, ticker, **kwargs):
        calls.append(ticker)
        if ticker == "TWO":
            return []
        return [
            {
                "accession": "0000000001-26-000001",
                "ticker": "ONE",
                "cik": "1",
                "form": "8-K",
                "filing_date": date(2026, 10, 15),
                "report_date": None,
                "items": ["2.02"],
                "accepted_at": datetime(2026, 10, 15, 20, tzinfo=timezone.utc),
                "primary_document": "report.htm",
                "raw": {},
            }
        ]

    p = pipeline(monkeypatch, collect)
    p.sec = SEC()
    result = p.submissions()
    assert calls == ["ONE", "TWO"]
    assert result["status"] == "degraded"
    assert result["failed_companies"][0]["ticker"] == "ONE"
    assert p.repo.cursors["sec-submissions-progress"]["completed"] == ["TWO"]


def test_sec_completed_cycle_refreshes_on_next_trade_date(monkeypatch):
    calls = []

    def collect(sec, *, ticker, **kwargs):
        calls.append(ticker)
        return []

    p = pipeline(monkeypatch, collect)
    p.submissions()
    calls.clear()
    p.clock = FrozenClock(datetime(2026, 10, 18, 0, 50, tzinfo=timezone.utc))
    p.submissions()
    assert calls == ["ONE", "TWO"]


def test_sec_permission_failure_is_not_misreported_as_a_company_gap(monkeypatch):
    def collect(sec, **kwargs):
        raise PermissionError("database write denied")

    p = pipeline(monkeypatch, collect)
    with pytest.raises(PermissionError, match="database write denied"):
        p.submissions()


def test_sec_reuses_transport_without_splitting_the_shared_rate_budget():
    from inves_cog.ingest.sec_client import SECClient

    first = SECClient(user_agent="offline fixture fixture@example.invalid")
    second = SECClient(user_agent="offline fixture fixture@example.invalid")
    assert first.http.pool and second.http.pool
    assert first.budget is second.budget
    assert first.budget.count == 5 and first.budget.seconds == 1
