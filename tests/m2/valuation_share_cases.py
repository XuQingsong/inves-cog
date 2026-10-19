"""A008 optional valuation denominator: preserve every existing trading field."""

from copy import deepcopy
from datetime import date


def assert_valuation_share_contract(input_facts):
    from inves_cog.ingest.fundamentals.extractors import extract_state
    from inves_cog.ingest.fundamentals.valuation_shares import select_weighted_shares

    day = date(2026, 10, 13)
    raw = input_facts()
    before = deepcopy(raw)
    old = extract_state(raw, ticker="FIXTURE", as_of=day)
    assert old.values["diluted_shares_weighted"] == 100_000_000
    proof = old.field_sources["diluted_shares_weighted"]
    assert proof["period_kind"] == "quarter" and proof["duration_days"] == 91
    assert proof["start"] == "2026-04-01" and proof["end"] == "2026-06-30"
    assert proof["unit"] == "shares" and proof["filed"] == "2026-08-01"
    assert select_weighted_shares(raw, ticker="TSM", as_of=day)[1]["listed_share_ratio"] == 5
    changed = deepcopy(raw)
    rows = changed["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"]
    rows[-1]["val"] = 120_000_000
    new = extract_state(changed, ticker="FIXTURE", as_of=day)
    assert new.values["diluted_shares_weighted"] == 120_000_000
    assert {k: v for k, v in new.values.items() if k != "diluted_shares_weighted"} == {
        k: v for k, v in old.values.items() if k != "diluted_shares_weighted"
    }
    assert {k: v for k, v in new.field_sources.items() if k != "diluted_shares_weighted"} == {
        k: v for k, v in old.field_sources.items() if k != "diluted_shares_weighted"
    }
    assert old.oracle_values == new.oracle_values and raw == before
    assert "diluted_shares_weighted" not in extract_state(raw, ticker="FIXTURE", as_of=day, extractor="legacy").values
    rows.append({**rows[-1], "filed": "2027-01-01", "val": 999})
    value, source = select_weighted_shares(changed, ticker="FIXTURE", as_of=day)
    assert value == 120_000_000 and source["filed"] == "2026-08-01"
    # Do not add classes; prefer a consolidated denominator or a verified D9 class.
    dims = {"us-gaap:StatementClassOfStockAxis": "us-gaap:CommonClassAMember"}
    dimensional = {**rows[-2], "val": 9, "dimensions": dims}
    only = {
        "facts": {"us-gaap": {"WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [dimensional]}}}}
    }
    assert select_weighted_shares(only, ticker="UNKNOWN", as_of=day)[0] is None
    assert select_weighted_shares(only, ticker="V", as_of=day)[0] == 9
    only["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"].append(
        {**dimensional, "dimensions": {}, "val": 12}
    )
    assert select_weighted_shares(only, ticker="V", as_of=day)[0] == 12
    # Raw per-filing basis is preserved; duplicate EPS split observations are not applied to shares.
    split = {**rows[-2], "val": 50, "split_adjustment": [{"ratio": 10}, {"ratio": 10}]}
    only["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"] = [split]
    assert select_weighted_shares(only, ticker="FIXTURE", as_of=day)[0] == 50
    for units in [{"USD": [split]}, {"shares": [{**split, "start": "2026-06-29"}]}, {"shares": [{**split, "val": 0}]}]:
        only["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"] = units
        assert select_weighted_shares(only, ticker="FIXTURE", as_of=day)[0] is None
    raw["facts"]["us-gaap"].pop("WeightedAverageNumberOfDilutedSharesOutstanding")
    assert select_weighted_shares(raw, ticker="FIXTURE", as_of=day)[0] is None, (
        "Ordinary shares and NI/EPS cannot substitute"
    )
    annual = {**split, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-01", "val": 30}
    only["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"] = {"shares": [annual]}
    assert select_weighted_shares(only, ticker="FIXTURE", as_of=day)[1]["period_kind"] == "annual"
