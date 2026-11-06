"""Bounded recovery policy; successful exit alone never resolves a gap."""

import os
import resource
import signal
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass(frozen=True)
class ResourceState:
    memory_alarm: bool = False
    io_alarm: bool = False
    known: bool = True


def eligible(row, now, *, detect_only, resources):
    if detect_only or not resources.known or resources.memory_alarm or resources.io_alarm:
        return False
    if row["kind"] == "suspect" or row["status"] != "open":
        return False
    last = row.get("last_attempt_at")
    return last is None or now >= last + timedelta(minutes=10 * max(1, row["attempts"]))


def attempt(row, now, *, max_attempts, run, downstream, recheck, persist):
    row.update(status="backfilling", attempts=row["attempts"] + 1, last_attempt_at=now)
    persist(row)  # durable before spawning; a crash is not permission to duplicate the child
    try:
        success = run() and downstream() and recheck()
    except Exception:
        success = False
    if success:
        row.update(status="resolved", resolved_at=now)
    elif row["attempts"] >= max_attempts:
        row.update(status="unrecoverable", reason="补数达到重试上限，数据或下游仍未通过复核")
    else:
        row.update(status="open", reason="补数后数据或下游仍未通过复核")
    persist(row)


def slice_resources(root=Path("/sys/fs/cgroup"), uid=None):
    """Current kernel state, never an old log line. Unknown fails closed for recovery only."""
    uid = os.getuid() if uid is None else uid
    path = root / f"user.slice/user-{uid}.slice"
    try:
        current = int((path / "memory.current").read_text())
        maximum = (path / "memory.max").read_text().strip()
        memory = maximum != "max" and current / int(maximum) >= 0.85
        full = next(line for line in (path / "io.pressure").read_text().splitlines() if line.startswith("full "))
        io = float(dict(part.split("=") for part in full.split()[1:])["avg10"]) >= 10
        return ResourceState(memory, io)
    except (OSError, ValueError, StopIteration, KeyError, ZeroDivisionError):
        return ResourceState(known=False)


def limited_run(argv, *, cwd, env, timeout=600):
    """One bounded child/process group. Suppress provider output which may contain credentials."""

    def limits():
        os.nice(19)
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

    child = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        start_new_session=True,
        preexec_fn=limits,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        return child.wait(timeout=timeout) == 0
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        return False
