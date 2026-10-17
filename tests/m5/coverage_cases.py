"""A008 denominator preference and complete formula-blocker explanations."""

from datetime import date


def assert_coverage_contract():
    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.calculations import calculate
    from inves_cog.valuation_v1.inputs import financial_inputs

    state = FinState(
        ticker="FIXTURE",
        extractor="fixed",
        filed=date(2026, 8, 1),
        period_end=date(2026, 6, 30),
        values={"shares": 999, "diluted_shares_weighted": 12, "fcf_ttm": 120},
        field_sources={
            "shares": {"method": "instant"},
            "diluted_shares_weighted": {
                "method": "diluted_weighted_disclosed",
                "start": "2026-04-01",
                "end": "2026-06-30",
                "filed": "2026-08-01",
                "period_kind": "quarter",
                "duration_days": 91,
                "unit": "shares",
                "security_basis": "consolidated_common_equivalent",
                "accn": "fixture",
            },
        },
    )
    entity = {"ticker": "FIXTURE", "sector": "test"}
    data = financial_inputs(state, [], entity)
    assert data["diluted_shares"] == 12 and data["fcf_per_share"] == 10
    assert state.values["shares"] == 999
    state.field_sources["diluted_shares_weighted"]["end"] = "2025-06-30"
    assert financial_inputs(state, [], entity)["diluted_shares"] is None
    state.field_sources["diluted_shares_weighted"]["end"] = "2026-06-30"
    state.field_sources["diluted_shares_weighted"]["filed"] = "2027-01-01"
    assert financial_inputs(state, [], entity)["diluted_shares"] is None
    # An unproved ADS/ordinary conversion must remain explicit, not divide twice.
    state.field_sources["diluted_shares_weighted"].update(
        filed="2026-08-01", security_basis="ordinary_shares", listed_share_ratio=None
    )
    assert financial_inputs(state, [], {**entity, "foreign": True})["diluted_shares"] is None
    missing = calculate("周期", {})
    assert {r["field"] for r in missing["blocking_inputs"]} == {
        "normal_net_margin",
        "normal_revenue",
        "diluted_shares",
        "cyclical_subindustry_PE_parameters",
    }
    assert {r["field"] for r in calculate("金融", {})["blocking_inputs"]} == {"rote_5y_avg", "tbv_per_share"}
    stable = calculate("稳定", {"eps_ttm": 1})
    assert {r["field"] for r in stable["blocking_inputs"]} == {
        "fcf_ttm",
        "diluted_shares",
        "pe_p25",
        "pe_p50",
        "pe_p75",
    }
    assert calculate("困境", {})["blocking_inputs"] == [], "Intentional non-valuation is not an ingestion defect"
    assert_annual_basis_history()


def assert_annual_basis_history():
    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.inputs import financial_inputs

    rows = []
    for year in range(2018, 2026):
        rows.append(
            FinState(
                ticker="FOREIGN",
                extractor="fixed",
                filed=date(year + 1, 3, 1),
                period_end=date(year, 12, 31),
                form="6-K",
                health_codes=["annual_basis"],
                values={"rev_ttm": 100, "ni_ttm": 10, "eps_ttm": 1},
                field_sources={
                    "rev_ttm": {
                        "components": [
                            {
                                "start": f"{year}-01-01",
                                "end": f"{year}-12-31",
                                "filed": f"{year + 1}-03-01",
                                "accn": f"annual-{year}",
                            }
                        ]
                    }
                },
            )
        )
    out = financial_inputs(rows[-1], rows, {"ticker": "FOREIGN", "sector": "半导体设备", "foreign": True})
    assert len(out["annual_sequence"]) == 8 and out["normal_net_margin"] == 0.1
    assert out["normal_revenue"] == 100
    # An actual quarterly interim or an unproved annual label is not annual history.
    rows[0].health_codes = ["interim_unaudited"]
    rows[1].field_sources["rev_ttm"]["components"][0]["start"] = "2019-10-01"
    out = financial_inputs(rows[-1], rows, {"ticker": "FOREIGN", "sector": "半导体设备", "foreign": True})
    assert len(out["annual_sequence"]) == 6 and out["normal_net_margin"] is None
