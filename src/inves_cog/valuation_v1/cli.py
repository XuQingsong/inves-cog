"""Explicit read-only probes or role-scoped writes; production registration is separate."""

import argparse
import json
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import exchange, trading_day
from inves_cog.ingest.repository import Repository as Operations
from inves_cog.ingest.settings import read_environment
from inves_cog.valuation_v1.calculations import LABEL
from inves_cog.valuation_v1.repository import Repository
from inves_cog.valuation_v1.service import build

ROOT = Path(__file__).resolve().parents[3]


def latest_closed_day(clock):
    current = clock.today_trade_date()
    cal = exchange(current.year)
    session = cal.date_to_session(current, direction="previous")
    if clock.now_utc() < cal.session_close(session):
        session = cal.previous_session(session)
    return session.date()


def due(clock, last=None):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    return (
        trading_day(local.date())
        and local.time() >= time(22, 30)
        and (last is None or last.astimezone(local.tzinfo).date() < local.date())
    )


def run(*, clock, values, persist=True, target=None, connection=None, book=None):
    target = target or latest_closed_day(clock)
    if target > latest_closed_day(clock):
        raise ValueError("不能估值尚未收盘的交易日")
    universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]
    if connection is not None:
        return build(
            clock=clock, repository=Repository(connection), universe=universe, as_of=target, persist=persist, book=book
        )
    url = values.get("INVES_COG_VALUATION_DATABASE_URL")
    if not url:
        raise ValueError("未配置估值角色数据库连接")
    with connect({**values, "INVES_COG_DATABASE_URL": url}) as db:
        if not persist:
            db.execute("SET default_transaction_read_only=on")
        return build(
            clock=clock, repository=Repository(db), universe=universe, as_of=target, persist=persist, book=book
        )


def scheduled(*, clock, values):
    # The operational role writes job_runs, while the valuation role can write
    # only valuation_v1; neither client gains the other's table permissions.
    with connect(values) as operations:
        repo = Operations(operations)
        if not due(clock, repo.last_runs().get("valuation_v1")):
            return {"label": LABEL, "status": "not_due"}
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=repo.health_rows(), persist=repo.write_health),
            persist=repo.write_job,
            persist_start=repo.write_job,
        )
        return {"label": LABEL, **runner.run("valuation_v1", "ValuationV1", lambda: run(clock=clock, values=values))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["run", "scheduled"])
    p.add_argument("--date", type=date.fromisoformat)
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    out = (
        run(clock=SystemClock(), values=read_environment(), persist=not args.read_only, target=args.date)
        if args.action == "run"
        else scheduled(clock=SystemClock(), values=read_environment())
    )
    value = json.dumps(out, default=str, ensure_ascii=False, allow_nan=False, indent=2)
    if args.output:
        args.output.write_text(value + "\n")
    else:
        print(value)


if __name__ == "__main__":
    main()
