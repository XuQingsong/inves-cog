"""Prioritized SIC mapping; unknown sectors remain SPY-only."""

from pathlib import Path

import yaml


def load_mapping(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[3] / "config/sic_to_etf.yaml"
    return yaml.safe_load(path.read_text())["rules"]


def sector_etf(sic, rules):
    try:
        code = int(sic)
    except (ValueError, TypeError):
        return None
    for rule in rules:
        if any(a <= code <= b for a, b in rule["ranges"]):
            return rule["etf"]
    return None
