"""Versioned M9 parameters; no rule A values are modified."""

from functools import lru_cache
from pathlib import Path

from inves_cog.params import load_params


@lru_cache(maxsize=1)
def settings():
    return load_params(Path(__file__).resolve().parents[3] / "config/params/p-2026.10").values["m9"]
