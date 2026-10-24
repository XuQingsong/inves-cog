"""Strong dependencies wait until the deadline, then record skipped_upstream. Success is a job row."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.review.calendar import add_sessions, cutoff, is_session

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


# Resident review for session D runs on calendar D+1, ET 01:00 through 07:30.
# poll() above keeps the older per-task windows; this path calls the real writers.
UPSTREAM = ("anomaly_daily", "attribution_labels", "bars_full")
_DAILY = ("review_snapshots", "review_labels", "review_oneliner")
_WEEKLY = ("review_weekly_sample", "review_weekly_report")
_MONTHLY = ("review_monthly_sample", "review_monthly_report")
_OPEN = (1, 0)
_DEADLINE = (7, 30)
_MISSING_WRITER = "缺少 INVES_COG_PERCEPTION_DATABASE_URL"


def review_day(moment):
    """Session D whose review window contains this ET clock, or None."""
    local = moment.astimezone(NY)
    current = (local.hour, local.minute)
    if current < _OPEN or current > _DEADLINE:
        return None
    day = local.date() - timedelta(days=1)
    if not is_session(day) or cutoff(day) > moment:
        return None
    return day


def due_tasks(day):
    """Daily tasks, plus the week pair and the month pair when D is that period's last session."""
    tasks = list(_DAILY)
    nxt = add_sessions(day, 1)
    if nxt.isocalendar()[:2] != day.isocalendar()[:2]:
        tasks.extend(_WEEKLY)
    if (nxt.year, nxt.month) != (day.year, day.month):
        tasks.extend(_MONTHLY)
    return tasks


def run_cycle(moment, *, records, connection, writer, clock, client=None):
    """Dispatch the real review jobs once. A missing writer returns before any model call."""
    day = review_day(moment)
    if day is None:
        return {"status": "not_due"}
    pending = [task for task in due_tasks(day) if _pending(task, records)]
    if not pending:
        return {"status": "already_attempted", "trade_date": day.isoformat()}
    missing = _upstream_missing(records, moment)
    if missing:
        if (moment.astimezone(NY).hour, moment.astimezone(NY).minute) != _DEADLINE:
            return {"status": "waiting_dependencies", "trade_date": day.isoformat()}
        summary = "skipped_upstream: " + "；".join(missing)
        for task in pending:
            _write_skip(connection, task, day, summary, clock)
        return {"status": "failed", "trade_date": day.isoformat(), "error_summary": summary}
    if writer is None:
        _write_skip(connection, pending[0], day, _MISSING_WRITER, clock)
        return {"status": "failed", "trade_date": day.isoformat(), "error_summary": _MISSING_WRITER}
    for task in pending:
        run_recorded(
            connection,
            clock=clock,
            task_name=task,
            trade_date=day,
            params_version=PARAMS,
            operation=_operation(task, day, connection, writer, clock, client),
        )
    return {"status": "ok", "trade_date": day.isoformat(), "tasks": pending}


def _pending(task, records):
    rows = list(records(task) or [])
    if task == "review_oneliner" and rows:
        return False
    return _classify(rows) == "run"


def _upstream_missing(records, moment):
    missing = []
    for name in UPSTREAM:
        rows = list(records(name) or [])
        if _ready(rows, moment):
            continue
        if not rows:
            missing.append(name + " 没有记录")
        else:
            missing.append(name + " 状态 " + str(rows[-1].get("status")))
    return missing


def _operation(task, day, reader, writer, clock, client):
    def run():
        if task == "review_snapshots":
            from inves_cog.perception.review.snapshots import write_snapshots

            return write_snapshots(writer, day)
        if task == "review_labels":
            from inves_cog.perception.review.cases import run_labels

            return run_labels(writer, day, clock)
        if task == "review_oneliner":
            return _write_oneliner(writer, day, clock, client)
        if task == "review_weekly_sample":
            from inves_cog.perception.review.samples import sample_weekly

            return len(sample_weekly(writer, day))
        if task == "review_weekly_report":
            from inves_cog.perception.review.reports import store_weekly

            store_weekly(reader, day, clock, writer=writer)
            return 1
        if task == "review_monthly_sample":
            from inves_cog.perception.review.samples import sample_monthly

            drawn = sample_monthly(writer, day)
            return len(drawn["moves"]) + len(drawn["companies"])
        if task == "review_monthly_report":
            from inves_cog.perception.review.reports import store_monthly

            store_monthly(reader, day, clock, writer=writer)
            return 1
        raise ValueError("未知任务")

    return run


def _write_oneliner(writer, day, clock, client):
    from inves_cog.perception.review.oneliner import ground, store_oneliner, template_sentence

    visible = cutoff(day)
    rows = writer.execute(
        """
        SELECT anomaly_id FROM perception.anomalies
        WHERE trade_date = %s AND universe = 'pool'
          AND (generated_at IS NULL OR generated_at < %s)
        ORDER BY anomaly_id
        """,
        (day, visible),
    ).fetchall()
    page = {
        "date": day,
        "counts": {"anomaly_count": len(rows)},
        "anomalies": [{"anomaly_id": row["anomaly_id"]} for row in rows],
    }
    sentence = template_sentence(len(rows)) if client is None else ground(client, page)
    store_oneliner(writer, day, clock, sentence)
    return 1
