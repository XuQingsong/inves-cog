"""Strong dependencies wait until the deadline, then record skipped_upstream. Success is a job row."""

from datetime import datetime
from zoneinfo import ZoneInfo

from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.review.calendar import is_session

NY = ZoneInfo("America/New_York")
PARAMS = "m10-review-v1"
FINISHED = {"ok", "degraded"}
# (start hour, start minute), (deadline hour, deadline minute), upstream task names.
WINDOWS = {
    "review_labels": ((7, 31), (7, 40), ("anomaly_daily",)),
    "review_snapshots": ((21, 12), (21, 20), ("market_structure",)),
    "review_reports": ((7, 41), (7, 50), ("review_labels", "review_snapshots")),
}


def poll(task, moment, *, records, connection=None, clock=None, operation=None):
    if task not in WINDOWS:
        raise ValueError("未知任务")
    if not _in_window(task, moment):
        return {"status": "not_due"}
    day = moment.astimezone(NY).date()
    own = list(records(task) or [])
    if _classify(own) != "run":
        return {"status": "already_attempted"}
    missing = _missing(task, moment, records)
    if missing:
        if not _at_deadline(task, moment):
            return {"status": "waiting_dependencies"}
        summary = "skipped_upstream: " + "；".join(missing)
        if connection is not None and clock is not None:
            _write_skip(connection, task, day, summary, clock)
        return {"status": "failed", "error_summary": summary}
    if operation is not None:
        operation()
    elif connection is not None and clock is not None:
        run_recorded(
            connection,
            clock=clock,
            task_name=task,
            trade_date=day,
            params_version=PARAMS,
            operation=lambda: 0,
        )
    found = list(records(task) or [])
    if not any(row.get("status") in FINISHED for row in found):
        return {"status": "failed", "reason": "no_job_row"}
    return {"status": "ok"}


def _missing(task, moment, records):
    missing = []
    for name in WINDOWS[task][2]:
        rows = list(records(name) or [])
        if _ready(rows, moment):
            continue
        if not rows:
            missing.append(name + " 没有记录")
        else:
            missing.append(name + " 状态 " + str(rows[-1].get("status")))
    return missing


def _classify(rows):
    if any(row.get("status") in FINISHED for row in rows):
        return "done"
    if any(str(row.get("error_summary") or "").startswith("skipped_upstream:") for row in rows):
        return "skipped"
    return "run"


def _ready(rows, moment):
    for row in rows:
        ended = _aware(row.get("ended_at"))
        if row.get("status") in FINISHED and ended is not None and ended <= moment:
            return True
    return False


def _aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    return None


def _in_window(task, moment):
    local = moment.astimezone(NY)
    if not is_session(local.date()):
        return False
    start, end, _ = WINDOWS[task]
    current = (local.hour, local.minute)
    return start <= current <= end


def _at_deadline(task, moment):
    local = moment.astimezone(NY)
    return (local.hour, local.minute) == WINDOWS[task][1]


def _write_skip(connection, task, day, summary, clock):
    def refuse():
        raise RuntimeError(summary)

    try:
        run_recorded(
            connection,
            clock=clock,
            task_name=task,
            trade_date=day,
            params_version=PARAMS,
            operation=refuse,
        )
    except RuntimeError:
        return
