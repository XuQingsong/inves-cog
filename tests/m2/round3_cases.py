"""Round-three boundaries: source selection, share bases and blocking diagnostics."""

from copy import deepcopy
from datetime import date


def assert_source_selection():
    from inves_cog.ingest.fundamentals.extractors import Facts, repair_flow

    rows = [
        {"start": "2025-01-01", "end": "2025-03-31", "filed": "2025-05-01", "form": "10-Q", "val": 10},
        {"start": "2025-04-01", "end": "2025-06-30", "filed": "2025-08-01", "form": "10-Q", "val": 20},
        {"start": "2025-07-01", "end": "2025-09-30", "filed": "2025-11-01", "form": "10-Q", "val": 30},
        {"start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-01", "form": "10-K", "fp": "FY", "val": 100},
        {"start": "2025-01-01", "end": "2025-12-31", "filed": "2026-03-01", "form": "DEF 14A", "fp": "FY", "val": -900},
    ]
    data = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": rows}}}}}
    facts = Facts(data, date(2026, 3, 2), fixed=True)
    series = facts.quarterly(["NetIncomeLoss"])
    repair_flow(facts, ["NetIncomeLoss"], series)
    assert series[date(2025, 12, 31)]["val"] == 40
    legacy = Facts(data, date(2026, 3, 2), fixed=False)
    assert any(r["form"] == "DEF 14A" for r in legacy.entries("us-gaap", "NetIncomeLoss"))
    rows.append({"start": "2025-01-01", "end": "2025-09-30", "filed": "2025-11-01", "form": "10-Q", "val": 60})
    rows.append({"start": "2025-01-01", "end": "2025-03-31", "filed": "2026-03-02", "form": "10-Q", "val": 20})
    revised = Facts(data, date(2026, 3, 3), fixed=True)
    updated = revised.quarterly(["NetIncomeLoss"])
    repair_flow(revised, ["NetIncomeLoss"], updated)
    assert updated[date(2025, 12, 31)]["val"] == 30  # old YTD9 must not override restated Q1


def assert_split_basis():
    from inves_cog.ingest.fundamentals.extractors import Facts

    rows = [
        {"start": "2025-01-01", "end": "2025-03-31", "filed": "2025-05-01", "form": "10-Q", "val": -0.4},
        {"start": "2025-04-01", "end": "2025-06-30", "filed": "2025-08-01", "form": "10-Q", "val": 0.2},
    ]
    data = {
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {"units": {"USD/shares": rows}},
                "StockholdersEquityNoteStockSplitConversionRatio1": {
                    "units": {"pure": [{"end": "2025-06-01", "filed": "2025-08-01", "form": "10-Q", "val": 4}]}
                },
            }
        }
    }
    before = Facts(data, date(2025, 5, 2), fixed=True).quarterly(["EarningsPerShareDiluted"])
    assert before[date(2025, 3, 31)]["val"] == -0.4
    after = Facts(data, date(2025, 8, 2), fixed=True).quarterly(["EarningsPerShareDiluted"])
    assert after[date(2025, 3, 31)]["val"] == -0.1
    assert after[date(2025, 6, 30)]["val"] == 0.2
    assert after[date(2025, 3, 31)]["split_adjustment"][0]["ratio"] == 4
    assert Facts(data, date(2025, 8, 2)).quarterly(["EarningsPerShareDiluted"])[date(2025, 3, 31)]["val"] == -0.4

    import json
    from pathlib import Path

    from inves_cog.ingest.fundamentals.extractors import extract_state

    official = json.loads((Path(__file__).parents[1] / "fixtures/phase1/m2/round3_official.json").read_text())
    lite = extract_state(official["LITE"], ticker="LITE", as_of=date(2026, 10, 15))
    assert lite.values["ni_ttm"] == -6_935_100_000
    assert lite.values["eps_ttm"] == -92.96
    assert "implausible_value" in lite.health_codes
    crowd = extract_state(official["CRWD"], ticker="CRWD", as_of=date(2026, 10, 15))
    assert crowd.values["ni_ttm"] == 44_995_000
    assert abs(crowd.values["eps_ttm"] - 0.05) < 1e-12


def assert_multi_class(input_facts):
    from inves_cog.ingest.fundamentals.extractors import extract_state

    data = input_facts()
    gaap = data["facts"]["us-gaap"]
    gaap["WeightedAverageNumberOfDilutedSharesOutstanding"] = {
        "units": {
            "shares": [{"start": "2026-07-01", "end": "2026-09-30", "filed": "2026-10-10", "form": "10-Q", "val": 1900}]
        }
    }
    out = extract_state(data, ticker="V", as_of=date(2026, 10, 13))
    assert out.values["shares"] == 1900
    assert out.field_sources["shares"]["method"] == "multi_class_diluted"
    assert extract_state(data, ticker="V", as_of=date(2026, 10, 13), switches={"D9": False}).values["shares"] != 1900
    assert extract_state(data, ticker="OTHER", as_of=date(2026, 10, 13)).values["shares"] != 1900


def assert_plausibility():
    from inves_cog.ingest.fundamentals.health import health_row
    from inves_cog.ingest.fundamentals.plausibility import violations
    from inves_cog.ingest.fundamentals.state import FinState

    values = {"rev_ttm": 100e6, "ni_ttm": 20e6, "eps_ttm": 2, "shares": 10e6}
    assert not violations(values, {})
    for update, rule in [({"ni_ttm": -200e6}, 1), ({"eps_ttm": -2}, 2), ({"eps_ttm": 0.9}, 2)]:
        errors = violations({**values, **update}, {})
        assert any(row["rule"] == rule for row in errors)
    assert not violations({**values, "eps_ttm": 1}, {})  # exact 0.5 boundary
    assert not violations({**values, "eps_ttm": 4}, {})  # exact 2 boundary
    assert not violations({**values, "ni_ttm": 9_999_999, "eps_ttm": -20}, {})
    series = {
        "ni": {
            date(2026, m, 1): {"val": v, "derivation": "q4_derived" if m == 10 else None}
            for m, v in [(1, 10), (4, 10), (7, 10), (10, -31)]
        }
    }
    assert any(r["rule"] == 3 and r["quarters"] for r in violations(values, series))
    ratio_errors = violations({**values, "ni_ttm": -200e6}, series)
    assert any(row["rule"] == 1 and row["quarters"] for row in ratio_errors)
    safe = deepcopy(series)
    safe["ni"][date(2026, 10, 1)]["val"] = -30
    assert not violations(values, safe)
    state = FinState(
        ticker="BAD",
        extractor="fixed",
        filed=date(2026, 10, 13),
        period_end=date(2026, 9, 30),
        values=values,
        field_sources={"implausible_value": {"violations": [{"rule": 3, "quarters": ["2026-10-01"]}]}},
        health_codes=["implausible_value"],
    )
    health = health_row(state)
    assert not health["can_score"] and "3" in health["reason"] and "2026-10-01" in health["reason"]
