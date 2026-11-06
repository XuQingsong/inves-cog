"""Adapt existing historical parsers to a single-date, actual-receipt recovery write.
Preserves the existing vintage identity, so downstream readers see the repaired row.
Never fabricates historical publication time for newly obtained data.
"""

import re

from inves_cog.flows.store import upsert_many

DATES = {
    "observations": "obs_date",
    "option_volume_occ": "date",
    "etf_daily": "date",
    "short_volume": "date",
    "cftc_positions": "report_date",
}
STAMPED = {"observations", "etf_daily"}


def bounded_rows(table, rows, *, day, now, filters):
    if table not in {*DATES, "series_catalog"}:
        raise ValueError("Recovery table is not allowed")
    result = []
    for original in rows:
        row = dict(original)
        if table in DATES and row.get(DATES[table]) != day:
            continue
        if any(key in row and row[key] not in values for key, values in filters.items()):
            continue
        if table in STAMPED:
            row.update(published_at=now, ingested_at=now)
        if table == "cftc_positions":
            row["release_at"] = now
        result.append(row)
    return result


class ReceiptWriter:
    """Accept only the INSERT shape emitted by flows.store.upsert_many and raw-file receipts."""

    def __init__(self, connection, *, day, now, filters):
        self.db, self.day, self.now, self.filters = connection, day, now, filters

    def execute(self, sql, args=None):
        if not sql.lstrip().startswith("INSERT INTO flows.raw_files "):
            raise ValueError("Recovery direct statement is not allowed")
        return self.db.execute(sql, args)

    def cursor(self):
        return _Cursor(self)


class _Cursor:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, values):
        match = re.match(r"INSERT INTO flows\.([a-z_]+) \(([a-z_,]+)\) VALUES ", sql)
        if not match:
            raise ValueError("Unexpected recovery INSERT shape")
        table, cols = match.group(1), match.group(2).split(",")
        owner = self.owner
        rows = bounded_rows(
            table,
            [dict(zip(cols, r, strict=True)) for r in values],
            day=owner.day,
            now=owner.now,
            filters=owner.filters,
        )
        if rows:
            # Reuse the existing upsert helper, with the original connection, to avoid recursion.
            upsert_many(owner.db, table, list(rows[0]), rows, "update" if table != "series_catalog" else "nothing")
