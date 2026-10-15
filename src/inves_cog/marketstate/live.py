"""Opt-in real-source smoke, always excluded from CI."""

import os

from inves_cog.ingest.settings import read_environment
from inves_cog.marketstate.cli import completed_day, run


def run_smoke(*, clock):
    if os.environ.get("INVES_COG_LIVE") != "1":
        raise RuntimeError("Explicit live opt-in required")
    report = run(clock=clock, values=read_environment(), day=completed_day(clock))
    if report.get("status") == "failed":
        raise RuntimeError("Inspect actual source health")
    return report
