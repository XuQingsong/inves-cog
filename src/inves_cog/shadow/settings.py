"""Versioned M9 parameters; no rule A values are modified."""

from pathlib import Path

from inves_cog.params import load_params


def settings():
    return load_params(Path(__file__).resolve().parents[3] / "config/params/p-2026.10").values["m9"]
