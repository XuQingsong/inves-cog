"""Candidate review state machine shared by CLI, API and persistence adapters."""

import math
from copy import deepcopy

EDITABLE = {"direction", "strength", "lag", "exposure_usd", "exposure_basis", "exposure_asof", "basket_ids"}


def validate_edits(changes):
    if set(changes) - EDITABLE:
        raise ValueError("Unknown or immutable review field")
    strength = changes.get("strength")
    if strength is not None and (type(strength) not in (int, float) or not math.isfinite(strength)):
        raise ValueError("Strength must be finite or null")
    amount = changes.get("exposure_usd")
    if amount is not None and (not isinstance(amount, (float, int)) or not math.isfinite(amount) or amount < 0):
        raise ValueError("Exposure must be a nonnegative finite amount")
    if "exposure_basis" in changes and changes["exposure_basis"] not in {
        None,
        "收入占比",
        "RPO",
        "合同",
        "应收",
        "预付",
        "分部收入",
    }:
        raise ValueError("Unknown exposure basis")


class ReviewQueue:
    def __init__(self, *, clock, rows=(), save=None):
        self.clock, self.save = clock, save
        self.rows = {row["relation_id"]: deepcopy(row) for row in rows}

    def add(self, row):
        identifier = row["relation_id"]
        if identifier not in self.rows:
            self.rows[identifier] = deepcopy(row)
            self.rows[identifier]["status"] = "候选"
            if self.save:
                self.save(self.rows[identifier])

    def candidates(self, basket=None):
        return [
            deepcopy(row)
            for row in self.rows.values()
            if row["status"] == "候选" and (basket is None or basket in row.get("basket_ids", []))
        ]

    def confirmed(self):
        return [deepcopy(row) for row in self.rows.values() if row["status"] == "观察到"]

    def review(self, identifiers, *, action, edits=None):
        if action not in {"confirm", "reject", "modify"}:
            raise ValueError("Unknown review action")
        for identifier in identifiers:
            row = self.rows[identifier]
            if action == "modify":
                changes = (edits or {}).get(identifier, {})
                validate_edits(changes)
                row.update(deepcopy(changes))
                row["status"] = "候选"
                row["reviewed_at"] = None
            else:
                row["status"] = "观察到" if action == "confirm" else "驳回"
                row["reviewed_at"] = self.clock.now_utc()
            if self.save:
                self.save(row)
        return [deepcopy(self.rows[key]) for key in identifiers]
