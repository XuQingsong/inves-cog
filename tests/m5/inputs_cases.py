"""PIT data-contract assertions shared by the prescribed acceptance names."""

from datetime import date, datetime, timezone


def assert_inputs():
    from inves_cog.valuation_v1.inputs import consensus_inputs, diluted_shares

    row = {
        "as_of": date(2026, 10, 8),
        "captured_at": datetime(2026, 10, 8, 10, tzinfo=timezone.utc),
        "eps_cy": 6,
        "eps_ny": 12,
        "rev_cy": 100,
        "rev_ny": 160,
        "fy_cy": date(2026, 12, 31),
        "fy_ny": date(2027, 12, 31),
    }
    a = consensus_inputs([row], date(2026, 10, 8))
    assert a["eps_ntm"] == 11 and a["rev_ntm_consensus"] == 150
    assert a["consensus_next_year_eps_growth"] == 100
    assert consensus_inputs([row], date(2026, 10, 7))["eps_ntm"] is None
    assert (
        consensus_inputs([{**row, "captured_at": datetime(2026, 10, 10, tzinfo=timezone.utc)}], date(2026, 10, 8))[
            "eps_ntm"
        ]
        is None
    )
    assert consensus_inputs([{**row, "fy_cy": date(2025, 12, 31)}], date(2026, 10, 8))["eps_ntm"] is None
    broken = {**row, "as_of": date(2026, 10, 9), "eps_cy": None, "eps_ny": None}
    assert consensus_inputs([row, broken], date(2026, 10, 9))["eps_ntm"] is None
    assert (
        diluted_shares(10, {"method": "instant", "components": [{"tag": "dei:EntityCommonStockSharesOutstanding"}]})
        is None
    )
    assert diluted_shares(12, {"method": "diluted_weighted_approximation"}) == 12
