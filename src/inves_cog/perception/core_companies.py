"""B-069: core-company universe used by the news-event layer."""

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def core_companies():
    """ticker -> segment from config/core_companies.yaml."""
    root = Path(__file__).resolve().parents[3]
    document = yaml.safe_load((root / "config/core_companies.yaml").read_text())
    return {entry["ticker"]: entry["segment"] for entry in document["companies"]}
