"""Poll one later attribution slot. A failed attempt is not run again and is not marked ok."""

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
TASKS = ("attribution_tracks", "attribution_labels")


def child_environment(root, load_environment):
    return dict(load_environment(root / ".env"))


def run_once(*, clock, task_name, root=ROOT, python=None, run=subprocess.run, load_environment=read_environment):
    if task_name not in TASKS:
        raise ValueError("未知任务")
    moment = clock.now_utc()
    slot = job_slot(moment)
    if slot is None or slot["task_name"] != task_name or not trading_day(moment.astimezone(NY).date()):
        return {"status": "not_due"}
    root = Path(root).resolve()
    state = root / ".harness/service"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    local = moment.astimezone(SHANGHAI)
    name = task_name.replace("_", "-") + "-" + str(local.date()) + "-" + slot["beijing"].replace(":", "") + ".json"
    attempt = state / name
    result = {"status": "attempted", "beijing_date": str(local.date()), "slot": slot["beijing"], "task_name": task_name}
    try:
        with attempt.open("x", encoding="utf-8") as output:
            output.write(json.dumps(result))
    except FileExistsError:
        return {"status": "already_attempted"}
    try:
        values = child_environment(root, load_environment)
        completed = run(
            [
                str(python or sys.executable),
                "-m",
                "inves_cog.perception.attribution.scheduled",
                "--task",
                task_name,
            ],
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


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--task" not in args or args.index("--task") + 1 >= len(args):
        raise SystemExit("需要 --task")
    task_name = args[args.index("--task") + 1]
    clock = SystemClock()
    while True:
        try:
            result = run_once(clock=clock, task_name=task_name)
            if result["status"] not in {"not_due", "already_attempted"}:
                print(json_text(result), flush=True)
        except Exception as exc:
            print(json_text({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
