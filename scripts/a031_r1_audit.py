"""Attach reproducible membership/removed-company coverage to the corrected study."""

import csv
import json
from collections import Counter
from pathlib import Path

from run_a031_r1 import BANK_INSURANCE

from inves_cog.backtest.membership import is_member


def main():
    root = Path("handoff/A031/evidence")
    path = root / "r1-corrected/data-audit.json"
    audit = json.loads(path.read_text())
    raw = json.loads((root / "membership/official-events.json").read_text())
    ledger = json.loads((root / "membership/ledger.json").read_text())
    counts = Counter()
    for row in csv.DictReader(open(Path.home() / "inves-cog-bt/valuation/panel_sp500.csv")):
        if is_member(ledger["events"].get(row["ticker"], []), row["date"]) is False:
            counts[row["ticker"]] += 1
    coverage = {}
    for year in range(2018, 2027):
        expected = set()
        for row in raw["events"]:
            if row["action"] != "deleted" or not row["effective"].startswith(str(year)):
                continue
            symbols = (row["ticker"] or ("company:" + row["company"])).split("/")
            if row["company"] == "Twenty-First Century Fox":
                symbols = ["predecessor:Twenty-First Century Fox"]
            expected.update(t for t in symbols if t not in BANK_INSURANCE)
        valid = set(audit["yearly"].get(str(year), {}).get("valid_names", []))
        covered = expected & valid
        coverage[str(year)] = dict(
            official_removed=len(expected),
            with_valid_m=len(covered),
            pct=100 * len(covered) / len(expected) if expected else None,
            missing=sorted(expected - covered),
        )
    audit.update(removed_coverage_by_year=coverage, official_membership=ledger, excluded_outside_membership=counts)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    source = json.loads((root / "r1-source-audit.json").read_text())
    source.update(
        status="official_events_applied_coverage_limits_retained",
        resolution=dict(
            announcements=121,
            official_events=sum(len(v) for v in ledger["events"].values()),
            excluded_weekly_rows=sum(counts.values()),
            affected_tickers=len(counts),
            corrected_output="r1-corrected/",
            remaining=(
                "observable panel lacks some removed issuers; "
                "no-event names retain supplied membership; terminal quote is a proxy"
            ),
        ),
    )
    (root / "r1-source-audit.json").write_text(json.dumps(source, indent=2) + "\n")


if __name__ == "__main__":
    main()
