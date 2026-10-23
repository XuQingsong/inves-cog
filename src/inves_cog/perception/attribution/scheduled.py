"""Run the stored 09:30 and 12:30 stages. The morning page stays the 09:15 entry."""

import sys

from inves_cog.perception.attribution.chain import _closed_trade_date, run_scheduled
from inves_cog.perception.attribution.morning import (
    PARAMS,
    _connections,
    _fail_job,
    _load,
    _moment,
    _record_clock,
    _require_writer,
    in_stage_window,
    job_rows,
    stage_cutoff,
    upstream_ready,
)
from inves_cog.perception.attribution.store import Store

_TASKS = ("attribution_tracks", "attribution_labels")
_PREVIOUS = {
    "attribution_tracks": "attribution_candidates",
    "attribution_labels": "attribution_tracks",
}


def main(argv=None, *, connection=None, perception=None, clock=None, client=None, record_clock=None):
    """Run only the named stage at its own minute. Tests inject both connections and the clock."""
    args = list(sys.argv[1:] if argv is None else argv)
    task_name = _named(args)
    moment = _moment(args, clock)
    if not _due(moment, task_name):
        print("not-due")
        return 0
    borrowed, writer, owned = _connections(connection, perception)
    try:
        return _execute(borrowed, writer, moment, task_name, client, _record_clock(record_clock))
    finally:
        for item in owned:
            item.close()


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
    """The whole wait window is due. The visibility cutoff stays at the window open."""
    return in_stage_window(task_name, moment)


def _execute(connection, writer, moment, task_name, client, record_clock):
    cutoff = stage_cutoff(task_name, moment)
    day = _closed_trade_date(cutoff)
    if writer is None:
        return _fail_job(
            connection,
            moment,
            task_name,
            day,
            "缺少 INVES_COG_PERCEPTION_DATABASE_URL",
            clock=record_clock,
        )
    if writer is not connection:
        try:
            _require_writer(writer)
        except Exception as exc:
            return _fail_job(connection, moment, task_name, day, str(exc), clock=record_clock)
    if client is None:
        from inves_cog.llm.client import Client

        client = Client.from_environment()
    previous = _PREVIOUS[task_name]
    if not upstream_ready(job_rows(connection, day, previous), moment, previous):
        return _fail_job(connection, moment, task_name, day, f"缺少已成功的{previous}", clock=record_clock)
    try:
        loaded = _load(connection, cutoff, day)
    except Exception:
        return _fail_job(connection, moment, task_name, day, "读取上一阶段失败", clock=record_clock)
    try:
        run_scheduled(
            cutoff,
            anomalies=loaded["anomalies"],
            items=loaded["items"],
            client=client,
            store=Store(writer),
            connection=connection,
            writer=None if writer is connection else writer,
            clock=record_clock,
            trade_date=day,
            params_version=PARAMS,
            valuation=loaded["valuation"],
            plan=loaded["plan"],
            holdings=loaded["holdings"],
        )
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
