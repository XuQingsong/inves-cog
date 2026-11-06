"""Bounded A-032 source audit. Read-only login, no provider/model requests, no raw logs."""

import argparse
import json
import resource
import time as timer
from datetime import date, datetime, time, timedelta
from pathlib import Path


class Recorded:
    def __init__(self, db):
        self.db = db
        self.calls = []

    def execute(self, sql, parameters=()):
        self.calls.append((sql, parameters))
        return self.db.execute(sql, parameters)


def nodes(plan):
    result = []
    if plan.get("Node Type") in ("Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Index Scan"):
        result.append({k: plan[k] for k in ("Node Type", "Relation Name", "Index Name", "Plan Rows") if k in plan})
    for child in plan.get("Plans", []):
        result.extend(nodes(child))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", type=Path, required=True)
    args = p.parse_args()
    # Overlay only the new package on the installed project; never replace production code.
    import inves_cog

    inves_cog.__path__.insert(0, str(args.code / "src/inves_cog"))
    from inves_cog.clock import SystemClock
    from inves_cog.dataguard.calendar import NY
    from inves_cog.dataguard.reader import load
    from inves_cog.dataguard.service import connect, scan
    from inves_cog.ingest.settings import read_environment

    values = read_environment("/home/claudeuser/inves-cog/.env")
    _, items = load(args.code / "config/data_expectations.yaml")
    out = {
        "semantics": (
            "Current stored rows classified by observation date; not proof of original pre-repair availability."
        ),
        "production_writes": False,
        "provider_calls": 0,
        "model_calls": 0,
        "replay": {},
        "plans": [],
    }
    with connect(values) as db:
        out["read_only"] = (
            db.execute("SHOW default_transaction_read_only").fetchone()["default_transaction_read_only"] == "on"
        )
        out["non_admin"] = db.execute("SELECT current_user NOT IN ('postgres','inves_cog_admin') ok").fetchone()["ok"]
        recorder = Recorded(db)
        t = timer.monotonic()
        result, errors = scan(recorder, items, SystemClock().now_utc(), budget=23)
        out["cycle_seconds"] = round(timer.monotonic() - t, 3)
        out["checked_datasets"] = sum(bool(days) for _, days in result)
        out["query_errors"] = errors
        out["current_findings"] = [
            {"dataset": item.dataset, "date": str(day), "kinds": [f.kind for f in found]}
            for item, days in result
            for day, found in days.items()
            if found
        ]
        for sql, parameters in recorder.calls:
            try:
                raw = db.execute("EXPLAIN (FORMAT JSON) " + sql, parameters).fetchone()["QUERY PLAN"]
                out["plans"].append({"sql": sql, "nodes": nodes(raw[0]["Plan"])})
            except Exception as exc:
                out["plans"].append({"sql": sql, "error_type": type(exc).__name__})
        # Incident dates, limited to public market input facts. Do not query or export account/holding payloads.
        selected = [
            i
            for i in items
            if i.table
            in {
                "flows.observations",
                "ingest.macro_observations",
                "flows.option_volume_occ",
                "flows.short_volume",
                "ingest.bars_daily",
            }
            and i.dataset not in {"宽池日线", "监控池日线"}
        ]
        for day in (date(2026, 11, 3) + timedelta(days=n) for n in range(4)):
            moment = datetime.combine(day + timedelta(days=1), time(10), NY)
            rows, failed = scan(db, selected, moment, budget=20)
            out["replay"][str(day)] = {
                "errors": failed,
                "findings": [
                    {"dataset": item.dataset, "date": str(d), "kind": f.kind, "detail": f.detail}
                    for item, days in rows
                    for d, found in days.items()
                    if d == day
                    for f in found
                ],
            }
        out["incident_values"] = db.execute(
            "SELECT ticker,trade_date,close,adj_factor FROM ingest.bars_daily "
            "WHERE ticker='SOXX' AND trade_date BETWEEN DATE '2026-11-03' AND DATE '2026-11-06' ORDER BY trade_date"
        ).fetchall()
    out["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    print(json.dumps(out, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
