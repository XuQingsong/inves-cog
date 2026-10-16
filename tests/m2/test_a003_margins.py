"""D-27: direct medical costs must not disappear from an insurer's cost basis."""

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from inves_cog.ingest.fundamentals.extractors import extract_state

pytestmark = pytest.mark.phase1_blocking
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/phase1/m2"


def facts():
    return json.loads((FIXTURES / "a003/unh-cost-components.json").read_text())


def extract(data, **kwargs):
    return extract_state(data, ticker="UNH", as_of=date(2026, 10, 16), price=300, sic=6324, **kwargs)


def ttm(data, tag):
    rows = data["facts"]["us-gaap"][tag]["units"]["USD"]

    def value(start, end):
        choices = [r for r in rows if r.get("start") == start and r["end"] == end]
        return max(choices, key=lambda r: r["filed"])["val"]

    return value("2025-01-01", "2025-12-31") + value("2026-01-01", "2026-06-30") - value("2025-01-01", "2025-06-30")


def test_unh_gross_profit_includes_medical_and_product_costs():
    data = facts()
    revenue = ttm(data, "Revenues")
    product_cost = ttm(data, "CostOfGoodsAndServicesSold")
    medical_cost = ttm(data, "PolicyholderBenefitsAndClaimsIncurredNet")
    expected = (revenue - product_cost - medical_cost) / revenue * 100
    state = extract(data, extractor="fixed")
    assert state.values["gross_margin"] == pytest.approx(expected)
    assert "gross_margin_derived" in state.health_codes
    assert not state.values.get("split_suspect", False)
    assert "PolicyholderBenefitsAndClaimsIncurredNet" in str(state.field_sources["gross_margin"])


@pytest.mark.parametrize("missing", [True, False])
def test_unh_incomplete_medical_costs_cannot_produce_high_margin(missing):
    data = facts()
    nodes = data["facts"]["us-gaap"]
    if missing:
        nodes.pop("PolicyholderBenefitsAndClaimsIncurredNet")
    else:
        for row in nodes["PolicyholderBenefitsAndClaimsIncurredNet"]["units"]["USD"]:
            row["end"] = (date.fromisoformat(row["end"]) - timedelta(days=2)).isoformat()
    state = extract(data, extractor="fixed")
    assert state.values["gross_margin"] is None
    assert "gross_margin_costs_incomplete" in state.health_codes
    assert "medical" in state.field_sources["gross_margin"]["reason"].lower()


def test_unh_reported_gross_profit_takes_precedence():
    data = json.loads((FIXTURES / "companyfacts_synthetic.json").read_text())
    state = extract(data, extractor="fixed")
    assert state.values["gross_margin"] == pytest.approx(40)
    assert "gross_margin_costs_incomplete" not in state.health_codes


def test_other_issuer_cost_derivation_is_unchanged():
    data = json.loads((FIXTURES / "companyfacts_synthetic.json").read_text())
    data["facts"]["us-gaap"].pop("GrossProfit")
    state = extract_state(data, ticker="OTHER", as_of=date(2026, 10, 16), extractor="fixed")
    assert state.values["gross_margin"] == pytest.approx(40)
    assert "gross_margin_costs_incomplete" not in state.health_codes


def test_unh_legacy_does_not_inherit_fixed_cost_repair():
    state = extract(deepcopy(facts()), extractor="legacy")
    assert state.values["gross_margin"] is None
