"""Phase-2 flows collectors — slot-based, separate process, failure-isolated."""

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from inves_cog.clock import SystemClock
from inves_cog.flows.collectors import (
    INDEX_SYMS,
    collect_cboe_chain,
    collect_cboe_pc,
    collect_etf_shares,
    collect_occ,
    collect_occ_series,
)
from inves_cog.flows.store import DEFAULT_RAW, polite_http, record_health_agg
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.settings import read_environment

XCHK_SYMS = ["SPY", "QQQ", "IWM", "SMH"]
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


def _etf_done(connection, today):
    try:
        r = connection.execute(
            "SELECT count(*) AS c FROM flows.etf_daily WHERE date=%s AND published_at::date=%s",
            (today, today),
        ).fetchone()
        return bool(r and r["c"])
    except Exception:
        return False


def _barometer(conn, today, hm, cur, local, state):
    """Official 16:45+ reading (once today's bars land ~20:20) + intraday slots.

    Official: runs only when the day's bars exist for the core symbols; marks
    done only when a barometer_daily row was actually written. A day whose
    bars never land stays in `baro_pending:` and is retried on every loop;
    past 09:00 ET the next day it records degraded health (that date, not
    today) and clears. record_health(connection, source, ok, now, items, note).
    """
    from inves_cog.flows.store import record_health
    from inves_cog.perception.barometer.run import persist, run_intraday, run_range

    out = {}

    def _try_day(day):
        key = f"baro:{day}"
        if key in state:
            return
        rows = conn.execute(
            "SELECT count(*) AS c FROM ingest.bars_daily WHERE trade_date=%s AND ticker = ANY(%s)",
            (day, ["SPY", "QQQ", "SMH"] + list(INDEX_SYMS)),
        ).fetchone()
        if rows["c"] >= 3:
            recs = run_range(conn, day, day)
            written = [r for r in recs if r["date"].date() == day]
            persist(conn, written)
            if written:
                record_health(
                    conn, "Flows:Barometer", True, local, items=len(written), note=f"fear={written[-1]['fear']}"
                )
                out[key] = {"fear": written[-1]["fear"]}
                state[key] = True
                state.pop(f"baro_pending:{day}", None)
                return
        # bars missing: degraded once the day after is past 09:00 ET
        overdue = (local.date() > day and local.hour >= 9) or (local.date() - day).days > 1
        if overdue:
            record_health(conn, "Flows:Barometer", False, local, items=0, note=f"bars_daily missing for {day}")
            state[key] = "degraded"
            state.pop(f"baro_pending:{day}", None)
        else:
            state[f"baro_pending:{day}"] = True

    if hm >= "16:45" or f"baro_pending:{today}" in state:
        _try_day(today)
    # retry every still-pending past trading day
    for key in [k for k in state if k.startswith("baro_pending:")]:
        day = date.fromisoformat(key.split(":", 1)[1])
        if day != today and trading_day(day):
            _try_day(day)
        elif day != today:
            state.pop(key, None)
    if cur and f"baro:{today}" not in state:
        key = f"baro_intra:{today}:{cur}"
        if key not in state:
            rec = run_intraday(conn, local)
            persist(conn, [rec], table="flows.barometer_intraday", ts=local)
            out[key] = {"fear": rec["fear"], "missing": len(rec["missing"])}
            state[key] = True
    return out


def run_once(clock, values, http=None, conn=None, raw_dir=DEFAULT_RAW):  # noqa: C901
    local = clock.now_utc().astimezone(NY)
    today = local.date()
    http = http or polite_http()
    state = _load_state()
    result = {}
    own = conn is None
    if conn is None:
        conn = _connection(values)
    try:
        hm = local.strftime("%H:%M")
        is_td = trading_day(today)
        # OCC daily jobs: every day from 07:00 (historical by date → catch-up ok)
        if hm >= "07:00":
            for day in _prev_trading_days(today):
                for kind, label in (("volume", "occ_vol"), ("oi", "occ_oi")):
                    key = f"{label}:{day}"
                    if key not in state:
                        result[key] = collect_occ(http, conn, day, raw_dir, kind, local)
                        if result[key].get("rows", 0) > 0 or "error" in result[key]:
                            state[key] = True
            xkey = f"occ_xchk:{today}"
            if xkey not in state:
                syms = XCHK_SYMS + [t for t in _universe() if t not in XCHK_SYMS]
                res = [collect_occ_series(http, conn, s, raw_dir, local) for s in syms]
                result[xkey] = res
                record_health_agg(conn, "Flows:OCCSeriesXchk", res, local)
                state[xkey] = True  # note: _SPX dropped (no series-search page)
        if not is_td:
            _save_state(state)
            return {"status": "ok", "at": str(local), "note": "non-trading day: occ only", **result}
        # intraday: only the slot containing now; within [slot, slot+15min)
        cur = None
        for sl in _intra_slots(today):
            if sl <= hm < (datetime.strptime(sl, "%H:%M") + timedelta(minutes=15)).strftime("%H:%M"):
                cur = sl
        if cur:
            key = f"intra:{today}:{cur}"
            if key not in state:
                res = [collect_cboe_chain(http, conn, s, raw_dir, 60, today, local) for s in INDEX_SYMS]
                result[key] = res
                record_health_agg(conn, "Flows:CboeChain", res, local)
                state[key] = True
        if hm >= "16:30":
            key = f"eod:{today}"
            if key not in state:
                universe = INDEX_SYMS + [t for t in _universe() if t not in INDEX_SYMS]
                res = [collect_cboe_chain(http, conn, s, raw_dir, None, today, local) for s in universe]
                result[key] = res
                record_health_agg(conn, "Flows:CboeChain", res, local)
                state[key] = True
        if hm >= "19:00":
            key = f"cboe_pc:{today}"
            if key not in state:
                result[key] = collect_cboe_pc(http, conn, today, raw_dir, local)
                if result[key].get("rows", 0) > 0:
                    state[key] = True
        # ETF slot 22:30 → retry until file date == today; stale → degraded after 09:00 next day
        key = f"etf:{today}"
        if (hm >= "22:30" or (hm < "09:00" and key in state)) and key not in state:
            result[key] = collect_etf_shares(http, conn, raw_dir, local)
            if _etf_done(conn, today):
                state[key] = True
            elif hm < "09:00":
                state[f"etf_stale:{today}"] = True
                from inves_cog.flows.store import record_health

                record_health(conn, "Flows:ETFShares", False, 0, f"files stale, latest != {today}", now=local)
                state[key] = True
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
