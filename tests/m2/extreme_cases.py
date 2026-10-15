"""Original-statement verification must never become an issuer-wide waiver."""

from copy import deepcopy
from datetime import date


def assert_verified_extremes():
    from inves_cog.ingest.fundamentals.cli import current_ciks

    history = [
        {"ticker": "XOM", "cik": "34088", "filing_date": date(2026, 5, 1), "accession": "old"},
        {"ticker": "XOM", "cik": "2115436", "filing_date": date(2026, 7, 1), "accession": "new"},
    ]
    assert current_ciks(history, as_of=date(2026, 6, 30))["XOM"] == "34088"
    assert current_ciks(list(reversed(history)), as_of=date(2026, 10, 15))["XOM"] == "2115436"
    from inves_cog.ingest.fundamentals.health import health_row
    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.ingest.fundamentals.verification import apply_verification, inline_facts

    raw = """<html><xbrli:context id="main"><xbrli:entity></xbrli:entity>
    <xbrli:period><xbrli:startdate>2025-01-01</xbrli:startdate><xbrli:enddate>2025-12-31</xbrli:enddate></xbrli:period>
    </xbrli:context>
    <ix:nonfraction name="us-gaap:NetIncomeLoss" contextref="main" scale="6" sign="-">200</ix:nonfraction>
    <ix:nonfraction name="us-gaap:Revenues" contextref="main" scale="6">100</ix:nonfraction>
    <ix:nonfraction name="us-gaap:EarningsPerShareDiluted" contextref="main" sign="-">20</ix:nonfraction></html>"""
    original = inline_facts(raw, source_url="https://www.sec.gov/Archives/fixture.html")
    state = FinState(
        "SYN",
        "fixed",
        date(2026, 2, 1),
        date(2025, 12, 31),
        values={"ni_ttm": -200e6, "rev_ttm": 100e6, "eps_ttm": -20, "shares": 10e6},
        health_codes=["implausible_value"],
        field_sources={"implausible_value": {"violations": [{"rule": 1}, {"rule": 3, "field": "ni"}]}},
    )
    fixed = apply_verification(state, original, reason="Original statement confirms the exceptional loss")
    assert "extreme_value_verified" in fixed.health_codes and "implausible_value" not in fixed.health_codes
    assert health_row(fixed)["can_score"] and "Original statement" in health_row(fixed)["reason"]
    altered = deepcopy(state)
    altered.values["ni_ttm"] = -201e6
    assert "implausible_value" in apply_verification(altered, original, reason="test").health_codes
    wrong_period = deepcopy(state)
    wrong_period.period_end = date(2025, 9, 30)
    assert "implausible_value" in apply_verification(wrong_period, original, reason="test").health_codes
    legacy = deepcopy(state)
    legacy.extractor = "legacy"
    assert apply_verification(legacy, original, reason="test").health_codes == legacy.health_codes
    assert original["source_sha256"] and all(not row["dimensions"] for row in original["facts"])
