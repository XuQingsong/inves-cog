"""Poll the morning page at its minute, then the candidates chain until the ET deadline."""

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
    _is_morning,
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
_CHAIN = "attribution_candidates"
_ANOMALY = "anomaly_daily"


def child_environment(root, load_environment):
    values = dict(load_environment(root / ".env"))
    folder = Path(values.get("INVES_COG_PAGE_DIR") or root.parent / "daily-pages").expanduser()
    folder = (folder if folder.is_absolute() else root / folder).resolve()
    if folder.is_relative_to(root):
        raise ValueError("Morning page output must be outside the repository")
    values["INVES_COG_PAGE_DIR"] = str(folder)
    return values


def run_once(
    *,
    clock,
    root=ROOT,
    python=None,
    run=subprocess.run,
    load_environment=read_environment,
    records=None,
    skip=None,
):
    moment = clock.now_utc()
    page_due = _is_morning(moment)
    chain_due = in_stage_window(_CHAIN, moment)
    if not page_due and not chain_due:
        return {"status": "not_due"}
    root = Path(root).resolve()
    if page_due and _ready(records, root, load_environment, _ANOMALY, moment):
        return _page(root, moment, python, run, load_environment, page_only=False)
    page_result = {"status": "not_due"}
    if page_due:
        page_result = _page(root, moment, python, run, load_environment, page_only=True)
    if not chain_due:
        return page_result
    chain_result = _chain(root, moment, clock, python, run, load_environment, records, skip)
    if page_due and chain_result["status"] not in {"waiting_dependencies", "already_attempted"}:
        return {**page_result, "chain": chain_result}
    if page_due:
        return page_result
    return chain_result


def _page(root, moment, python, run, load_environment, *, page_only):
    state = root / ".harness/service"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    local = moment.astimezone(SHANGHAI)
    attempt = state / ("morning-page-" + str(local.date()) + "-" + local.strftime("%H%M") + ".json")
    result = {"status": "attempted", "beijing_date": str(local.date()), "slot": local.strftime("%H:%M")}
    try:
        with attempt.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result))
    except FileExistsError:
        return {"status": "already_attempted"}
    command = [str(python or sys.executable), "-m", "inves_cog.perception.attribution.morning"]
    if page_only:
        command.append("--page-only")
    try:
        values = child_environment(root, load_environment)
        completed = run(
            command,
            cwd=root,
            env=values,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        result.update(status="ok" if completed.returncode == 0 else "failed", returncode=completed.returncode)
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__)
    attempt.write_text(json.dumps(result), encoding="utf-8")
    return result


def _chain(root, moment, clock, python, run, load_environment, records, skip):
    day = _closed_trade_date(moment)
    own = _lookup(records, root, load_environment, _CHAIN, day)
    if own is None:
        if at_stage_deadline(_CHAIN, moment):
            return {"status": "failed", "error_type": "LookupError"}
        return {"status": "waiting_dependencies"}
    if dispatch_decision(_CHAIN, own) != "run":
        return {"status": "already_attempted"}
    upstream = _lookup(records, root, load_environment, _ANOMALY, day)
    if upstream is None or not upstream_ready(upstream, moment, _ANOMALY):
        if not at_stage_deadline(_CHAIN, moment):
            return {"status": "waiting_dependencies"}
        summary = skip_summary([upstream_phrase(_ANOMALY, upstream or [])])
        _write_skip(root, load_environment, _CHAIN, day, summary, clock, skip)
        return {"status": "failed", "error_summary": summary}
    try:
        values = dict(load_environment(root / ".env"))
        completed = run(
            [
                str(python or sys.executable),
                "-m",
                "inves_cog.perception.attribution.morning",
                "--chain-only",
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
        return {"status": "failed", "error_type": type(exc).__name__}
    found = _lookup(records, root, load_environment, _CHAIN, day)
    if completed.returncode == 0 and not any(row.get("status") in {"ok", "degraded", "failed"} for row in found or []):
        return {"status": "failed", "returncode": 0, "reason": "no_job_row"}
    return {
        "status": "ok" if completed.returncode == 0 and upstream_ready(found, moment, _CHAIN) else "failed",
        "returncode": completed.returncode,
    }


def _ready(records, root, load_environment, task, moment):
    rows = _lookup(records, root, load_environment, task, _closed_trade_date(moment))
    return bool(rows is not None and upstream_ready(rows, moment, task))


def _lookup(records, root, load_environment, task, day):
    if records is not None:
        return list(records(task, day) or [])
    try:
        from inves_cog.ingest.cli import connect

        values = dict(load_environment(root / ".env"))
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

    values = dict(load_environment(root / ".env"))
    with connect(values) as connection:
        record_skip(connection, task, day, summary, clock)


def main():
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock=clock)
            if result["status"] not in {"not_due", "already_attempted", "waiting_dependencies"}:
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
