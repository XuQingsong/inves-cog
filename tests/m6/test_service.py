"""The public daily entry must preserve its requested price universe (D-32)."""

from datetime import date, datetime, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.marketstate import service


@pytest.mark.phase1_blocking
def test_market_service_preserves_requested_tickers(monkeypatch):
    requested = ["NVDA", "AMD", "MSFT"]
    seen = {}

    class Rows:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Repository:
        def query(self, sql, params=None):
            if "issuer_profiles" in sql:
                return Rows([{"ticker": "SHW", "sic": 3674}, {"ticker": "BKNG", "sic": 3674}])
            if "bars_daily" in sql:
                seen["queried_tickers"] = params[2]
            return Rows([])

        def vix(self):
            return []

    def calculate(bars, baskets, vix, *, day, tickers, sic_etfs):
        seen["tickers"] = list(tickers)
        seen["sic_etfs"] = sic_etfs
        return {"daily": [{"ticker": t} for t in tickers], "baskets": [], "rotation": [], "market": {}}

    monkeypatch.setattr(service, "calculate", calculate)
    clock = FrozenClock(datetime(2026, 10, 16, 1, tzinfo=timezone.utc))
    runner = service.MarketService(repository=Repository(), clock=clock)
    written = []
    monkeypatch.setattr(runner, "put", lambda table, row: written.append((table, row)))
    result = runner.run(date(2026, 10, 15), tickers=requested)

    assert seen["tickers"] == requested, "SIC overrides must not replace the requested universe"
    assert requested == ["NVDA", "AMD", "MSFT"]
    assert set(requested) <= set(seen["queried_tickers"])
    assert seen["sic_etfs"] == {"SHW": "XLB", "BKNG": "XLY"}, "Ticker-specific SIC overrides still apply"
    assert result["coverage"] == result["expected"] == 3
    assert {row["ticker"] for table, row in written if table == "daily"} == set(requested)
