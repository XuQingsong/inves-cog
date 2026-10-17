"""Explicit units, rather than currency or plausible magnitudes, determine conversion."""

from copy import deepcopy

import pytest


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

    blocked = evaluate("稳定", {**stable(), "listed_unit_blockers": [{"field": "eps_ntm", "reason": "unit absent"}]})
    assert blocked["neutral"] is None and any(r["field"] == "eps_ntm" for r in blocked["blocking_inputs"])
