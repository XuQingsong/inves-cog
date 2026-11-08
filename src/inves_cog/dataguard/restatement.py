"""UD-A-60: append-only retrospective readings, never a historical PIT replacement.

The existing calculator is reused through a restricted read view. Daily source
values are aligned to observation days only inside this explicitly retrospective
view; actual collection/publication times remain untouched in source tables.
Weekly/monthly flow publication alignment is retained (no inferred release date).
"""

import hashlib
import json
import math
import re
from datetime import datetime, time, timedelta

from inves_cog.dataguard.calendar import NY


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class InputView:
    """Only the calculator's five known source tables, bounded by observation/revision time."""

    def __init__(self, connection, day, now):
        self.connection, self.day, self.now = connection, day, now
        self.sources = []

    def execute(self, sql, args=()):
        if not sql.startswith("SELECT ") or ";" in sql:
            raise ValueError("Restatement view is read-only")
        match = re.search(r" FROM ([a-z_]+\.[a-z_]+) ", sql)
        table = match[1] if match else ""
        columns = {
            "ingest.bars_daily": ("trade_date", None),
            "ingest.macro_observations": ("observation_date", "fetched_at"),
            "flows.observations": ("obs_date", "ingested_at"),
            "flows.etf_daily": ("date", "ingested_at"),
            "flows.cftc_positions": ("report_date", None),
        }
        if table not in columns:
            raise ValueError("Unknown restatement source")
        column, seen = columns[table]
        conditions = [f"{column}>=%s", f"{column}<=%s"]
        # The lookback must cover the deepest rolling input on px.index so a
        # restate reproduces the live path's values, not an approximation:
        # 资管净多分位 is _pct_rank(window=1260, minp=504) — the percentile at
        # day D is the rank of the last value across the trailing 1260
        # trading-day positions of the input series. px.index length is set by
        # this bound (every day on it is a trading day), so the bound must
        # span ≥1260 trading days ≈ 1825 calendar days; +20% margin → 2190.
        bound = [self.day - timedelta(days=int(1260 * 365 / 252 * 1.2)), self.day]
        if seen:
            conditions.append(f"{seen}<=%s")
            bound.append(self.now)
        if table in {"flows.observations", "flows.etf_daily"}:
            conditions.append("published_at<=%s")
            bound.append(self.now)
        if table == "flows.cftc_positions":
            conditions.append("release_at<=%s")
            bound.append(self.now)
            # Do not import reports released after the target historical day.
            bound[-1] = min(self.now, datetime.combine(self.day + timedelta(days=1), time(), NY))
        if table == "flows.etf_daily":
            conditions.append("published_at<=%s")
            bound.append(self.now)
        # The SELECT alias only changes alignment in this retrospective calculation.
        # No timestamp is written back to any business input table.
        sid = args[0] if args else ""
        if table == "flows.observations" and (
            sid.startswith("yahoo_px_") or sid.startswith("cboe_") or sid.startswith("ecb_")
        ):
            sql = sql.replace("published_at AS p", "(obs_date::timestamp AT TIME ZONE 'America/New_York') AS p")
        order = sql.index(" ORDER BY ")
        before, after = sql[:order], sql[order:]
        join = " AND " if " WHERE " in before else " WHERE "
        if table == "ingest.macro_observations":
            if "DISTINCT ON" not in before:
                before = before.replace("SELECT ", "SELECT DISTINCT ON (observation_date) ", 1)
            after = " ORDER BY observation_date,fetched_at DESC,realtime_start DESC"
        if table == "flows.observations":
            # A backfill vintage wins over older initial rows deterministically.
            if "DISTINCT ON" not in before:
                before = before.replace("SELECT ", "SELECT DISTINCT ON (obs_date) ", 1)
            after = " ORDER BY obs_date,ingested_at DESC,published_at DESC,vintage DESC"
        sql = before + join + " AND ".join(conditions) + after + " LIMIT 50001"
        rows = self.connection.execute(sql, (*args, *bound)).fetchall()
        # Sized for the widest read: ingest.bars_daily ~44 tickers × ~1550
        # trading days (2190d bound) ≈ 68k rows → 80k cap.
        if len(rows) > 80000:
            raise ValueError("Restatement input limit exceeded")
        digest = hashlib.sha256(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest()
        self.sources.append(dict(table=table, series=str(sid), rows=len(rows), sha256=digest))
        return Rows(rows)


def restate(connection, day, now, *, compute=None, code_rev=None):
    if now.tzinfo is None or now.astimezone(NY).date() < day:
        raise ValueError("Revision time must be actual aware time on or after data date")
    if compute is None:
        from inves_cog.perception.barometer.run import _rev, run_range

        compute, code_rev = run_range, _rev()
    view = InputView(connection, day, now)
    records = compute(view, day, day)
    if len(records) != 1:
        raise ValueError("No unique target-day reading")
    record = records[0]
    if str(record["date"])[:10] != str(day):
        raise ValueError("Wrong restatement date")
    record = {**record, "date": str(day), "asof": now.isoformat()}

    # Convert numpy scalars, reject non-finite metrics rather than writing invalid JSON.
    def finite(value):
        if isinstance(value, dict):
            return {k: finite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [finite(v) for v in value]
        return None if isinstance(value, float) and not math.isfinite(value) else value

    record = finite(json.loads(json.dumps(record, default=str)))
    for key in ("fear", "greed", "fear_level", "greed_level", "pendulum", "short_heat", "accumulation", "rebound"):
        if key in record and record[key] is not None:
            record[key] = float(record[key])
            if not math.isfinite(record[key]):
                record[key] = None
    provenance = dict(mode="retrospective", data_date=str(day), available_at=now.isoformat(), sources=view.sources)
    identity = dict(sources=view.sources, record={k: v for k, v in record.items() if k != "asof"}, code_rev=code_rev)
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    connection.execute(
        "INSERT INTO ops.barometer_revisions(data_date,revised_at,input_hash,record,provenance,code_rev) "
        "VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s) ON CONFLICT(data_date,input_hash) DO NOTHING",
        (day, now, digest, json.dumps(record), json.dumps(provenance), code_rev or "unknown"),
    )
    saved = connection.execute(
        "SELECT record,revised_at FROM ops.barometer_revisions WHERE data_date=%s AND input_hash=%s",
        (day, digest),
    ).fetchone()
    if not saved:
        raise ValueError("Restatement write not verified")
    return dict(record=saved["record"], revised_at=saved["revised_at"].isoformat(), input_hash=digest)


def verified(revision):
    record = revision.get("record") or {}
    return not record.get("missing", ["unknown"]) and all(
        isinstance(record.get(key), (float, int)) and math.isfinite(record[key]) for key in ("fear", "greed")
    )
