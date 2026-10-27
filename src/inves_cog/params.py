"""Load a versioned parameter directory without silent key overwrites."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Any
import yaml


@dataclass(frozen=True)
class Parameters:
    params_version: str
    values: Mapping[str, Any]


def load_params(directory: Path | str) -> Parameters:
    directory = Path(directory)
    if not directory.is_dir() or not directory.name.startswith("p-"):
        raise ValueError(f"{directory}: expected a versioned parameter directory")
    values = {}
    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        raise ValueError(f"{directory}: no parameter files")
    for path in paths:
        parsed = yaml.safe_load(path.read_text())
        if not isinstance(parsed, dict):
            raise ValueError(f"{path}: parameters must be a mapping")
        duplicate = set(values) & set(parsed)
        if duplicate:
            raise ValueError(f"{path}: duplicate parameter keys {sorted(duplicate)}")
        values.update(parsed)
    return Parameters(directory.name, MappingProxyType(values))
