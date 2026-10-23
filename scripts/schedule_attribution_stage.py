"""Poll one later attribution stage across its ET window. Success is a job row, not an exit code."""

import json
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.clock import SystemClock
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.settings import read_environment
from inves_cog.perception.attribution.chain import _closed_trade_date
from inves_cog.perception.attribution.morning import (
    _UPSTREAM,
    at_stage_deadline,
    dispatch_decision,
    in_stage_window,
    job_rows,
    record_skip,
    skip_summary,
    upstream_phrase,
    upstream_ready,
)

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
TASKS = ("attribution_tracks", "attribution_labels")


def child_environment(root, load_environment):
    return dict(load_environment(root / ".env"))


def run_once(
    *,
    clock,
    task_name,
    root=ROOT,
    python=None,
    run=subprocess.run,
    load_environment=read_environment,
    records=None,
    skip=None,
):
    if task_name not in TASKS:
        raise ValueError("未知任务")
    moment = clock.now_utc()
    if not in_stage_window(task_name, moment):
        return {"status": "not_due"}
    root = Path(root).resolve()
    day = _closed_trade_date(moment)
    own = _lookup(records, root, load_environment, task_name, day)
    if own is None:
        if at_stage_deadline(task_name, moment):
            return _logged(root, moment, task_name, {"status": "failed", "error_type": "LookupError"})
        return {"status": "waiting_dependencies"}
    if dispatch_decision(task_name, own) != "run":
        return {"status": "already_attempted"}
    missing = []
    for name in _UPSTREAM[task_name]:
        rows = _lookup(records, root, load_environment, name, day)
        if rows is None or not upstream_ready(rows, moment, name):
            missing.append(upstream_phrase(name, rows or []))
    if missing:
        if not at_stage_deadline(task_name, moment):
            return {"status": "waiting_dependencies"}
        summary = skip_summary(missing)
        _write_skip(root, load_environment, task_name, day, summary, clock, skip)
        return _logged(root, moment, task_name, {"status": "failed", "error_summary": summary, "task_name": task_name})
    try:
        values = child_environment(root, load_environment)
        completed = run(
            [
                str(python or sys.executable),
                "-m",
                "inves_cog.perception.attribution.scheduled",
                "--task",
                task_name,
                "--at",
                moment.isoformat(),
            ],
            cwd=root,
            env=values,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception as exc:
        return _logged(
            root,
            moment,
            task_name,
            {"status": "failed", "error_type": type(exc).__name__, "task_name": task_name},
        )
    found = _lookup(records, root, load_environment, task_name, day)
    if completed.returncode == 0 and not any(row.get("status") in {"ok", "degraded", "failed"} for row in found or []):
        return _logged(
            root,
            moment,
            task_name,
            {"status": "failed", "returncode": 0, "reason": "no_job_row", "task_name": task_name},
        )
    status = "ok" if completed.returncode == 0 and upstream_ready(found, moment, task_name) else "failed"
    return _logged(
        root,
        moment,
        task_name,
        {"status": status, "returncode": completed.returncode, "task_name": task_name},
    )


def _lookup(records, root, load_environment, task, day):
    if records is not None:
        return list(records(task, day) or [])
    try:
        from inves_cog.ingest.cli import connect

        values = child_environment(root, load_environment)
        if not values.get("INVES_COG_DATABASE_URL"):
            return None
        with connect(values) as connection:
            return job_rows(connection, day, task)
    except Exception:
        return None


def _write_skip(root, load_environment, task, day, summary, clock, skip):
    if skip is not None:
        skip(task, day, summary)
        return
    from inves_cog.ingest.cli import connect

    values = child_environment(root, load_environment)
    with connect(values) as connection:
        record_skip(connection, task, day, summary, clock)


def _logged(root, moment, task_name, result):
    state = root / ".harness/service"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    local = moment.astimezone(SHANGHAI)
    name = task_name.replace("_", "-") + "-" + str(local.date()) + "-" + local.strftime("%H%M%S") + ".json"
    payload = {"beijing_date": str(local.date()), "slot": local.strftime("%H:%M"), **result}
    (state / name).write_text(json.dumps(payload), encoding="utf-8")
    return payload


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--task" not in args or args.index("--task") + 1 >= len(args):
        raise SystemExit("需要 --task")
    task_name = args[args.index("--task") + 1]
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock=clock, task_name=task_name)
            if result["status"] not in {"not_due", "already_attempted", "waiting_dependencies"}:
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
