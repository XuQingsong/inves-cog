"""Phase-2 flows collectors — slot-based, separate process, failure-isolated.
State file tracks completed slots so missed windows are caught up."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from inves_cog.clock import SystemClock
from inves_cog.flows.collectors import (
    INDEX_SYMS,
    collect_cboe_chain,
    collect_etf_shares,
    collect_occ,
    collect_occ_series,
)
from inves_cog.flows.store import DEFAULT_RAW, polite_http
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.settings import read_environment

STATE = Path("/home/claudeuser/inves-cog-data/flows/schedule_state.json")
_UNIVERSE = Path(__file__).resolve().parents[1] / "config" / "universe.yaml"


def _universe():
    try:
        loaded = yaml.safe_load(_UNIVERSE.read_text())
        return [r["ticker"] for r in loaded.get("stocks", loaded if isinstance(loaded, list) else [])]
    except Exception:
        return []


def _dsn(values):
    return values.get("Database", {}).get("INVES_COG_DATABASE_URL") or values.get("INVES_COG_DATABASE_URL")


def _connection(values):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(_dsn(values), row_factory=dict_row, autocommit=True)


def _load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))


def _intra_slots(day):
    out, t = [], datetime.combine(day, datetime.strptime("09:45", "%H:%M").time(), tzinfo=NY)
    end = datetime.combine(day, datetime.strptime("16:00", "%H:%M").time(), tzinfo=NY)
    while t <= end:
        out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=15)
    return out


def _prev_trading_days(day, n=5):
    out, d = [], day - timedelta(days=1)
    while len(out) < n:
        if trading_day(d):
            out.append(d)
        d -= timedelta(days=1)
    return out


def run_once(clock, values, http=None, conn=None, raw_dir=DEFAULT_RAW):
    local = clock.now_utc().astimezone(NY)
    today = local.date()
    if not trading_day(today):
        return {"status": "skipped", "reason": "non-trading day"}
    http = http or polite_http()
    state = _load_state()
    result = {}
    own = conn is None
    if conn is None:
        conn = _connection(values)
    try:
        hm = local.strftime("%H:%M")
        # missed intraday slots can't be replayed (chain is "now") — run only the
        # latest due slot; earlier ones are marked skipped.
        due = [sl for sl in _intra_slots(today) if hm >= sl and f"intra:{today}:{sl}" not in state]
        for sl in due[:-1]:
            state[f"intra:{today}:{sl}"] = "skipped"
        if due:
            slot = due[-1]
            result[f"intra:{today}:{slot}"] = [
                collect_cboe_chain(http, conn, s, raw_dir, 60, today) for s in INDEX_SYMS
            ]
            state[f"intra:{today}:{slot}"] = True
        eod_key = f"eod:{today}"
        if hm >= "16:30" and eod_key not in state:
            universe = INDEX_SYMS + [t for t in _universe() if t not in INDEX_SYMS]
            result[eod_key] = [collect_cboe_chain(http, conn, s, raw_dir, None, today) for s in universe]
            state[eod_key] = True
        etf_key = f"etf:{today}"
        if hm >= "17:30" and etf_key not in state:
            result[etf_key] = collect_etf_shares(http, conn, raw_dir)
            state[etf_key] = True
        if hm >= "07:00":
            for day in _prev_trading_days(today):
                for kind, label in (("volume", "occ_vol"), ("oi", "occ_oi")):
                    key = f"{label}:{day}"
                    if key not in state:
                        result[key] = collect_occ(http, conn, day, raw_dir, kind)
                        if result[key].get("rows", 0) > 0:
                            state[key] = True
                xkey = f"occ_xchk:{day}"
                if xkey not in state:
                    result[xkey] = [collect_occ_series(http, conn, s, raw_dir) for s in INDEX_SYMS]
                    state[xkey] = True
        _save_state(state)
        return {"status": "ok", "at": str(local), **result}
    finally:
        if own:
            conn.close()


def main():
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock, read_environment())
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
