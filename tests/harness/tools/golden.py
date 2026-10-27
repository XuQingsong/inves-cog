"""One read-only loader for requirements golden and frozen-input validation."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def read_manifest(directory, rule):
    directory = Path(directory)
    path = directory / "MANIFEST.sha256"
    if not path.is_file():
        raise AssertionError(f"{path}:1: {rule}: missing manifest")
    rows = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-f0-9]{64})  (.+)", line)
        if not match:
            raise AssertionError(f"{path}:{line_no}: {rule}: invalid manifest row")
        digest, name = match.groups()
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in rows:
            raise AssertionError(f"{path}:{line_no}: {rule}: unsafe or duplicate path {name}")
        rows[name] = digest
    return rows


def validate_golden(directory=None):
    directory = Path(directory) if directory is not None else ROOT / "docs/phase1/golden"
    rows = read_manifest(directory, "FR-M0-07")
    present = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    expected = set(rows) | {"MANIFEST.sha256"}
    if present != expected:
        raise AssertionError(f"{directory}:1: FR-M0-07: file-set mismatch {sorted(present ^ expected)}")
    for name, expected_hash in rows.items():
        p = directory / name
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected_hash:
            raise AssertionError(f"{p}:1: FR-M0-07: SHA-256 mismatch")
    return rows


def load_golden(name, directory=None):
    directory = Path(directory) if directory is not None else ROOT / "docs/phase1/golden"
    rows = validate_golden(directory)
    if name not in rows:
        raise AssertionError(f"{directory / name}:1: FR-M0-07: unregistered golden")
    path = directory / name
    return json.loads(path.read_text()) if path.suffix == ".json" else path.read_bytes()


def validate_frozen(directory, changelog, *, changelog_prefix="tests/fixtures/phase1/"):
    directory, changelog = Path(directory), Path(changelog)
    rows = read_manifest(directory, "FR-M0-08")
    ignored = {"MANIFEST.sha256"}
    if changelog.parent == directory:
        ignored.add(changelog.name)
    present = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
    if present - ignored != set(rows):
        raise AssertionError(f"{directory}:1: FR-M0-08: frozen file-set mismatch")
    log = changelog.read_text()
    for name, registered_hash in rows.items():
        p = directory / name
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != registered_hash:
            raise AssertionError(f"{p}:1: FR-M0-08: frozen hash mismatch; update manifest and CHANGELOG")
        if not any(changelog_prefix + name in line and actual in line for line in log.splitlines()):
            raise AssertionError(f"{p}:1: FR-M0-08: missing CHANGELOG path and new hash")
