"""Run or schedule the price-only market structure task."""

import argparse
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import trading_day
from inves_cog.ingest.repository import Repository as OperationalRepository
from inves_cog.ingest.settings import read_environment
from inves_cog.marketstate.repository import Repository
from inves_cog.marketstate.service import MarketService, json_value

ROOT = Path(__file__).resolve().parents[3]


def selected_tickers(connection, day):
    from inves_cog.ingest.market_structure import price_universe

    seeds = [r["ticker"] for r in yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]]
    return sorted(set(seeds) | set(price_universe(connection, day)))


def completed_day(clock):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    day = local.date()
    if (local.hour, local.minute) < (20, 45):
        day -= timedelta(days=1)
    while not trading_day(day):
        day -= timedelta(days=1)
    return day


def run(*, clock, values, day, schedule=False):
    writer = {**values, "INVES_COG_DATABASE_URL": values.get("INVES_COG_MARKETSTATE_DATABASE_URL")}
    with connect(writer) as connection, connect(values) as operations:
        operational = OperationalRepository(operations)
        if schedule:
            local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
            last = operational.last_runs(trade_date=day).get("market_structure")
            slot = local.replace(hour=20, minute=45, second=0, microsecond=0)
            if day != local.date() or not trading_day(day) or local < slot or last is not None and last >= slot:
                return {"status": "not_due"}
            bar = operations.execute(
                "SELECT status FROM ingest.job_runs WHERE task_name='bars_full' AND trade_date=%s "
                "ORDER BY started_at DESC LIMIT 1",
                (day,),
            ).fetchone()
            if bar is None or bar["status"] not in {"ok", "degraded"}:
                return {"status": "waiting_bars"}
        service = MarketService(repository=Repository(connection), clock=clock)
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=operational.health_rows(), persist=operational.write_health),
            persist=operational.write_job,
            timeout_seconds=600,
        )
        return runner.run(
            "market_structure",
            "MarketStructure",
            lambda: service.run(day, tickers=selected_tickers(operations, day)),
            trade_date=day,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "schedule"])
    parser.add_argument("--trade-date", type=date.fromisoformat)
    args, clock = parser.parse_args(), SystemClock()
    print(
        json_value(
            run(
                clock=clock,
                values=read_environment(),
                day=args.trade_date
                or (clock.today_trade_date() if args.action == "schedule" else completed_day(clock)),
                schedule=args.action == "schedule",
            )
        )
    )


if __name__ == "__main__":
    main()
