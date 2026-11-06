"""A-032: single-checker detection service with a transactional notification queue.
No credentials or provider responses are written to logs. Business data is read-only.
"""

import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import time as wall_time
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from inves_cog.clock import SystemClock
from inves_cog.dataguard.core import Finding, due_dates
from inves_cog.dataguard.mail import Mailer
from inves_cog.dataguard.reader import findings, load, read
from inves_cog.dataguard.recovery import eligible, slice_resources
from inves_cog.dataguard.store import Store
from inves_cog.ingest.market import NY
from inves_cog.ingest.settings import read_environment

ROOT = Path(__file__).resolve().parents[3]
BJ = ZoneInfo("Asia/Shanghai")
log = logging.getLogger(__name__)


def connect(values, *, writer=False):
    import psycopg
    from psycopg.rows import dict_row

    key = "INVES_COG_DATABASE_URL" if writer else "INVES_COG_WEB_DATABASE_URL"
    options = "-c statement_timeout=1000 -c lock_timeout=1000"
    if not writer:
        options += " -c default_transaction_read_only=on"
    return psycopg.connect(values[key], row_factory=dict_row, autocommit=True, options=options, connect_timeout=5)


def scan(connection, items, now, *, budget=18, monotonic=time.monotonic):
    """Pure detection over bounded source windows; caller decides whether to persist."""
    started = monotonic()
    results, errors = [], []
    for index, item in enumerate(items):
        if monotonic() - started >= budget:
            errors.extend(i.dataset for i in items[index:])
            break
        days = due_dates(item, now, lookback=70 if item.cadence == "monthly" else max(7, item.release_days + 7))
        if item.cadence.startswith("intraday:") or item.carry_forward:
            days = [now.astimezone(NY).date()] if days else []
        if not days:
            results.append((item, {}))
            continue
        try:
            grouped = read(connection, item, min(days) - timedelta(days=10), max(days), now)
            # Outside the trading window is not an empty data window.
            if item.cadence.startswith("intraday:") and not grouped:
                from inves_cog.ingest.market import regular_bounds

                bounds = regular_bounds(now.astimezone(NY).date())
                minutes = int(item.cadence.split(":")[1]) + item.grace_min
                if not bounds or not bounds[0] + timedelta(minutes=minutes) <= now <= bounds[1]:
                    results.append((item, {}))
                    continue
            results.append((item, {d: findings(item, d, grouped) for d in days}))
        except Exception as exc:
            errors.append(item.dataset)
            log.warning("data check failed dataset=%s error_type=%s", item.dataset, type(exc).__name__)
            # No reconciliation on failed reads: an old unresolved gap must not become healthy.
    return results, errors


def run_once(reader, writer, items, now, *, detect_only, values, resources=None, monotonic=time.monotonic):
    started = monotonic()
    resources = resources or slice_resources()
    results, errors = scan(reader, items, now, monotonic=monotonic)
    store = Store(writer)
    notices, keys = [], []
    checked = sum(bool(days) for _, days in results)
    complete = sum(bool(days) and not any(days.values()) for _, days in results)
    with writer.transaction():
        for item, days in results:
            for day, found in days.items():
                rows, new = store.reconcile(item.dataset, day, found, now)
                notices.extend(rows)
                keys.extend(new)
        # Failed/unfinished inspection remains visible, without closing actual source gaps.
        check_item = "数据守护检查"
        failed = (
            [
                Finding(
                    check_item,
                    now.astimezone(NY).date(),
                    "partial",
                    {"impact": "部分数据尚未完成核查，不能据此判断完整", "datasets": errors},
                )
            ]
            if errors
            else []
        )
        rows, new = store.reconcile(check_item, now.astimezone(NY).date(), failed, now)
        notices.extend(rows)
        keys.extend(new)
        store.enqueue(keys, notices, now)
        local = now.astimezone(BJ)
        if local.time() >= wall_time(8, 30):
            daily_rows = writer.execute(
                "SELECT * FROM ops.data_gaps WHERE data_date>=%s AND data_date<=%s ORDER BY data_date,dataset",
                (now.astimezone(NY).date() - timedelta(days=1), now.astimezone(NY).date()),
            ).fetchall()
            summary = (
                f"已核查{checked}项，完整{complete}项；内存告警：{resources.memory_alarm}；"
                f"IO告警：{resources.io_alarm}；资源可核实：{resources.known}"
            )
            store.enqueue([], daily_rows, now, event_key=f"daily:{local.date()}", daily=True, resources=summary)
    mailer = Mailer(values)
    mail_status = store.send_pending(mailer, now)
    duration = monotonic() - started
    writer.execute(
        "INSERT INTO ops.data_guard_runtime(singleton,first_started_at,checked_at,detect_only,"
        "mail_status,resource_status,complete_datasets,checked_datasets,duration_seconds) "
        "VALUES(true,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(singleton) DO UPDATE SET "
        "checked_at=EXCLUDED.checked_at,detect_only=EXCLUDED.detect_only,mail_status=EXCLUDED.mail_status,"
        "resource_status=EXCLUDED.resource_status,complete_datasets=EXCLUDED.complete_datasets,"
        "checked_datasets=EXCLUDED.checked_datasets,duration_seconds=EXCLUDED.duration_seconds",
        (now, now, detect_only, mail_status, Jsonb(asdict(resources)), complete, checked, duration),
    )
    return {
        "checked": checked,
        "complete": complete,
        "check_errors": len(errors),
        "seconds": round(duration, 3),
        "detect_only": detect_only,
        "mail_status": mail_status,
    }


