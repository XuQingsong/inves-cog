"""Atomic file publication of the exact public, tightening-only contract."""

import json
import os
from datetime import date
from pathlib import Path

from inves_cog.overlay.rules import timestamp

ROOT_FIELDS = {"version", "generated_at", "source_events_asof", "params_version", "tickers", "market"}
TICKER_FIELDS = {
    "linkage_events",
    "cooling_off",
    "first_lot_multiplier",
    "divergence_tag",
    "stop_review_eligible",
    "reason",
}


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != ROOT_FIELDS:
        raise ValueError("I24: overlay root contract differs")
    if type(payload["version"]) is not int or payload["version"] < 1:
        raise ValueError("I24: invalid overlay version")
    generated, source = timestamp(payload["generated_at"]), timestamp(payload["source_events_asof"])
    if generated is None or source is None or source > generated:
        raise ValueError("I24: overlay source must be visible at generation")
    for item in payload["tickers"].values():
        if set(item) != TICKER_FIELDS or type(item["cooling_off"]) is not bool:
            raise ValueError("I24: unsupported action or ticker field")
        if (
            type(item["first_lot_multiplier"]) not in (int, float)
            or item["first_lot_multiplier"] != 1.0
            or item["stop_review_eligible"] is not False
        ):
            raise ValueError("I24: multiplier and stop review are frozen")
    json.dumps(payload, allow_nan=False)
    return payload


class FileDelivery:
    def __init__(self, folder):
        self.folder = Path(folder)

    def _path(self, day):
        return self.folder / f"event_overlay_{date.fromisoformat(str(day)).isoformat()}.json"

    def read(self, day):
        path = self._path(day)
        return validate_payload(json.loads(path.read_text())) if path.is_file() else None

    def publish(self, day, payload):
        validate_payload(payload)
        path = self._path(day)
        self.folder.mkdir(parents=True, exist_ok=True)
        old = self.read(day)
        if old is not None:
            if old == payload:
                return
            if payload["version"] <= old["version"]:
                raise ValueError("overlay version cannot go backwards or replace an existing version")
        temporary = path.with_suffix(".json.staged")
        with temporary.open("x") as output:
            json.dump(payload, output, ensure_ascii=False, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
