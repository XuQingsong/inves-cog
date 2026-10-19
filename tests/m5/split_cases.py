"""K05 source-unit contracts; synthetic amounts, fixed public action identities."""

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from inves_cog.ingest.fundamentals.state import FinState


def annual(year, eps, *, source=None, ticker="NVDA"):
    filed, end = date(year, 2, 28), date(year, 1, 28)
    return FinState(
        ticker=ticker,
        extractor="fixed",
        filed=filed,
        period_end=end,
        form="10-K",
        values={
            "eps_ttm": eps,
            "ni_ttm": 100,
            "fcf_ttm": 80,
            "rev_ttm": 100 * 2 ** (year - 2022),
            "gross_margin": {2022: 65, 2023: 45, 2024: 70, 2025: 75, 2026: 76}[year],
            "rev_growth": 40,
        },
        field_sources={
            "eps_ttm": {"components": [source or {"filed": str(filed), "end": str(end), "accn": f"synthetic-{year}"}]}
        },
    )


def assert_canonical_eps_units():
    from inves_cog.valuation_v1.calculations import settings
    from inves_cog.valuation_v1.eps_units import normalize_eps
    from inves_cog.valuation_v1.inputs import financial_inputs
    from inves_cog.valuation_v1.lifecycle import classify

    states = [annual(y, e) for y, e in [(2022, 3.85), (2023, 1.74), (2024, 11.93), (2025, 2.94), (2026, 4.9)]]
    entity = {"ticker": "NVDA", "sector": "test"}
    out = financial_inputs(states[-1], states, entity)
    assert out["annual_eps"] == pytest.approx([0.385, 0.174, 1.193, 2.94, 4.9])
    assert classify(out) == "成长"
    assert financial_inputs(states[-1], states, entity) == out, "Same-day repeats are deterministic and non-mutating"
    before = financial_inputs(states[2], states, entity)
    assert before["annual_eps"] == [3.85, 1.74, 11.93]
    assert financial_inputs(states[2], states[:3], entity) == before, "Later reports never enter an earlier input"
    # Announced on May22, effective June7 16:01 NY, then a later earnings filing.
    for instant, expected in [
        (datetime(2024, 6, 7, 20, 0, tzinfo=timezone.utc), 11.93),
        (datetime(2024, 6, 7, 20, 2, tzinfo=timezone.utc), 1.193),
    ]:
        row = financial_inputs(states[2], states, entity, as_of=instant)
        assert row["annual_eps"][-1] == pytest.approx(expected)

    events = [e for e in settings()["eps_units"]["events"] if e["ticker"] == "NVDA"]
    alias1 = {
        "ratio": 10,
        "event_date": "2024-05-31",
        "first_reported": "2024-08-28",
        "accession": "0001045810-24-000264",
    }
    alias2 = {
        "ratio": 10,
        "event_date": "2024-06-30",
        "first_reported": "2025-05-28",
        "accession": "0001045810-25-000116",
    }
    raw = {
        "filed": "2024-02-21",
        "end": "2024-01-28",
        "accn": "original-before-split",
        "split_adjustment": [alias1, alias2],
    }
    source = deepcopy(raw)
    value, audit = normalize_eps(0.1193, {"components": [source]}, events, date(2026, 2, 28))
    assert value == pytest.approx(1.193)  # The upstream chain divided twice, restore one duplicate factor.
    assert source == raw and audit["status"] == "known"
    assert audit["target_event_ids"] == ["NVDA-split-2021-07-19-4", "NVDA-split-2024-06-07-10"]
    # A later comparative EPS is already restated even though its period predates the split.
    restated = {"filed": "2024-08-28", "end": "2024-01-28", "accn": "0001045810-24-000264"}
    value, audit = normalize_eps(1.193, {"components": [restated]}, events, date(2026, 2, 28))
    assert value == pytest.approx(1.193) and audit["remaining_factor"] == 1
    # A future alias in an already-selected source is invalid provenance, not advance knowledge.
    value, audit = normalize_eps(0.1193, {"components": [source]}, events, date(2024, 10, 1))
    assert value is None and audit["status"] == "unknown" and "future" in audit["reason"]
    unknown = {**restated, "split_adjustment": [{**alias1, "accession": "unrecognized-action"}]}
    value, audit = normalize_eps(1.193, {"components": [unknown]}, events, date(2026, 2, 28))
    assert value is None and "unrecognized" in audit["reason"]
    assert classify({**out, "annual_eps_basis_unknown": True}) == "未确定"
    assert classify({**out, "annual_eps_basis_unknown": True, "subindustry": "存储"}) == "周期"
    assert classify({**out, "annual_eps_basis_unknown": True, "ni_ttm": -1, "rev_growth": 20}) == "未盈利成长"
    assert classify({**out, "ticker": "ANOTHER", "annual_eps_basis_unknown": False}) == "成长"
    # Latest four quarter sources algebraically cancel the exact three Q4 deductions.
    # Their duplicate adjustment chains cannot contaminate the surviving annual source.
    qs = [{**raw, "end": f"2023-{month}-28"} for month in ["04", "07", "10"]]
    q4 = {"derivation": "eps_q4_derived", "end": "2024-01-28", "inputs": [restated, *deepcopy(qs)]}
    value, audit = normalize_eps(1.193, {"components": [*qs, q4]}, events, date(2026, 2, 28))
    assert value == pytest.approx(1.193) and audit["cancelled_terms"] == 3
    # Missing or mixed source basis is explicit; an unaffected issuer keeps its original value.
    assert normalize_eps(2, {}, [], date(2026, 2, 28))[0] == 2
    assert normalize_eps(2, {}, events, date(2026, 2, 28))[0] is None
