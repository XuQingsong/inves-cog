"""Poll existing M3/M6 schedule entry points after their persisted dependencies finish."""

import time
from datetime import datetime, timezone

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.settings import read_environment

TASKS = ("bars_full", "m6_market_inputs", "financials", "m2_financials")


def dependencies_met(name, records):
    def completed(row):
        return bool(row and row["status"] in {"ok", "degraded"} and row.get("ended_at") is not None)

    if name == "market_structure":
        return all(completed(records.get(task)) for task in ("bars_full", "m6_market_inputs"))
    if name == "rule_a_scores":
        financial = [records[task] for task in ("financials", "m2_financials") if task in records]
        floor = datetime.min.replace(tzinfo=timezone.utc)
        latest = max(financial, key=lambda row: row.get("started_at") or row.get("ended_at") or floor, default=None)
        return completed(latest)
    raise ValueError("Unknown module task")


def readiness(values):
    records = None

    def ready(name, day):
        nonlocal records
        if records is None:
            with connect(values) as connection:
                rows = connection.execute(
                    "SELECT DISTINCT ON (task_name) task_name,status,started_at,ended_at "
                    "FROM ingest.job_runs WHERE trade_date=%s AND task_name=ANY(%s) "
                    "ORDER BY task_name,started_at DESC",
                    (day, list(TASKS)),
                ).fetchall()
                records = {row["task_name"]: row for row in rows}
        return dependencies_met(name, records)

    return ready


def run_once(*, clock, values, ready=None, market_run=None, score_run=None):
    local = clock.now_utc().astimezone(NY)
    if not trading_day(local.date()):
        return {}
    ready, result = ready or readiness(values), {}
    tasks = []
    if (local.hour, local.minute) >= (20, 45):
        tasks.append(("market_structure", market_run, "day"))
    if (local.hour, local.minute) >= (22, 30):
        tasks.append(("rule_a_scores", score_run, "signal_date"))
    for name, operation, day_key in tasks:
        try:
            if not ready(name, local.date()):
                result[name] = {"status": "waiting_dependencies"}
                continue
            if operation is None:
                if name == "market_structure":
                    from inves_cog.marketstate.cli import run as operation
                else:
                    from inves_cog.trading.scoring.cli import run as operation
            output = operation(clock=clock, values=values, schedule=True, **{day_key: local.date()})
            # Module entry points retain their persisted once-per-day guards.
            result[name] = {
                key: output[key]
                for key in ("status", "processed_count", "coverage", "expected", "observed_at")
                if key in output
            }
        except Exception as exc:
            # Keep one module failure from suppressing another; never log DSNs or keys.
            result[name] = {"status": "failed", "error_type": type(exc).__name__}
    return result


def main():
    clock = SystemClock()
    while True:
        result = run_once(clock=clock, values=read_environment())
        if any(row.get("status") != "not_due" for row in result.values()):
            print(json_text(result), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
