"""Retained TSM annual input: aligned valuation data without changing Rule A."""

import gzip
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest


def recording():
    path = Path(__file__).resolve().parents[1] / "fixtures/phase1/m2/tsm-valuation-annual.json.gz"
    return json.loads(gzip.decompress(path.read_bytes()))


def carrier():
    from inves_cog.ingest.fundamentals.state import FinState

    return FinState(
        "TSM",
        "fixed",
        date(2026, 10, 8),
        date(2024, 12, 31),
        accession="old-companyfacts",
        form="20-F",
        values={
            "eps_ttm": 1.39160875,
            "fcf_ttm": 27108500000,
            "shares": 25929700000,
            "rev_ttm": 90000000000,
            "ni_ttm": 30000000000,
        },
        field_sources={"interim_ttm": {"annual_period_end": "2025-12-31"}},
        health_codes=["annual_basis"],
    )


def assert_tsm_annual_input():
    from inves_cog.ingest.fundamentals.fx import FXBook, FXGap
    from inves_cog.ingest.fundamentals.valuation_annual import attach_valuation_annual

    data, state = recording(), carrier()
    original = deepcopy(vars(state))
    attach_valuation_annual(state, data["facts"], filing=data["filing"], fx=FXBook(data["fx"]), as_of=state.filed)
    annual = state.values["valuation_annual_basis"]
    assert annual["period_end"] == "2025-12-31" and annual["known_at"] == "2026-04-17"
    assert annual["values"]["eps_ttm"] == pytest.approx(2.1043409144073206)
    assert annual["values"]["fcf_ttm"] == pytest.approx(32224511368.36515)
    assert annual["values"]["diluted_shares_weighted"] == 25930600000
    eps = annual["field_sources"]["eps_ttm"]["components"][-1]
    assert eps["fx"]["method"] == "daily_mean" and eps["fx"]["series"] == "DEXTAUS"
    assert eps["original_value"] == 65.47, "Do not use the convenience USD column"
    unchanged = deepcopy(vars(state))
    for key in ["values", "field_sources"]:
        unchanged[key].pop("valuation_annual_basis")
    assert unchanged == original
    for t, extractor in [("ARM", "fixed"), ("TSM", "legacy")]:
        other = carrier()
        other.ticker, other.extractor = t, extractor
        attach_valuation_annual(other, data["facts"], filing=data["filing"], fx=FXBook(data["fx"]), as_of=state.filed)
        assert "valuation_annual_basis" not in other.values
    early = carrier()
    attach_valuation_annual(early, data["facts"], filing=data["filing"], fx=FXBook(data["fx"]), as_of=date(2026, 4, 16))
    assert "valuation_annual_basis" not in early.values
    tag = "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
    for change in ["period", "accession", "dimension", "future", "missing", "conflict"]:
        facts = deepcopy(data["facts"])
        rows = facts["facts"]["ifrs-full"][tag]["units"]["TWD"]
        row = next(r for r in rows if r["end"] == "2025-12-31")
        if change == "period":
            row["start"] = "2025-07-01"
        if change == "accession":
            row["accn"] = "another-filing"
        if change == "dimension":
            row["dimensions"] = {"axis": "segment"}
        if change == "future":
            row["filed"] = "2027-01-01"
        if change == "missing":
            rows.remove(row)
        if change == "conflict":
            rows.append({**row, "val": row["val"] + 1})
        rejected = carrier()
        attach_valuation_annual(rejected, facts, filing=data["filing"], fx=FXBook(data["fx"]), as_of=state.filed)
        assert rejected.values["valuation_annual_basis"] is None
        assert rejected.field_sources["valuation_annual_basis"]["reason"]
    with pytest.raises(FXGap, match="TWD"):
        attach_valuation_annual(carrier(), data["facts"], filing=data["filing"], fx=FXBook(), as_of=state.filed)
