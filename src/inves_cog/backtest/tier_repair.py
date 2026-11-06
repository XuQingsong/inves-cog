"""Opt-in Visa filing reconstruction for the local research replay."""

import json
from pathlib import Path
from types import SimpleNamespace

from inves_cog.ingest.fundamentals.extractors import extract_state
from inves_cog.ingest.fundamentals.health import BLOCKING
from inves_cog.ingest.fundamentals.instances import InstanceLoader
from inves_cog.ingest.fundamentals.repairs import merge_facts


def repaired_state(original, candidates, day):
    if original is None or original.filed > day or not BLOCKING.intersection(original.health_codes):
        return original
    return next(
        (row for row in candidates if row.filed == original.filed and not BLOCKING.intersection(row.health_codes)),
        original,
    )


def visa_reconstruction(repository, companyfacts, cache_dir, *, end):
    """Use cached filings in chronological order and reject network fallback."""
    cache = Path(cache_dir)
    raw = json.loads(Path(companyfacts).read_text())
    if int(raw["cik"]) != 1403161:
        raise ValueError("Expected Visa CompanyFacts")

    def no_network(*args):
        raise ValueError("Visa reconstruction requires locally cached filing attachments")

    loader = InstanceLoader(sec=SimpleNamespace(get=no_network), cache_dir=cache, offline=True)
    filings = repository.read_shared_filings("V")
    eligible = [
        row
        for row in filings
        if row["form"] in {"10-Q", "10-K"}
        and row["filing_date"] <= end
        and (cache / row["accession"] / "instance-path").is_file()
    ]
    accumulated = {"facts": {}}
    output = []
    for row in sorted(eligible, key=lambda row: row["filing_date"]):
        parsed = loader.facts({**row, "ticker": "V", "cik": "0001403161"})
        accumulated = merge_facts(accumulated, parsed)
        state = extract_state(raw, ticker="V", as_of=row["filing_date"], filings=filings, instance_facts=accumulated)
        if state.filed == row["filing_date"] and not BLOCKING.intersection(state.health_codes):
            output.append(state)
    return output
