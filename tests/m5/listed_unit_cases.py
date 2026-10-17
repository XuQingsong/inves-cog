"""Explicit units, rather than currency or plausible magnitudes, determine conversion."""

from copy import deepcopy


def assert_listed_units():
    from inves_cog.valuation_v1.listed_units import convert_unit

    relation = {"id": "fixture-ADS-5", "ratio": 5, "known_at": "2026-04-16", "source": "synthetic filing"}
    ordinary = {"unit": "USD/ordinary_share", "known_at": "2026-05-01", "source": "synthetic EPS"}
    original = deepcopy(ordinary)
    value, proof = convert_unit(2, ordinary, relation, "2026-10-15", kind="per_share")
    assert value == 10 and proof["factor"] == 5 and proof["to_unit"] == "USD/ADS"
    assert ordinary == original
    shares = {**ordinary, "unit": "ordinary_shares"}
    assert convert_unit(100, shares, relation, "2026-10-15", kind="shares")[0] == 20
    for kind, unit in [("per_share", "USD/ADS"), ("shares", "ADS"), ("price", "USD/ADS")]:
        assert convert_unit(7, {**ordinary, "unit": unit}, relation, "2026-10-15", kind=kind)[0] == 7
    # Idempotent reuse accepts an explicit already-normalized proof, never applies five twice.
    once = {**ordinary, "unit": "USD/ADS", "listing_conversion": proof}
    assert convert_unit(value, once, relation, "2026-10-15", kind="per_share")[0] == value
    for source, mapping in [
        ({**ordinary, "unit": "USD"}, relation),
        ({**ordinary, "known_at": "2027-01-01"}, relation),
        (ordinary, {**relation, "known_at": "2027-01-01"}),
        ({**ordinary, "listing_conversion": proof}, relation),
        ({**ordinary, "split_event_ids": [relation["id"]]}, relation),
    ]:
        v, audit = convert_unit(2, source, mapping, "2026-10-15", kind="per_share")
        assert v is None and audit["status"] == "unknown" and audit["reason"]
    assert convert_unit(float("nan"), ordinary, relation, "2026-10-15", kind="per_share")[0] is None
    from inves_cog.valuation_v1.calculations import evaluate
    from tests.m5.test_valuation import stable

    blocked = evaluate("稳定", {**stable(), "listed_unit_blockers": [{"field": "eps_ttm", "reason": "unit absent"}]})
    assert blocked["neutral"] is None and any(r["field"] == "eps_ttm" for r in blocked["blocking_inputs"])
    from datetime import date

    from inves_cog.valuation_v1.lifecycle import ValuationBook

    book = ValuationBook()
    plain = {**stable(), "eps_ntm": None, "listed_unit_audit": {"eps_ntm": {"status": "absent"}}}
    before = book.update("LISTED", date(2026, 10, 14), "稳定", plain, period="2026-06-30", price=100)
    missing_unit = book.update(
        "LISTED",
        date(2026, 10, 15),
        "稳定",
        {
            **plain,
            "pe_p50": plain["pe_p50"] * 1.1,
            "listed_unit_audit": {"eps_ntm": {"status": "unknown", "reason": "unit absent"}},
        },
        period="2026-06-30",
        price=110,
    )
    assert missing_unit["neutral"] is not None
    assert missing_unit["inputs"]["listed_unit_audit"]["eps_ntm"]["status"] == "unknown"
    assert missing_unit["trigger_audit"]["unit_contract_event"]
    assert missing_unit["neutral"] == before["neutral"], "forecast audit alone must not refresh historical PE"
    recovered = book.update("LISTED", date(2026, 10, 16), "稳定", plain, period="2026-06-30", price=120)
    assert recovered["neutral"] is not None and recovered["trigger_audit"]["unit_contract_event"]
    # Withdrawing an unusable forecast must not display its old range while
    # waiting for the ordinary >25% change review.
    withdrawal = ValuationBook()
    known = {**plain, "eps_ntm": 1000, "listed_unit_audit": {"eps_ntm": {"status": "known"}}}
    withdrawal.update("WITHDRAW", date(2026, 10, 14), "稳定", known, period="2026-06-30", price=100)
    fallback = withdrawal.update(
        "WITHDRAW",
        date(2026, 10, 15),
        "稳定",
        {**plain, "listed_unit_audit": {"eps_ntm": {"status": "unknown"}}},
        period="2026-06-30",
        price=110,
    )
    assert fallback["inputs"]["eps_ntm"] is None and not fallback["pending_review"]
    assert fallback["trigger_audit"]["invalid_forecast_withdrawn"]
    assert_listing_adapter()


def assert_listing_adapter():
    from datetime import date

    from inves_cog.ingest.fundamentals.state import FinState
    from inves_cog.valuation_v1.calculations import evaluate
    from inves_cog.valuation_v1.listed_units import normalize_listing
    from tests.m5.test_valuation import stable

    state = FinState(
        "TSM",
        "fixed",
        date(2026, 10, 8),
        date(2024, 12, 31),
        values={"diluted_shares_weighted": 100},
        field_sources={
            "eps_ttm": {
                "components": [
                    {"tag": "ifrs-full:DilutedEarningsLossPerShare", "unit": "TWD/shares", "filed": "2025-04-17"}
                ]
            },
            "diluted_shares_weighted": {
                "method": "diluted_weighted_disclosed",
                "unit": "shares",
                "security_basis": "ordinary_shares",
                "period_kind": "annual",
                "end": "2024-12-31",
                "filed": "2025-04-17",
            },
        },
    )
    inputs = {**stable(), "ticker": "TSM", "price": 100, "eps_ttm": 2, "fcf_ttm": 100}
    snapshot = {"as_of": "2026-10-15", "source": "synthetic Yahoo", "earningsCurrency": "USD"}
    unknown = normalize_listing(inputs, state, snapshot, "2026-10-15")
    assert unknown["eps_ttm"] == 10 and unknown["diluted_shares"] == 20 and unknown["price"] == 100
    assert unknown["eps_ntm"] is None and unknown["consensus_next_year_eps_growth"] is None
    assert not unknown["listed_unit_blockers"] and "unit" in unknown["consensus_reason"]
    assert evaluate("稳定", unknown)["neutral"] is not None
    for unit, factor in [("USD/ADS", 1), ("USD/ordinary_share", 5)]:
        known = normalize_listing(inputs, state, {**snapshot, "eps_security_unit": unit}, "2026-10-15")
        assert known["eps_ntm"] == inputs["eps_ntm"] * factor and not known["listed_unit_blockers"]
    bad = deepcopy(state)
    bad.field_sources["eps_ttm"]["components"][0]["unit"] = "USD"
    rejected = normalize_listing(inputs, bad, snapshot, "2026-10-15")
    assert evaluate("稳定", rejected)["neutral"] is None
    future = normalize_listing(inputs, state, snapshot, "2026-03-01")
    assert evaluate("稳定", future)["neutral"] is None
