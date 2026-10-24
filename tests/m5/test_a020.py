from datetime import datetime, timedelta, timezone

import pytest

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def sample():
    # Reduced, artificial values in the provider shape verified against the private
    # NVDA fixture sha256 f68049c50b9d8293376ea527e1bf94b0557f2ab3baef6adf77b09ca1d00c004f.
    return {
        "symbol": "NVDA",
        "estimates": [
            {
                "date": "2028-01-31",
                "horizon": "fiscal year",
                "eps_estimate_average": "15.91",
                "eps_estimate_analyst_count": "52",
                "revenue_estimate_average": "200000000",
            },
            {
                "date": "2027-01-31",
                "horizon": "fiscal year",
                "eps_estimate_average": "9.31",
                "eps_estimate_analyst_count": "51",
                "revenue_estimate_average": "None",
            },
            {
                "date": "2026-12-31",
                "horizon": "fiscal quarter",
                "eps_estimate_average": "-1.25",
                "eps_estimate_analyst_count": "4",
                "revenue_estimate_average": "1200",
            },
        ],
    }


@pytest.mark.phase1_blocking
def test_a020_parse_future_annual_and_quarterly_without_changing_raw():
    from copy import deepcopy

    from inves_cog.valuation_v1.consensus import parse_estimates

    raw = sample()
    before = deepcopy(raw)
    rows = parse_estimates("NVDA", raw, NOW)
    assert raw == before
    assert [(r["horizon"], r["eps_avg"], r["eps_count"]) for r in rows] == [
        ("FY1", 9.31, 51),
        ("FY2", 15.91, 52),
        ("Q1", -1.25, 4),
    ]
    assert rows[0]["revenue_avg"] is None


@pytest.mark.phase1_blocking
def test_a020_rotation_prioritizes_never_then_oldest_with_stable_ties():
    from inves_cog.valuation_v1.consensus import rotation

    assert rotation(["C", "B", "A"], {"A": NOW, "B": NOW - timedelta(days=1)}) == ["C", "B", "A"]
    assert rotation(["B", "A"], {}) == ["A", "B"]


@pytest.mark.phase1_blocking
@pytest.mark.parametrize("field", ["Note", "Information"])
def test_a020_rate_limit_stops_all_remaining_requests(field):
    from inves_cog.clock import FrozenClock
    from inves_cog.valuation_v1.consensus import collect

    class Repo:
        def __init__(self):
            self.reserved = []
            self.saved = []

        def latest(self):
            return {}

        def reserve(self, ticker, now):
            self.reserved.append(ticker)
            return str(len(self.reserved))

        def finish(self, request_id, ticker, now, raw, rows, status):
            self.saved.append((raw, status))

    repo = Repo()
    calls = []

    def fetch(ticker):
        calls.append(ticker)
        return {field: "daily quota reached"}

    result = collect(clock=FrozenClock(NOW), repository=repo, tickers=["A", "B"], fetch=fetch, pause=lambda: None)
    assert calls == ["A"] and repo.reserved == ["A"]
    assert repo.saved == [({field: "daily quota reached"}, "throttled")]
    assert result["status"] == "degraded" and result["request_count"] == 1


@pytest.mark.phase1_blocking
def test_a020_failed_transport_consumes_attempt_and_is_not_retried():
    from inves_cog.clock import FrozenClock
    from inves_cog.valuation_v1.consensus import collect

    class Repo:
        def latest(self):
            return {}

        def reserve(self, ticker, now):
            return "one"

        def finish(self, *args):
            self.saved = args

    calls = []
    repo = Repo()

    def fetch(ticker):
        calls.append(ticker)
        raise TimeoutError("sensitive URL must not enter result")

    result = collect(clock=FrozenClock(NOW), repository=repo, tickers=["A"], fetch=fetch, pause=lambda: None)
    assert calls == ["A"] and result["request_count"] == 1 and result["processed_count"] == 0
    assert "sensitive" not in str(result) and "sensitive" not in str(repo.saved)


@pytest.mark.phase1_blocking
def test_a020_http_client_has_no_retry_redirect_or_unbounded_body(monkeypatch):
    from contextlib import contextmanager

    import httpx

    from inves_cog.valuation_v1.consensus import Client

    calls = []
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: pytest.fail("unbounded get must not be used"))

    @contextmanager
    def stream(*a, **kw):
        calls.append(kw)

        class Response:
            status_code = 200

            def iter_bytes(self):
                yield b'{"Information":"quota"}'

        yield Response()

    monkeypatch.setattr(httpx, "stream", stream)
    response = Client("test-only-placeholder").fetch("NVDA")
    assert response.raw == {"Information": "quota"} and len(calls) == 1
    assert calls[0]["follow_redirects"] is False


@pytest.mark.phase1_blocking
def test_a020_verified_provider_shape_keeps_precision_nulls_and_past_raw():
    from copy import deepcopy

    from inves_cog.valuation_v1.consensus import parse_estimates

    # Sanitized structural fixture, not a copy of the private provider payload.
    # Real server-only verification: 40920 bytes, 41 raw periods -> 2 future FY + 2 Q.
    raw = sample()
    raw["estimates"][0]["eps_estimate_average"] = "15.9146"
    raw["estimates"][1]["eps_estimate_average"] = "9.3124"
    raw["estimates"].extend(
        [
            {**raw["estimates"][2], "date": "2026-10-31", "eps_estimate_average": "1.52"},
            {**raw["estimates"][1], "date": "2026-01-31", "eps_estimate_average": "4.77"},
        ]
    )
    for row in raw["estimates"]:
        row.update(
            {
                "eps_estimate_high": "18.6",
                "eps_estimate_low": "8.2",
                "revenue_estimate_high": "300000000",
                "revenue_estimate_low": "100000000",
                "revenue_estimate_analyst_count": "40",
            }
        )
        row.update({f"eps_estimate_average_{days}_days_ago": "8.9" for days in (7, 30, 60, 90)})
        row.update(
            {
                f"eps_estimate_revision_{direction}_trailing_{days}_days": None
                for direction in ("up", "down")
                for days in (7, 30)
            }
        )
    before = deepcopy(raw)
    rows = parse_estimates("NVDA", raw, NOW)
    assert raw == before and len(raw["estimates"]) == 5
    assert [(r["horizon"], r["eps_avg"], r["eps_count"]) for r in rows] == [
        ("FY1", 9.3124, 51),
        ("FY2", 15.9146, 52),
        ("Q1", 1.52, 4),
        ("Q2", -1.25, 4),
    ]
    assert rows[0]["revenue_avg"] is None
