"""Run the barometer for one day or a range — used by backfill and the scheduler."""
import json
import logging
import subprocess

from inves_cog.perception.barometer.compute import STAGES, compute_day, dimensions, indicators
from inves_cog.perception.barometer.loader import flows_inputs, price_frame

log = logging.getLogger(__name__)


def _rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def run_range(conn, start, end):
    """Compute every trading day in [start, end]; returns list of records."""
    px = price_frame(conn, end, start)
    idx = px.index
    flows = flows_inputs(conn, idx, px)
    M = indicators(px, flows)
    F, G = dimensions(M)
    days = [d for d in M.index if d.date() >= start and d.date() <= end]
    return [compute_day(M, F, G, d) for d in days]


def persist(conn, records):
    rev = _rev()
    with conn.cursor() as c:
        for r in records:
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
                (r["date"], r["asof"] if "asof" in r else r["date"], r["fear"], r["greed"],
                 r["fear_level"], r["greed_level"],
                 STAGES[r["stage"] + 3] if isinstance(r["stage"], int) else r["stage"],
                 r["pendulum"], r["short_heat"], r["accumulation"], r["nature"],
                 json.dumps(r["dims"], default=str), json.dumps(r.get("inputs", {}), default=str),
                 json.dumps(r.get("missing", []), default=str), rev))
