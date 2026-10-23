"""Paper planning entry point; all observations use an injected Clock."""

import argparse
import json
import time
from datetime import date, datetime
from datetime import time as wall_time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import exchange, trading_day
from inves_cog.ingest.repository import Repository as OperationalRepository
from inves_cog.ingest.settings import read_environment
from inves_cog.trading.execution.service import daily_plan

ROOT = Path(__file__).resolve().parents[4]


def due(clock, last=None):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    return (
        trading_day(local.date())
        and (8, 35) <= (local.hour, local.minute) < (9, 5)
        and (last is None or last.astimezone(ZoneInfo("America/New_York")).date() < local.date())
    )


def read_overlay(values, target, *, asof=None):
    folder = values.get("INVES_COG_OVERLAY_DIR")
    path = Path(folder) / f"event_overlay_{target}.json" if folder else None
    if path is not None and path.is_file():
        result = json.loads(path.read_text())
        if asof is not None:
            value = result.get("generated_at")
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
            if stamp is None or stamp.tzinfo is None or stamp > asof:
                return None
        return result
    return None


def run_daily(*, clock, values, persist=True, target=None, connection=None):
    target = target or clock.today_trade_date()
    universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]
    window_start = datetime.combine(target, wall_time(8, 35), ZoneInfo("America/New_York"))
    overlay = read_overlay(values, target, asof=min(clock.now_utc(), window_start))
    if connection is not None:
        return daily_plan(
            clock=clock,
            connection=connection,
            universe=universe,
            target=target,
            overlay=overlay,
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
            overlay=overlay,
            persist=persist,
        )


def polling_due(clock):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    return trading_day(local.date()) and (8, 35) <= (local.hour, local.minute) <= (9, 5)


def scores_ready(records, cutoff):
    return any(
        r["status"] in {"ok", "degraded"} and r.get("ended_at") is not None and r["ended_at"] <= cutoff for r in records
    )


def scheduled(*, clock, values):
    if not polling_due(clock):
        return {"status": "not_due"}
    with connect(values) as operations:
        target = clock.today_trade_date()
        lock = "M4:paper_plan:" + str(target)
        acquired = operations.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired", (lock,)
        ).fetchone()["acquired"]
        if not acquired:
            return {"status": "already_running"}
        try:
            return _scheduled_locked(clock=clock, values=values, operations=operations, target=target)
        finally:
            operations.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (lock,))


def _scheduled_locked(*, clock, values, operations, target):
    repository = OperationalRepository(operations)
    existing = operations.execute(
        "SELECT id FROM ingest.job_runs WHERE task_name='paper_plan' AND trade_date=%s LIMIT 1", (target,)
    ).fetchone()
    if existing:
        return {"status": "already_attempted"}
    signal_day = exchange(target.year).previous_session(str(target)).date()
    rows = operations.execute(
        "SELECT status,ended_at FROM ingest.job_runs WHERE task_name='rule_a_scores' AND trade_date=%s",
        (signal_day,),
    ).fetchall()
    ready = scores_ready(rows, clock.now_utc())
    if not ready or not due(clock):
        if due(clock):
            return {"status": "waiting_dependencies"}
        stamp = clock.now_utc()
        reason = (
            "skipped_upstream: rule_a_scores " + str(signal_day) + " not ready before ET09:05"
            if not ready
            else "skipped_window: paper_plan was not started before ET09:05"
        )
        repository.write_job(
            {
                "task_name": "paper_plan",
                "trade_date": target,
                "started_at": stamp,
                "ended_at": clock.now_utc(),
                "status": "failed",
                "processed_count": 0,
                "error_summary": reason,
                "params_version": "p-2026.10",
            }
        )
        return {"status": "failed", "processed_count": 0, "error": reason}
    runner = JobRunner(
        clock=clock,
        health=HealthBook(clock=clock, rows=repository.health_rows(), persist=repository.write_health),
        persist=repository.write_job,
        persist_start=repository.write_job,
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

    return runner.run("paper_plan", "RuleAPaper", operation, trade_date=target)


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
