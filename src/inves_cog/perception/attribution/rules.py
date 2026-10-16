"""Versioned M8 thresholds. Business code reads them from the parameter directory."""

from pathlib import Path

from inves_cog.params import load_params


def m8_rules(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[4]
    loaded = load_params(root / "config/params/p-2026.10")
    return loaded.values["m8"]
