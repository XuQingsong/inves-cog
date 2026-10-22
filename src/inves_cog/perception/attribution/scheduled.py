"""Run the stored 09:30 and 12:30 stages. The morning page stays the 09:15 entry."""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import trading_day
from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.attribution.chain import _closed_trade_date, job_slot, run_scheduled
from inves_cog.perception.attribution.morning import PARAMS, _borrow, _load, _moment
from inves_cog.perception.attribution.store import Store

_TASKS = ("attribution_tracks", "attribution_labels")
_PREVIOUS = {
    "attribution_tracks": "attribution_candidates",
    "attribution_labels": "attribution_tracks",
}
_NEW_YORK = ZoneInfo("America/New_York")


class _Frozen:
    def __init__(self, moment):
        self._moment = moment

    def now_utc(self):
        return self._moment


def main(argv=None, *, connection=None, clock=None, client=None):
    """Run only the named stage at its own minute. Tests inject the connection and clock."""
    args = list(sys.argv[1:] if argv is None else argv)
    task_name = _named(args)
    moment = _moment(args, clock)
    if not _due(moment, task_name):
        return 0
    borrowed, owned = _borrow(connection)
    try:
        return _execute(borrowed, moment, task_name, client)
    finally:
        if owned:
            borrowed.close()


def _named(args):
    if "--task" not in args:
        raise SystemExit("需要 --task")
    index = args.index("--task")
    if index + 1 >= len(args):
        raise SystemExit("需要 --task 后面的任务名")
    name = args[index + 1]
    if name not in _TASKS:
        raise SystemExit("任务只接受 attribution_tracks 或 attribution_labels")
    return name


def _due(moment, task_name):
    slot = job_slot(moment)
    if slot is None or slot["task_name"] != task_name:
        return False
    return trading_day(moment.astimezone(_NEW_YORK).date())


def _execute(connection, moment, task_name, client):
    if client is None:
        from inves_cog.llm.client import Client

        client = Client.from_environment()
    day = _closed_trade_date(moment)
    clock = _Frozen(moment)
    previous = _PREVIOUS[task_name]
    if not _previous_ready(connection, day, previous, moment):
        return _record_failure(connection, clock, task_name, day, f"缺少已成功的{previous}")
    try:
        loaded = _load(connection, moment, day)
    except Exception:
        return _record_failure(connection, clock, task_name, day, "读取上一阶段失败")
    try:
        run_scheduled(
            moment,
            anomalies=loaded["anomalies"],
            items=loaded["items"],
            client=client,
            store=Store(connection),
            connection=connection,
            clock=clock,
            trade_date=day,
            params_version=PARAMS,
            valuation=loaded["valuation"],
            plan=loaded["plan"],
            holdings=loaded["holdings"],
        )
    except Exception:
        return 1
    return 0


def _record_failure(connection, clock, task_name, day, reason):
    def refuse():
        raise RuntimeError(reason)

    try:
        run_recorded(
            connection,
            clock=clock,
            task_name=task_name,
            trade_date=day,
            params_version=PARAMS,
            operation=refuse,
        )
    except Exception:
        return 1
    return 1


def _previous_ready(connection, trade_date, previous, moment):
    rows = connection.execute(
        "SELECT task_name, status, ended_at FROM ingest.job_runs WHERE trade_date = %s AND task_name = %s",
        (trade_date, previous),
    ).fetchall()
    for row in rows:
        name = row["task_name"] if isinstance(row, dict) else row[0]
        status = row["status"] if isinstance(row, dict) else row[1]
        ended = row["ended_at"] if isinstance(row, dict) else row[2]
        ended = _aware(ended)
        if name == previous and status == "ok" and ended is not None and ended <= moment:
            return True
    return False


def _aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    return None
