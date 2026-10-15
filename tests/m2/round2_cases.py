"""Round-two regressions under the existing collected test names."""
from datetime import date


def assert_long_quarters():
    from inves_cog.ingest.fundamentals.extractors import Facts
    data = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"start": "2025-09-01", "end": "2025-12-22", "filed": "2026-01-10", "val": 10},
        {"start": "2025-09-01", "end": "2025-12-31", "filed": "2026-01-10", "val": 11},
    ]}}}}}
    assert len(Facts(data, date(2026, 2, 1), fixed=True).quarterly(["Revenues"])) == 1
    assert not Facts(data, date(2026, 2, 1), fixed=False).quarterly(["Revenues"])


def assert_d9(input_facts):
    from inves_cog.ingest.fundamentals.extractors import extract_state
    data = input_facts()
    gaap = data["facts"]["us-gaap"]
    gaap["RevenuesNetOfInterestExpense"] = gaap.pop("RevenueFromContractWithCustomerExcludingAssessedTax")
    result = extract_state(data, ticker="JPM", as_of=date(2026, 10, 13))
    assert result.values["rev_ttm"] == 400
    assert extract_state(data, ticker="JPM", as_of=date(2026, 10, 13), switches={"D9": False}).values["rev_ttm"] is None
    assert extract_state(data, ticker="JPM", as_of=date(2026, 10, 13), extractor="legacy").values["rev_ttm"] is None


def assert_recent_gaps(input_facts):
    from inves_cog.ingest.fundamentals.extractors import extract_state
    data = input_facts()
    data["facts"]["us-gaap"]["OperatingIncomeLoss"]["units"]["USD"].append(
        {"start":"2026-01-01", "end":"2026-12-31", "filed":"2027-01-10", "val": 100, "fp":"FY", "form":"10-K"})
    result = extract_state(data, ticker="FIXTURE", as_of=date(2027, 1, 20))
    assert "q4_missing" not in result.health_codes
    data["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"].append(
        {"start":"2026-01-01", "end":"2026-12-31", "filed":"2027-01-10", "val": 400, "fp":"FY", "form":"10-K"})
    assert "q4_missing" in extract_state(data, ticker="FIXTURE", as_of=date(2027, 1, 20)).health_codes


def assert_yahoo_page(clock):
    import json
    from inves_cog.ingest.fundamentals.providers import tables_from_yahoo_page
    data = {"earningsTrend": {"trend":[{"period":"0y", "earningsEstimate":{"avg":{"raw":4.5},"numberOfAnalysts":{"raw":12}},"revenueEstimate":{"avg":{"raw":100}},"epsRevisions":{"upLast7days":{"raw":2}}}]}}
    html = '<script type="application/json">' + json.dumps(data) + '</script>'
    tables = tables_from_yahoo_page(html)
    assert tables["earnings_estimate"]["0y"]["avg"] == 4.5
    assert tables["revenue_estimate"]["0y"]["avg"] == 100
    assert tables["eps_revisions"]["0y"]["upLast7days"] == 2
    try: tables_from_yahoo_page('<html>Request blocked</html>')
    except ValueError: pass
    else: raise AssertionError("A blocked page must not become an empty snapshot")
