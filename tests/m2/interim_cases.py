"""Frozen SEC 6-K originals: issuer rules, reported/adjusted and PIT boundaries."""

import gzip
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1] / "fixtures/phase1/m2/interims"
CASES = {
    "ASML": ("0001628280-26-065813", "2026-10-14", "2026-09-27", "EUR", [11662, 6699.8, 5172.8, 4960.4], 12.93),
    "TSM": ("0001046179-26-000451", "2026-07-16", "2026-06-30", "TWD", [1270381, 860311, 766603, 706562], 27.25),
    "NOK": ("0001104659-26-086081", "2026-07-23", "2026-06-30", "EUR", [4815, 2146, -50, 2], 0),
    "ARM": ("0001973239-26-000114", "2026-07-29", "2026-06-30", "USD", [1289, 1253, 91, 270], .25),
}


def assert_interim_parsers():
    from inves_cog.ingest.fundamentals.interims import parse_interim

    for ticker, (accession, filed, end, currency, amounts, eps) in CASES.items():
        raw = gzip.decompress((ROOT / (ticker + ".html.gz")).read_bytes()).decode()
        rows = parse_interim(raw, ticker=ticker, accession=accession, filed=filed, source_exhibit="https://www.sec.gov/" + accession)
        row = next(r for r in rows if str(r["period_end"]) == end)
        assert row["parse_status"] == "parsed", row
        assert row["currency"] == currency and row["eps_diluted"] == eps
        assert [row[k] for k in ("revenue", "gross_profit", "operating_income", "net_income")] == pytest.approx([v * 1e6 for v in amounts])
        assert "ordinary" in row["eps_basis"] and "ADS" in row["eps_basis"]
        # These are entirely different financial figures, never substitutes.
        if ticker == "NOK":
            assert row["net_income"] != 5e6 and row["operating_income"] != 434e6
        if ticker == "ARM":
            assert row["eps_diluted"] != 1078
        bad = parse_interim("unrelated shareholder meeting", ticker=ticker, accession=accession, filed=filed, source_exhibit="fixture")
        assert bad[0]["parse_status"].startswith("interim_unparsed:")
        assert bad[0]["revenue"] is None

    raw = gzip.decompress((ROOT / "SKHY.html.gz").read_bytes()).decode()
    row = parse_interim(raw, ticker="SKHY", accession="0001193125-26-321989", filed="2026-07-29", source_exhibit="fixture")[0]
    assert str(row["period_end"]) == "2026-06-30" and row["revenue"] == 79318746e6
    assert row["parse_status"].startswith("interim_unparsed:") and "gross_profit" in row["parse_status"]
    assert row["gross_profit"] is None and row["eps_diluted"] is None


def assert_interim_pit():
    from inves_cog.ingest.fundamentals.interims import apply_interims
    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.ingest.fundamentals.health import health_row

    state = FinState(ticker="TSM", extractor="fixed", filed=date(2026, 4, 16), period_end=date(2025, 12, 31), accession="annual", form="20-F", fiscal_period="FY", values={"rev_ttm": 100, "ni_ttm": 10, "eps_ttm": 1, "shares": 100}, field_sources={}, health_codes=["annual_basis", "stale_fundamentals"])
    rows = []
    for end in ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]:
        rows.append(dict(ticker="TSM", accession="quarter", filed=date(2026, 7, 16), period_end=date.fromisoformat(end), currency="TWD", revenue=100, gross_profit=60, operating_income=50, net_income=40, eps_diluted=2, eps_basis="ordinary; ADS=5 ordinary", source_exhibit="fixture", parse_status="parsed"))

    class Rates:
        def convert(self, value, **kwargs):
            assert kwargs["start"] is not None and kwargs["as_of"] == date(2026, 10, 15)
            return value / 20, {"fixture": True, "currency": kwargs["currency"]}

    assert apply_interims(state, rows, as_of=date(2026, 7, 15), fx=None).values == state.values
    result = apply_interims(state, rows, as_of=date(2026, 10, 15), fx=Rates())
    assert result.values["rev_ttm"] == 20 and result.values["eps_ttm"] == .4
    assert result.values["gross_margin"] == 60 and result.period_end == date(2026, 6, 30)
    assert "interim_unaudited" in result.health_codes and "stale_fundamentals" not in result.health_codes
    assert not health_row(result, foreign=True)["can_trade"]
    assert result.field_sources["interim_ttm"]["annual_accession"] == "annual"
    # Missing quarters and partial announcements never masquerade as full TTM.
    assert apply_interims(state, rows[1:], as_of=date(2026, 10, 15), fx=Rates()).values["rev_ttm"] == 100
    partial = deepcopy(rows)
    partial[-1]["parse_status"] = "interim_unparsed:missing net_income"
    assert apply_interims(state, partial, as_of=date(2026, 10, 15), fx=Rates()).values["rev_ttm"] == 100
    legacy = deepcopy(state)
    legacy.extractor = "legacy"
    assert apply_interims(legacy, rows, as_of=date(2026, 10, 15), fx=Rates()).values == state.values