def dispatch(writer, items, now, *, detect_only, resources, child, root=ROOT):
    if child and child.poll() is None:
        return child
    # A child from a previous daemon instance may still own this database lock.
    locked = writer.execute("SELECT pg_try_advisory_lock(hashtextextended('data_guard_recovery',0)) ok").fetchone()[
        "ok"
    ]
    if not locked:
        return None
    writer.execute("SELECT pg_advisory_unlock(hashtextextended('data_guard_recovery',0))")
    if detect_only:
        return None
    by_name = {i.dataset: i for i in items}
    rows = writer.execute(
        "SELECT * FROM ops.data_gaps WHERE status IN ('open','backfilling') "
        "ORDER BY last_attempt_at NULLS FIRST,data_date LIMIT 100"
    ).fetchall()
    store = Store(writer)
    for row in rows:
        if row["status"] == "backfilling":
            # Worker lock is free: prior worker has exited. Never count a lost SSH/daemon as completion.
            row.update(status="open", reason="上次补数进程已退出，数据仍需复核")
            store.transition(row, now)
        item = by_name.get(row["dataset"])
        if not item or not eligible(row, now, detect_only=detect_only, resources=resources):
            continue
        if item.backfill.get("entry", "manual") == "manual":
            row.update(status="unrecoverable", reason="没有可安全调用的有界补采入口，需要人工处理")
            with writer.transaction():
                store.transition(row, now)
                store.enqueue(
                    [f"{row['dataset']}:{row['data_date']}:{row['kind']}:{row['generation']}:unrecoverable"], [row], now
                )
            continue
        # The worker owns its lock, resource limits, deadline, durable transition and recheck.
        return subprocess.Popen(
            [
                "/usr/bin/timeout",
                "--kill-after=5",
                "900",
                sys.executable,
                "-m",
                "inves_cog.dataguard.worker",
                "--dataset",
                row["dataset"],
                "--date",
                str(row["data_date"]),
                "--kind",
                row["kind"],
            ],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return None


def main():
    logging.basicConfig(level=logging.INFO)
    values = read_environment()
    config, items = load(ROOT / "config/data_expectations.yaml")
    clock = SystemClock()
    child = None
    with connect(values, writer=True) as writer, connect(values) as reader:
        if not writer.execute("SELECT pg_try_advisory_lock(hashtextextended('data_guard',0)) ok").fetchone()["ok"]:
            return
        while True:
            now = clock.now_utc()
            first = writer.execute("SELECT first_started_at FROM ops.data_guard_runtime WHERE singleton").fetchone()
            day_one = not first or now < first["first_started_at"] + timedelta(days=1)
            enabled = values.get("INVES_DATAGUARD_BACKFILL") == "1"
            detect_only = day_one or not enabled
            resources = slice_resources()
            try:
                result = run_once(
                    reader, writer, items, now, detect_only=detect_only, values=values, resources=resources
                )
                child = dispatch(writer, items, now, detect_only=detect_only, resources=resources, child=child)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except Exception as exc:
                log.error("data guard cycle failed error_type=%s", type(exc).__name__)
            time.sleep(config.get("interval_seconds", 600))


if __name__ == "__main__":
    main()
