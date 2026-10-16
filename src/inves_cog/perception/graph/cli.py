"""Graph tasks and explicit batch review, without a local TCP service."""

import argparse
from pathlib import Path

import yaml

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.http import HTTPClient
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.repository import Repository as OperationalRepository
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.sec_client import SECClient
from inves_cog.ingest.settings import read_environment
from inves_cog.llm.client import Client
from inves_cog.perception.graph.repository import Repository
from inves_cog.perception.graph.service import GraphService

ROOT = Path(__file__).resolve().parents[4]


def run(*, action, values, clock, basket=None, identifiers=(), edits=None, revisions=None):
    writer = {**values, "INVES_COG_DATABASE_URL": values.get("INVES_COG_GRAPH_DATABASE_URL")}
    with connect(writer) as connection:
        repository = Repository(connection)
        if action == "list":
            return repository.candidates(basket)
        if action in {"confirm", "reject", "modify"}:
            if not identifiers:
                raise ValueError("Review requires explicit identifiers")
            return repository.review(
                list(identifiers), action=action, clock=clock, edits=edits, expected_revisions=revisions
            )
        if action == "cluster":
            from inves_cog.perception.graph.weekly import weekly_suggestions

            def operation():
                return weekly_suggestions(repository, day=clock.today_trade_date(), clock=clock)
        elif action == "monitored":
            operation = repository.refresh_monitored
        else:
            operation = None
        service = GraphService(
            repository=repository,
            sec=SECClient(user_agent=values["SEC_USER_AGENT"], http=HTTPClient(pool=True)),
            llm=Client.from_environment(values, clock=clock),
            clock=clock,
            universe=yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"],
            connection_factory=lambda: connect(writer),
        )
        with connect(values) as operational:
            op = OperationalRepository(operational)
            runner = JobRunner(
                clock=clock,
                health=HealthBook(clock=clock, rows=op.health_rows(), persist=op.write_health),
                persist=op.write_job,
                timeout_seconds=1800,
            )
            return runner.run(
                "graph_" + action,
                "GraphDrafts",
                operation
                or (
                    {"seed": service.seed_config, "structured": service.draft_structured}.get(action, service.draft_all)
                ),
            )


def main():
    import json

    parser = argparse.ArgumentParser(description="Graph drafting and batch review")
    parser.add_argument(
        "action", choices=["seed", "draft", "structured", "cluster", "monitored", "list", "confirm", "reject", "modify"]
    )
    parser.add_argument("--basket")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--edits", type=Path)
    parser.add_argument("--revisions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(
        action=args.action,
        values=read_environment(),
        clock=SystemClock(),
        basket=args.basket,
        identifiers=args.ids or [],
        edits=json.loads(args.edits.read_text()) if args.edits else None,
        revisions=json.loads(args.revisions.read_text()) if args.revisions else None,
    )
    rendered = json_text(result)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
