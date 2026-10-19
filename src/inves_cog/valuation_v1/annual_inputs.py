"""Project an opt-in annual valuation state, without altering M2/Rule A history."""

from copy import deepcopy

from inves_cog.ingest.fundamentals.extractors import day
from inves_cog.ingest.fundamentals.state import FinState


def valuation_state(state, as_of):
    if state is None or state.ticker != "TSM" or "valuation_annual_basis" not in state.values:
        return state
    data = state.values["valuation_annual_basis"]
    proof = state.field_sources.get("valuation_annual_basis", {})
    if data is None:
        raise ValueError("TSM annual valuation input: " + proof.get("reason", "original annual input invalid"))
    if proof.get("known_at", "9999") > str(as_of)[:10]:
        return state
    if (
        data.get("contract") != "tsm_disclosed_annual_v1"
        or data.get("ticker") != "TSM"
        or data.get("extractor") != "fixed"
        or data.get("period_end") != proof.get("period_end")
        or data.get("accession") != proof.get("accession")
        or data.get("known_at") != proof.get("known_at")
        or data.get("filed") != proof.get("known_at")
        or data.get("form") != "20-F"
    ):
        raise ValueError("TSM annual valuation input proof mismatch")
    projected = FinState(**{k: deepcopy(data[k]) for k in FinState.__dataclass_fields__})
    projected.filed, projected.period_end = day(projected.filed), day(projected.period_end)
    projected.field_sources["valuation_annual_basis"] = {
        **deepcopy(proof),
        "carrier_filed": str(state.filed),
        "carrier_period_end": str(state.period_end),
    }
    return projected


def valuation_history(state, rows):
    if state is not None and "valuation_annual_basis" in state.field_sources:
        return [*rows, state]
    return rows
