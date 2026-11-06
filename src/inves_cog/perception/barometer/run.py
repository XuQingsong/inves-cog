"""Run the barometer for one day or a range — used by backfill and the scheduler."""

import json
import logging
import subprocess

import pandas as pd

from inves_cog.perception.barometer.compute import STAGES, compute_day, dimensions, indicators
from inves_cog.perception.barometer.loader import flows_inputs, price_frame

log = logging.getLogger(__name__)


def _rev():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return "unknown"


def run_intraday(conn, local):
    """Provisional reading for the current intraday slot.

    Price inputs use today's ingest.intraday_snapshots.last (the same source
    the live pages use for 现价); columns with no snapshot today inherit the
    previous trading day's px row (daily series stay live intraday). Index
    snapshots map onto the daily columns they mirror (^VIX→VIX, ^VIX3M→VIX3M,
    ^TNX→TNX — same units verified against the daily series).
    """
    px = price_frame(conn, local.date())
    today = pd.Timestamp(local.date())
    snaps = conn.execute(
        "SELECT DISTINCT ON (ticker) ticker, last, as_of "
        "FROM ingest.intraday_snapshots "
        "WHERE (as_of AT TIME ZONE 'America/New_York')::date = %s AND as_of <= %s "
        "ORDER BY ticker, as_of DESC",
        (local.date(), local),
    ).fetchall()
    row = {r["ticker"]: float(r["last"]) for r in snaps}
    for snap_t, col in {"^VIX": "VIX", "^VIX3M": "VIX3M", "^TNX": "TNX"}.items():
        if snap_t in row:
            row[col] = row[snap_t]
    prov = px.loc[px.index[-1]].copy() if len(px.index) else pd.Series({t: float("nan") for t in px.columns})
    for t in px.columns:
        if t in row:
            prov[t] = row[t]
    prov.name = today
    px.loc[today] = prov  # provisional row: inherits yesterday, snapshots override
    flows = flows_inputs(conn, px.index, px)
    M = indicators(px, flows)
    F, G = dimensions(M)
    rec = compute_day(M, F, G, today)
    rec["asof"] = local
    rec["inputs"]["provisional"] = True
    return rec


def run_range(conn, start, end):
    """Compute every trading day in [start, end]; returns list of records."""
    px = price_frame(conn, end, start)
    idx = px.index
    flows = flows_inputs(conn, idx, px)
    M = indicators(px, flows)
    F, G = dimensions(M)
    days = [d for d in M.index if d.date() >= start and d.date() <= end]
    return [compute_day(M, F, G, d) for d in days]


def persist(conn, records, table="flows.barometer_daily", ts=None):
    rev = _rev()
    with conn.cursor() as c:
        for r in records:
            if ts is not None:
                c.execute(
                    "INSERT INTO flows.barometer_intraday (ts,asof,fear,greed,fear_level,greed_level,"
                    "stage,pendulum,short_heat,accumulation,nature,dims,inputs,missing,code_rev) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (ts) DO UPDATE SET fear=EXCLUDED.fear,greed=EXCLUDED.greed,"
                    "dims=EXCLUDED.dims,inputs=EXCLUDED.inputs,code_rev=EXCLUDED.code_rev",
                    (
                        ts,
                        r["asof"] if "asof" in r else r["date"],
                        r["fear"],
                        r["greed"],
                        r["fear_level"],
                        r["greed_level"],
                        STAGES[r["stage"] + 3] if isinstance(r["stage"], int) else r["stage"],
                        r["pendulum"],
                        r["short_heat"],
                        r["accumulation"],
                        r["nature"],
                        json.dumps(r["dims"], default=str),
                        json.dumps(r.get("inputs", {}), default=str),
                        json.dumps(r.get("missing", []), default=str),
                        rev,
                    ),
                )
                continue
            c.execute(
                "INSERT INTO flows.barometer_daily (date,asof,fear,greed,fear_level,greed_level,"
                "stage,pendulum,short_heat,accumulation,nature,dims,inputs,missing,code_rev) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (date) DO UPDATE SET asof=EXCLUDED.asof,fear=EXCLUDED.fear,"
                "greed=EXCLUDED.greed,fear_level=EXCLUDED.fear_level,"
                "greed_level=EXCLUDED.greed_level,stage=EXCLUDED.stage,"
                "pendulum=EXCLUDED.pendulum,short_heat=EXCLUDED.short_heat,"
                "accumulation=EXCLUDED.accumulation,nature=EXCLUDED.nature,"
                "dims=EXCLUDED.dims,inputs=EXCLUDED.inputs,missing=EXCLUDED.missing,"
                "code_rev=EXCLUDED.code_rev",
                (
                    r["date"],
                    r["asof"] if "asof" in r else r["date"],
                    r["fear"],
                    r["greed"],
                    r["fear_level"],
                    r["greed_level"],
                    STAGES[r["stage"] + 3] if isinstance(r["stage"], int) else r["stage"],
                    r["pendulum"],
                    r["short_heat"],
                    r["accumulation"],
                    r["nature"],
                    json.dumps(r["dims"], default=str),
                    json.dumps(r.get("inputs", {}), default=str),
                    json.dumps(r.get("missing", []), default=str),
                    rev,
                ),
            )
