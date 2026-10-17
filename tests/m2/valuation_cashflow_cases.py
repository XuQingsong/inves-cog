"""Synthetic period/filing contracts; no real financial source payload."""

from copy import deepcopy
from datetime import date


def cashflows():
    pairs = [
        ("2025-04-01", "2026-03-31", "2026-05-26", 100, 20),
        ("2026-04-01", "2026-06-30", "2026-07-29", 25, 5),
        ("2025-04-01", "2025-06-30", "2026-07-29", 10, 2),
    ]
    facts = {}
    for tag, pos in [
        ("NetCashProvidedByUsedInOperatingActivities", 3),
        ("PaymentsToAcquirePropertyPlantAndEquipment", 4),
    ]:
        facts[tag] = {
            "units": {
                "USD": [
                    dict(start=r[0], end=r[1], filed=r[2], accn=r[2], form="20-F" if i == 0 else "6-K", val=r[pos])
                    for i, r in enumerate(pairs)
                ]
            }
        }
    return {"facts": {"us-gaap": facts}}


def assert_valuation_cashflow_contract():
    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.ingest.fundamentals.valuation_cashflow import attach_valuation_cashflow, select_cashflow

    original = cashflows()
    value, proof = select_cashflow(original, period_end="2026-06-30", as_of="2026-09-23")
    assert value == 92 and proof["ocf"] == 115 and proof["capex"] == 23
    assert [r["coefficient"] for r in proof["components"]] == [1, 1, -1]
    assert proof["period_end"] == "2026-06-30" and proof["period_kind"] == "ttm"
    assert cashflows() == original
    assert select_cashflow(original, period_end="2026-03-31", as_of="2026-05-26")[0] == 80
    for change in ["missing", "end", "future", "currency", "scope"]:
        data = deepcopy(original)
        cap = data["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"]
        if change == "missing":
            cap["USD"].pop()
        if change == "end":
            cap["USD"][-1]["end"] = "2025-06-29"
        if change == "future":
            cap["USD"][-1]["filed"] = "2027-01-01"
        if change == "currency":
            cap["EUR"] = cap.pop("USD")
        if change == "scope":
            data["facts"]["us-gaap"]["NetCashUsedInInvestingActivities"] = data["facts"]["us-gaap"].pop(
                "PaymentsToAcquirePropertyPlantAndEquipment"
            )
        missing, why = select_cashflow(data, period_end="2026-06-30", as_of="2026-09-23")
        assert missing is None and why["reason"] and why["missing_periods"]
    state = FinState(
        "ARM",
        "fixed",
        date(2026, 9, 23),
        date(2026, 6, 30),
        values={"fcf_ttm": None, "shares": 7, "eps_ttm": 2},
        health_codes=["interim_unaudited"],
    )
    old = deepcopy(vars(state))
    attach_valuation_cashflow(state, original, as_of=state.filed)
    assert state.values["valuation_fcf_ttm"] == 92
    current = deepcopy(vars(state))
    for k in ["values", "field_sources"]:
        current[k].pop("valuation_fcf_ttm")
    assert current == old
    other = deepcopy(state)
    other.ticker = "OTHER"
    other.values.pop("valuation_fcf_ttm")
    other.field_sources.pop("valuation_fcf_ttm")
    attach_valuation_cashflow(other, original, as_of=other.filed)
    assert "valuation_fcf_ttm" not in other.values
