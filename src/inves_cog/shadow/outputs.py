"""Scoped M9 persistence and a recoverable DB-to-file publication boundary."""

import json

from inves_cog.overlay.delivery import FileDelivery
from inves_cog.shadow.repository import WriteRepository, jsonb


class DatabaseOutputs:
    def __init__(self, *, overlay_connection, shadow_connection, folder):
        self.overlay = overlay_connection
        self.shadow = shadow_connection
        self.writer = WriteRepository(shadow_connection)
        self.delivery = FileDelivery(folder)

    def last_overlay(self, target):
        row = self.overlay.execute(
            "SELECT payload FROM overlay.versions WHERE date<=%s AND published ORDER BY date DESC,version DESC LIMIT 1",
            (target,),
        ).fetchone()
        return row["payload"] if row else None

    def next_version(self):
        return self.overlay.execute(
            "SELECT nextval(pg_get_serial_sequence('overlay.versions','version')) AS version"
        ).fetchone()["version"]

    def publish_overlay(self, target, payload):
        # A prepared audit row survives file failure. HTTP and M4 consume the
        # same file; only successful delivery marks the database row published.
        with self.overlay.transaction():
            self.overlay.execute(
                "INSERT INTO overlay.versions (version,date,generated_at,source_events_asof,params_version,payload) "
                "OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    payload["version"],
                    target,
                    payload["generated_at"],
                    payload["source_events_asof"],
                    payload["params_version"],
                    jsonb(payload),
                ),
            )
        self.delivery.publish(str(target), payload)
        if self.delivery.read(str(target)) != payload:
            raise ValueError("overlay file verification failed")
        with self.overlay.transaction():
            self.overlay.execute("UPDATE overlay.versions SET published=true WHERE version=%s", (payload["version"],))

    def retain_overlay(self, target, payload):
        self.delivery.publish(str(target), payload)

    def register(self, definitions, at):
        versions = {}
        for definition in definitions:
            fields = ("definition", "inputs", "pit_note", "target", "rationale", "source", "expected_direction")
            prior = self.shadow.execute(
                "SELECT * FROM factor_shadow.registry WHERE factor_id=%s ORDER BY created_at DESC,version DESC",
                (definition["factor_id"],),
            ).fetchall()
            latest = max(prior, key=lambda row: int(row["version"].removeprefix("v")), default=None)
            matched = latest if latest and all(latest[key] == definition[key] for key in fields) else None
            if matched is None:
                n = max((int(row["version"].removeprefix("v")) for row in prior), default=0) + 1
                matched = {**definition, "version": f"v{n}", "created_at": at}
                self.writer.write("factor_shadow.registry", matched)
            versions[definition["factor_id"]] = matched["version"]
        return versions

    def seen_signals(self):
        rows = self.shadow.execute("SELECT signal_key FROM perception_shadow.signals").fetchall()
        return {row["signal_key"] for row in rows}

    def save_signals(self, rows):
        with self.shadow.transaction():
            for row in rows:
                self.writer.write("perception_shadow.signals", row)

    def save_factors(self, rows):
        with self.shadow.transaction():
            for row in rows:
                self.writer.write("factor_shadow.daily", row)

    def prior_state(self, ticker, holding_id, version, target):
        row = self.shadow.execute(
            "SELECT state FROM factor_shadow.f02_state WHERE ticker=%s AND holding_id=%s "
            "AND version=%s AND date<%s ORDER BY date DESC LIMIT 1",
            (ticker, holding_id, version, target),
        ).fetchone()
        return json.loads(row["state"]) if row and isinstance(row["state"], str) else (row["state"] if row else {})

    def save_state(self, row):
        self.writer.write("factor_shadow.f02_state", row)
