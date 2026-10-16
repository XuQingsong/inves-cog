"""Rule A daily/scheduled task. Credentials come from private environment only."""

import argparse
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.fundamentals.repository import Repository as FinancialRepository
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import trading_day
from inves_cog.ingest.repository import Repository as OperationalRepository
from inves_cog.ingest.settings import read_environment
from inves_cog.trading.scoring.repository import Repository, json_value
from inves_cog.trading.scoring.service import ScoringService

ROOT = Path(__file__).resolve().parents[4]


def due(clock, last_run=None):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    slot = local.replace(hour=22, minute=30, second=0, microsecond=0)
    return trading_day(local.date()) and local >= slot and (last_run is None or last_run < slot)


def run(*, clock, values, signal_date, extractor="fixed", schedule=False):
    writer_values = {**values, "INVES_COG_DATABASE_URL": values.get("INVES_COG_TRADING_DATABASE_URL")}
    with connect(writer_values) as connection, connect(values) as operational_connection:
        operational = OperationalRepository(operational_connection)
        if schedule:
            last = operational.last_runs(trade_date=signal_date).get("rule_a_scores")
            if signal_date != clock.today_trade_date() or not due(clock, last):
                return {"status": "not_due"}
            latest = connection.execute(
                "SELECT status FROM ingest.job_runs WHERE task_name IN ('financials',"
                "'m2_financials') AND trade_date=%s ORDER BY started_at DESC LIMIT 1",
                (signal_date,),
            ).fetchone()
            if latest is None or latest["status"] not in {"ok", "degraded"}:
                return {"status": "waiting_m2"}
        service = ScoringService(
            repository=Repository(connection),
            state_asof=FinancialRepository(connection).state_asof,
            universe=yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"],
            clock=clock,
        )
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=operational.health_rows(), persist=operational.write_health),
            persist=operational.write_job,
        )
        return runner.run(
            "rule_a_scores",
            "RuleAScoring",
            lambda: service.run(signal_date, extractor=extractor),
            trade_date=signal_date,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "schedule"])
    parser.add_argument("--signal-date", type=date.fromisoformat)
    parser.add_argument("--extractor", choices=["legacy", "fixed"], default="fixed")
    args = parser.parse_args()
    clock = SystemClock()
    print(
        json_value(
            run(
                clock=clock,
                values=read_environment(),
                signal_date=args.signal_date or clock.today_trade_date(),
                extractor=args.extractor,
                schedule=args.action == "schedule",
            )
        )
    )


if __name__ == "__main__":
    main()
