"""Daily consensus data task; independent of M5 formulas and pages."""

import time
from pathlib import Path

import yaml

from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.repository import Repository as Operations
from inves_cog.valuation_v1.consensus import Client, Repository, collect

ROOT = Path(__file__).resolve().parents[3]


def scheduled(*, clock, values):
    key = values.get("ALPHA_VANTAGE_API_KEY")
    url = values.get("INVES_COG_VALUATION_DATABASE_URL")
    if not key or not url:
        return {"status": "not_configured", "request_count": 0}
    with connect({**values, "INVES_COG_DATABASE_URL": url}) as db:
        if not db.execute("SELECT pg_try_advisory_lock(hashtextextended('A020:collector',0)) AS ok").fetchone()["ok"]:
            return {"status": "already_running", "request_count": 0}
        repository = Repository(db)
        if not repository.available(clock.now_utc()):
            return {"status": "not_due", "request_count": 0}
        tickers = [x["ticker"] for x in yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]]
        with connect(values) as ops:
            operational = Operations(ops)
            runner = JobRunner(
                clock=clock,
                health=HealthBook(clock=clock, rows=operational.health_rows(), persist=operational.write_health),
                persist=operational.write_job,
                persist_start=operational.write_job,
            )
            return runner.run(
                "consensus_snapshots",
                "AlphaVantage",
                lambda: collect(
                    clock=clock,
                    repository=repository,
                    tickers=tickers,
                    fetch=Client(key).fetch,
                    pause=lambda: time.sleep(15),
                ),
            )
