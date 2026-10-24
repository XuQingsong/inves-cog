"""Resident review loop. Jobs stay on the default connection; review tables use the perception login."""

import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.repository import json_text
from inves_cog.perception.review.schedule import review_day, run_cycle

_QUIET = {"not_due", "already_attempted", "waiting_dependencies"}


class _EnvironmentClient:
    """Build the model client on the first call, not at import or when the writer is missing."""

    def call(self, task, payload):
        from inves_cog.llm.client import Client

        return Client.from_environment().call(task, payload)


def run_once(*, clock, connection, writer, client=None):
    moment = clock.now_utc()
    day = review_day(moment)

    def records(task):
        if day is None:
            return []
        return list(
            connection.execute(
                """
                SELECT task_name, status, ended_at, error_summary, processed_count
                FROM ingest.job_runs
                WHERE trade_date = %s AND task_name = %s
                ORDER BY id
                """,
                (day, task),
            ).fetchall()
        )

    return run_cycle(moment, records=records, connection=connection, writer=writer, clock=clock, client=client)


def main():
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment

    values = read_environment()
    clock = SystemClock()
    while True:
        connection = None
        writer = None
        try:
            connection = connect(values)
            writer_url = values.get("INVES_COG_PERCEPTION_DATABASE_URL")
            writer = connect({"INVES_COG_DATABASE_URL": writer_url}) if writer_url else None
            result = run_once(clock=clock, connection=connection, writer=writer, client=_EnvironmentClient())
            if result["status"] not in _QUIET:
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        finally:
            if writer is not None:
                writer.close()
            if connection is not None:
                connection.close()
        time.sleep(30)


if __name__ == "__main__":
    main()
