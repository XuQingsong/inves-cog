"""Poll the existing M2 financials task only, in its formal SEC daily window."""

import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect as connect_database
from inves_cog.ingest.fundamentals.cli import build as build_m2
from inves_cog.ingest.fundamentals.cli import run_tasks
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.settings import read_environment


def due(clock, last_run=None):
    local = clock.now_utc().astimezone(NY)
    return (
        trading_day(local.date())
        and (21, 15) <= (local.hour, local.minute) < (21, 45)
        and (last_run is None or last_run.astimezone(NY).date() < local.date())
    )


def run_once(*, clock, values, connect=connect_database, build=build_m2, dispatch=run_tasks):
    if not due(clock):
        return {"status": "not_due"}
    with connect(values) as connection:
        row = connection.execute(
            "SELECT started_at FROM ingest.job_runs WHERE task_name='m2_financials' "
            "AND trade_date=%s ORDER BY started_at DESC LIMIT 1",
            (clock.today_trade_date(),),
        ).fetchone()
        if not due(clock, row["started_at"] if row else None):
            return {"status": "not_due"}
        _, runner, tasks, _ = build(clock=clock, values=values, connection=connection)
        # Do not call M2's unfiltered schedule command: it also dispatches Yahoo consensus.
        return dispatch(clock=clock, runner=runner, tasks=tasks, names=["financials"])


def main():
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock=clock, values=read_environment())
            if result.get("status") != "not_due":
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
