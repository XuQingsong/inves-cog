"""Poll the morning page's existing slot; persist each attempt without logging page contents."""

import json
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.clock import SystemClock
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.settings import read_environment
from inves_cog.perception.attribution.chain import job_slot

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")


def child_environment(root, load_environment):
    values = dict(load_environment(root / ".env"))
    folder = Path(values.get("INVES_COG_PAGE_DIR") or root.parent / "daily-pages").expanduser()
    folder = (folder if folder.is_absolute() else root / folder).resolve()
    if folder.is_relative_to(root):
        raise ValueError("Morning page output must be outside the repository")
    values["INVES_COG_PAGE_DIR"] = str(folder)
    return values


def run_once(*, clock, root=ROOT, python=None, run=subprocess.run, load_environment=read_environment):
    moment = clock.now_utc()
    slot = job_slot(moment)
    if slot is None or slot["task_name"] != "attribution_candidates" or not trading_day(moment.astimezone(NY).date()):
        return {"status": "not_due"}
    root = Path(root).resolve()
    state = root / ".harness/service"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    local = moment.astimezone(SHANGHAI)
    name = "morning-page-" + str(local.date()) + "-" + slot["beijing"].replace(":", "") + ".json"
    attempt = state / name
    result = {"status": "attempted", "beijing_date": str(local.date()), "slot": slot["beijing"]}
    try:
        # Atomic claim before dispatch: a crash or a nonzero child exit never
        # causes two processes/restarts to invoke the same day's minute twice.
        with attempt.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result))
    except FileExistsError:
        return {"status": "already_attempted"}
    try:
        values = child_environment(root, load_environment)
        completed = run(
            [str(python or sys.executable), "-m", "inves_cog.perception.attribution.morning"],
            cwd=root,
            env=values,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        result.update(status="ok" if completed.returncode == 0 else "failed", returncode=completed.returncode)
    except Exception as exc:
        # Neither the child output nor exception text is safe to put in service logs.
        result.update(status="failed", error_type=type(exc).__name__)
    attempt.write_text(json.dumps(result), encoding="utf-8")
    return result


def main():
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock=clock)
            if result["status"] not in {"not_due", "already_attempted"}:
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
