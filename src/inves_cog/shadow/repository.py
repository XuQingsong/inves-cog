"""Only explicit M9 shadow-table writes; caller owns the scoped transaction/login."""

import json

from psycopg.types.json import Jsonb


def jsonb(value):
    return Jsonb(value, dumps=lambda v: json.dumps(v, default=str, ensure_ascii=False, allow_nan=False))


class WriteRepository:
    allowed_tables = {
        "perception_shadow.signals",
        "factor_shadow.registry",
        "factor_shadow.daily",
        "factor_shadow.f02_state",
    }
    columns = {
        "perception_shadow.signals": (
            "signal_key",
            "date",
            "signal",
            "ticker",
            "event_id",
            "condition_detail",
            "shadow_action",
            "rule_a_action",
            "params_version",
        ),
        "factor_shadow.registry": (
            "factor_id",
            "version",
            "definition",
            "inputs",
            "pit_note",
            "target",
            "rationale",
            "source",
            "expected_direction",
            "status",
            "created_at",
        ),
        "factor_shadow.daily": (
            "date",
            "ticker",
            "factor_id",
            "version",
            "value",
            "substituted_value",
            "would_pass",
            "rule_a_entry_pass",
            "gap_detail",
            "params_version",
            "generated_at",
        ),
        "factor_shadow.f02_state": (
            "date",
            "ticker",
            "holding_id",
            "version",
            "state",
            "shadow_action",
            "params_version",
        ),
    }
    json_columns = {"condition_detail", "rule_a_action", "inputs", "value", "substituted_value", "gap_detail", "state"}

    def __init__(self, connection):
        self.connection = connection

    def write(self, table, row):
        if table not in self.allowed_tables:
            raise ValueError("I32/I35: no write outside M9 shadow schemas")
        columns = self.columns[table]
        values = [
            jsonb(row.get(key)) if key in self.json_columns and row.get(key) is not None else row.get(key)
            for key in columns
        ]
        # Append-only snapshots. Unique keys make a retry idempotent, not another X1 event.
        self.connection.execute(
            "INSERT INTO "
            + table
            + " ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join(["%s"] * len(columns))
            + ") ON CONFLICT DO NOTHING",
            values,
        )
