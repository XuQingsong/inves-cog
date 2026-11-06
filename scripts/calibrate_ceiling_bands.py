"""Offline quarterly calibration; production reads only the versioned YAML."""

import argparse
import csv
import hashlib
from datetime import date
from pathlib import Path

import yaml

from inves_cog.valuation_v1.ceiling_bands import calibrate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("panel", type=Path)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.panel.open() as stream:
        result = calibrate(csv.DictReader(stream), as_of=args.as_of, source="historical S&P 500 PIT weekly panel, r=8%")
    result["source_sha256"] = hashlib.sha256(args.panel.read_bytes()).hexdigest()
    args.output.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
