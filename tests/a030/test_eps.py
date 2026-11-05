from datetime import date

import pytest

from inves_cog.ingest.fundamentals.extractors import extract_state


def facts(value, **extra):
    rows = [
        dict(start=start, end=end, filed="2026-02-01", val=value, form="10-K", accn="test-2026", **extra)
        for start, end in [
            ("2025-01-01", "2025-03-31"),
            ("2025-04-01", "2025-06-30"),
            ("2025-07-01", "2025-09-30"),
            ("2025-10-01", "2025-12-31"),
        ]
    ]
    return {"facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": rows}}}}}


def test_class_eps_only_fills_missing_company_periods_with_source_marker():
    dimensional = facts(
        2,
        origin="instance_parsed",
        d9_only=True,
        dimensions={"us-gaap:StatementClassOfStockAxis": "us-gaap:CommonClassAMember"},
    )
    base = facts(1)
    present = extract_state(base, ticker="V", as_of=date(2026, 3, 1), instance_facts=dimensional)
    assert present.values["eps_ttm"] == 4
    missing = extract_state({"facts": {}}, ticker="V", as_of=date(2026, 3, 1), instance_facts=dimensional)
    assert missing.values["eps_ttm"] == 8
    components = missing.field_sources["eps_ttm"]["components"]
    assert all(r.get("origin") == "instance_class_eps_fallback" for r in components)
    old = extract_state({"facts": {}}, ticker="V", as_of=date(2026, 1, 1), instance_facts=dimensional)
    assert old.values["eps_ttm"] is None


pytestmark = pytest.mark.phase1_blocking
