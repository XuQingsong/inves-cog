"""Offline incident checks from the read-only production audit and the preserved public repair journal.
This explicitly distinguishes stored post-repair data from journal reconstruction; no original snapshot is invented.
"""

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from inves_cog.dataguard.core import evaluate
from inves_cog.dataguard.reader import barometer_drift, load

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "handoff/A032/evidence"
    journal = json.loads((path / "public-market-journal.json").read_text())
    lines = {r["line"]: r["text"] for r in journal["public_market_excerpt"]}
    match = re.search(r"= ([\d.]+) \(was stale ([\d.]+) from", lines[8])
    corrected, old = map(float, match.groups())
    _, items = load(ROOT / "config/data_expectations.yaml")
    by_name = {i.dataset: i for i in items}
    day = date(2026, 11, 5)
    item = replace(by_name["波动率日线"], expected_keys=("VIX_CBOE",))
    vix_source = evaluate(item, day, [], [{"key": "VIX_CBOE", "value": old}])
    vix_cached = barometer_drift("晴雨表日报", day, old, corrected)
    etf = replace(by_name["指数与半导体基金日线"], expected_keys=("SOXX",))
    current = [{"key": "SOXX", "value": 131.9, "adjustment": 1.0}]
    previous = [{"key": "SOXX", "value": 450.41, "adjustment": 1 / 3}]
    soxx = evaluate(etf, day, current, previous, actions=set(etf.corporate_actions[str(day)]))
    counterfactual = evaluate(etf, day, current, previous)
    result = {
        "provenance": {
            "production_journal": "ops/swe2-backfill-20261106.txt",
            "journal_sha256": journal["sha256"],
            "public_lines": list(lines),
            "semantics": (
                "Repair-journal reconstruction, not an original database snapshot or historical availability proof."
            ),
        },
        "vix": {
            "source_original_record": lines[6],
            "source_gap_kinds": [f.kind for f in vix_source],
            "reported_cached_value": old,
            "canonical_after_repair": corrected,
            "cached_reading_kind": vix_cached.kind,
        },
        "occ": {
            "original_missing_basis": "A-032 task background and repair-journal section 2",
            "repair_record": lines[16],
            "missing_classifier": [f.kind for f in evaluate(by_name["期权日成交量"], day, [], [])],
        },
        "soxx": {
            "raw_return": 131.9 / 450.41 - 1,
            "adjusted_return": 131.9 / (450.41 / 3) - 1,
            "confirmed_action": etf.corporate_actions[str(day)]["SOXX"],
            "actual_kinds": [f.kind for f in soxx],
            "synthetic_no_action_control_kinds": [f.kind for f in counterfactual],
            "conclusion": (
                "Confirmed 3:1 split is exempt under task section 1; "
                "the mandatory-suspect expectation in T2 conflicts with verified facts."
            ),
        },
        "unchanged_limits": [
            "Original pre-repair row snapshot is unavailable.",
            "Actual first availability cannot be reconstructed from overwritten rows.",
            "No real provider request, database write, model call or email is made by this replay.",
        ],
    }
    assert "missing" in result["vix"]["source_gap_kinds"]
    assert result["vix"]["cached_reading_kind"] == "stale"
    assert result["occ"]["missing_classifier"] == ["missing"]
    assert not soxx and "suspect" in result["soxx"]["synthetic_no_action_control_kinds"]
    (path / "incident-reconstruction.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
