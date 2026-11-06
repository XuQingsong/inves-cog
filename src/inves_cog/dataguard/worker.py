"""One bounded recovery worker. No model calls, historical plan reruns, or parallel children."""

import argparse
import os
import resource
import signal
import sys
from datetime import date, timedelta

from inves_cog.clock import SystemClock
from inves_cog.dataguard.reader import findings, load, read
from inves_cog.dataguard.receipts import ReceiptWriter
from inves_cog.dataguard.recovery import attempt, eligible, limited_run, slice_resources
from inves_cog.dataguard.service import ROOT, connect, load_values
from inves_cog.dataguard.store import Store


def recover(item, day, now, values):
    entry = item.backfill["entry"]
    if entry in {"bars_full", "wide_universe", "vix_daily"}:
        return limited_run(
            [sys.executable, "-m", "inves_cog.ingest.cli", "run", "--tasks", entry, "--trade-date", str(day)],
            cwd=ROOT,
            env={**os.environ, **values},
            timeout=600,
        )
    if entry == "barometer":
        from inves_cog.perception.barometer.run import persist, run_range

        with connect(values, writer=True) as db:
            records = run_range(db, day, day)
            persist(db, records)
            return bool(records)
    from inves_cog.flows import backfill
    from inves_cog.flows.collectors import collect_occ
    from inves_cog.flows.store import DEFAULT_RAW, polite_http

    with connect(values, writer=True) as db, db.transaction():
        receipt = ReceiptWriter(db, day=day, now=now, filters=item.filter)
        http = polite_http()
        if entry == "finra_short":
            from inves_cog.dataguard.finra import collect

            collect(http, db, DEFAULT_RAW, day=day, tickers=item.filter.get("ticker", ()), now=now)
        elif entry == "yahoo_px":
            backfill.backfill_yahoo_px(http, receipt, DEFAULT_RAW, day, day, now)
        elif entry == "occ":
            backfill.backfill_occ(http, receipt, DEFAULT_RAW, day, day, now)
        elif entry == "occ_oi":
            collect_occ(http, receipt, day, DEFAULT_RAW, kind="oi", published_at=now)
        elif entry == "cboe_pc":
            backfill.backfill_cboe_pc(http, receipt, DEFAULT_RAW, day, day, now)
        elif entry == "cboe_idx":
            backfill.backfill_cboe_index(http, receipt, DEFAULT_RAW, day, now)
        elif entry == "etf":
            backfill.backfill_proshares(http, receipt, DEFAULT_RAW, day, now)
            backfill.backfill_ssga(http, receipt, DEFAULT_RAW, day, now)
        elif entry == "cftc":
            backfill.backfill_cftc(http, receipt, DEFAULT_RAW, day, day, now)
        elif entry == "fred":
            backfill.backfill_fred(http, receipt, DEFAULT_RAW, now)
        elif entry == "ofr":
            backfill.backfill_ofr(http, receipt, DEFAULT_RAW, now)
        elif entry == "finra_margin":
            backfill.backfill_finra_margin(http, receipt, DEFAULT_RAW, now)
        else:
            return False
    return True  # authoritative success still requires downstream and source recheck below


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--kind", required=True, choices=["missing", "partial", "stale", "job_failed"])
    args = parser.parse_args()
    values = load_values()
    _, items = load(ROOT / "config/data_expectations.yaml")
    item = next(i for i in items if i.dataset == args.dataset)
    clock = SystemClock()

    # This process has its own wall-clock deadline even if the scheduler/SSH disappears.
    def stop(*_):
        raise TimeoutError("recovery deadline or termination")

    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGTERM, stop)
    signal.alarm(900)
    os.nice(19)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    with connect(values, writer=True) as writer, connect(values) as reader:
        if not writer.execute("SELECT pg_try_advisory_lock(hashtextextended('data_guard_recovery',0)) ok").fetchone()[
            "ok"
        ]:
            return
        first = writer.execute(
            "SELECT first_started_at,detect_only FROM ops.data_guard_runtime WHERE singleton"
        ).fetchone()
        now = clock.now_utc()
        if (
            values.get("INVES_DATAGUARD_BACKFILL") != "1"
            or not first
            or first["detect_only"]
            or now < first["first_started_at"] + timedelta(days=1)
        ):
            return
        row = writer.execute(
            "SELECT * FROM ops.data_gaps WHERE dataset=%s AND data_date=%s AND kind=%s",
            (args.dataset, args.date, args.kind),
        ).fetchone()
        if not row or not eligible(row, now, detect_only=False, resources=slice_resources()):
            return
        store = Store(writer)

        def persist(row):
            stamp = clock.now_utc()
            if row["status"] == "resolved":
                row["resolved_at"] = stamp
            with writer.transaction():
                store.transition(row, stamp)
                if row["status"] in {"resolved", "unrecoverable"}:
                    key = f"{row['dataset']}:{row['data_date']}:{row['kind']}:{row['generation']}:{row['status']}"
                    store.enqueue([key], [row], stamp)

        def downstream():
            for name in item.backfill.get("depends_on", []):
                if name != "barometer" or not recover(_barometer(items), args.date, clock.now_utc(), values):
                    return False
            return True

        def recheck():
            grouped = read(reader, item, args.date - timedelta(days=10), args.date, clock.now_utc())
            return not findings(item, args.date, grouped)

        maximum = item.backfill.get("max_attempts", 3)
        if row["attempts"] >= maximum:
            row.update(status="unrecoverable", reason="已达到重试上限，禁止再次自动启动")
            persist(row)
            return
        attempt(
            row,
            now,
            max_attempts=maximum,
            run=lambda: recover(item, args.date, clock.now_utc(), values),
            downstream=downstream,
            recheck=recheck,
            persist=persist,
        )
    signal.alarm(0)


def _barometer(items):
    return next(i for i in items if i.table == "flows.barometer_daily")


if __name__ == "__main__":
    main()
