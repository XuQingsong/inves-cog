"""Paper planning entry point; all observations use an injected Clock."""

import argparse
import json
import time
from datetime import date
from pathlib import Path

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import Repository as OperationalRepository
from inves_cog.ingest.settings import read_environment
from inves_cog.trading.execution.service import daily_plan

ROOT = Path(__file__).resolve().parents[4]


def due(clock, last=None):
    local = clock.now_utc().astimezone(NY)
    return (
        trading_day(local.date())
        and (8, 0) <= (local.hour, local.minute) < (8, 30)
        and (last is None or last.astimezone(NY).date() < local.date())
    )


def read_overlay(values, target):
    folder = values.get("INVES_COG_OVERLAY_DIR")
    path = Path(folder) / f"event_overlay_{target}.json" if folder else None
    if path is not None and path.is_file():
        return json.loads(path.read_text())
    return None


def run_daily(*, clock, values, persist=True, target=None, connection=None):
    target = target or clock.today_trade_date()
    universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]
    if connection is not None:
        return daily_plan(
            clock=clock,
            connection=connection,
            universe=universe,
            target=target,
            overlay=read_overlay(values, target),
            persist=persist,
        )
    writer = {**values, "INVES_COG_DATABASE_URL": values.get("INVES_COG_TRADING_DATABASE_URL")}
    with connect(writer) as source:
        if not persist:
            source.execute("SET default_transaction_read_only=on")
        return daily_plan(
            clock=clock,
            connection=source,
            universe=universe,
            target=target,
            overlay=read_overlay(values, target),
            persist=persist,
        )


def scheduled(*, clock, values):
    with connect(values) as operations:
        repository = OperationalRepository(operations)
        if not due(clock, repository.last_runs().get("paper_plan")):
            return {"status": "not_due"}
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=repository.health_rows(), persist=repository.write_health),
            persist=repository.write_job,
        )

        def operation():
            plan = run_daily(clock=clock, values=values)
            issue = not plan["published"] or bool(plan["missing_scores"]) or "cash_negative" in plan["health_codes"]
            return {
                "status": "degraded" if issue else "ok",
                "processed_count": len(plan["orders"]),
                "note": ";".join(plan["health_codes"]),
                "plan": plan,
            }

        return runner.run("paper_plan", "RuleAPaper", operation)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "schedule", "replay"])
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    clock = SystemClock()
    if args.action == "replay":
        from inves_cog.trading.execution.replay import run_frozen

        result = run_frozen(end=args.date or date(2026, 10, 7))
    elif args.action == "run":
        result = run_daily(clock=clock, values=read_environment(), target=args.date)
    else:
        while True:
            result = scheduled(clock=clock, values=read_environment())
            if result.get("status") != "not_due":
                print(json.dumps(result, default=str, ensure_ascii=False), flush=True)
            time.sleep(30)
    text = json.dumps(result, default=str, ensure_ascii=False, allow_nan=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
