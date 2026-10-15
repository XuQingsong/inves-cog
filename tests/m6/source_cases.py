"""Sourced single-business and quarterly exposure cases, including rejected inputs."""

from copy import deepcopy
from datetime import date


def assert_source_exceptions(clock):
    from inves_cog.ingest.fundamentals.fx import FXBook
    from inves_cog.perception.graph.source_exposures import quarterly_ttm_source, single_business_hdd

    as_of = date(2026, 10, 15)
    state = {
        "ticker": "STX",
        "extractor": "fixed",
        "filed": date(2026, 8, 4),
        "period_end": date(2026, 7, 3),
        "accession": "annual",
        "form": "10-K",
        "rev_ttm": 123.0,
        "field_sources": {"rev_ttm": {"components": [{"unit": "USD", "end": "2026-07-03"}]}},
    }
    source = single_business_hdd(state, as_of=as_of)
    assert source["revenue"] == 123 and source["evidence"]["source_table"] == "fundamentals.fin_state"
    assert "single_business_consolidated_revenue" in source["evidence"]["flags"]
    for change in (
        {"ticker": "AMD"},
        {"rev_ttm": None},
        {"rev_ttm": float("nan")},
        {"filed": date(2026, 10, 16)},
        {"field_sources": {}},
    ):
        assert single_business_hdd({**state, **change}, as_of=as_of) is None
    foreign = deepcopy(state)
    foreign["field_sources"]["rev_ttm"]["components"][0]["unit"] = "EUR"
    assert single_business_hdd(foreign, as_of=as_of) is None

    quarters = [
        {
            "ticker": "SKHY",
            "accession": str(i),
            "filed": date(2026, 8, 18),
            "period_end": end,
            "revenue": 10.0,
            "currency": "USD",
            "parse_status": "parsed",
            "source_exhibit": "https://www.sec.gov/Archives/fixture",
        }
        for i, end in enumerate([date(2025, 9, 30), date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30)])
    ]
    result = quarterly_ttm_source(quarters, as_of=as_of, fx=FXBook())
    assert result["status"] == "ok" and result["source"]["revenue"] == 40
    assert len(result["source"]["evidence"]["quarters"]) == 4
    # Restatements replace one quarter; they do not become a fifth quarter.
    revision = {**quarters[-1], "accession": "revised", "filed": date(2026, 9, 1), "revenue": 20.0}
    assert quarterly_ttm_source([*quarters, revision], as_of=as_of, fx=FXBook())["source"]["revenue"] == 50
    future = {**revision, "filed": date(2026, 10, 16), "revenue": 999}
    assert quarterly_ttm_source([*quarters, future], as_of=as_of, fx=FXBook())["source"]["revenue"] == 40
    for rows in (
        quarters[:3],
        [*quarters[:2], *quarters[:2]],
        [*quarters[:3], {**quarters[-1], "period_end": date(2026, 9, 30)}],
    ):
        rejected = quarterly_ttm_source(rows, as_of=as_of, fx=FXBook())
        assert rejected["status"] == "无法检验" and rejected["source"] is None
    krw = [{**row, "currency": "KRW"} for row in quarters]
    assert quarterly_ttm_source(krw, as_of=as_of, fx=FXBook())["reason"] == "fx_gap"
    from inves_cog.perception.graph.segments import validate_segment_draft

    draft = {"segment_id": source["row_id"], "exposure_usd": 123, "exposure_basis": "分部收入", "accession": "annual"}
    validated = validate_segment_draft(draft, [source], clock=clock)
    assert "single_business_consolidated_revenue" in validated["flags"]
