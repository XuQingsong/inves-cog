"""Poll one M10 review task across its ET window. A green exit without a job row is not success."""

import sys
from datetime import datetime

from inves_cog.clock import FrozenClock, SystemClock
from inves_cog.perception.review.schedule import poll


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: schedule_review.py <task> [iso-timestamp]")
    task = args[0]
    if len(args) > 1:
        moment = datetime.fromisoformat(args[1])
        clock = FrozenClock(moment)
    else:
        clock = SystemClock()
        moment = clock.now_utc()
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment

    values = read_environment()
    with connect(values) as connection:
        result = poll(
            task,
            moment,
            records=lambda name: _rows(connection, moment, name),
            connection=connection,
            clock=clock,
        )
    return 0 if result.get("status") in {"ok", "already_attempted", "not_due", "waiting_dependencies"} else 1


def _rows(connection, moment, task):
    from zoneinfo import ZoneInfo

    day = moment.astimezone(ZoneInfo("America/New_York")).date()
    return list(
        connection.execute(
            """
            SELECT task_name, status, ended_at, error_summary
            FROM ingest.job_runs
            WHERE trade_date = %s AND task_name = %s
            ORDER BY id
            """,
            (day, task),
        ).fetchall()
    )


if __name__ == "__main__":
    raise SystemExit(main())
