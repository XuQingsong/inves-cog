"""Prioritized SIC mapping; unknown sectors remain SPY-only."""

from pathlib import Path

import yaml


def load_sic(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[3] / "config/sic_to_etf.yaml"
    document = yaml.safe_load(path.read_text())
    return document["rules"], document.get("tickers") or {}


def load_mapping(path=None):
    return load_sic(path)[0]


def sector_etf(sic, rules, *, ticker=None, tickers=None):
    if ticker and tickers and ticker in tickers:
        chosen = tickers[ticker]
        return None if chosen in {None, "SPY"} else chosen
    try:
        code = int(sic)
    except (ValueError, TypeError):
        return None
    for rule in rules:
        if any(a <= code <= b for a, b in rule["ranges"]):
            return rule["etf"]
    return None
