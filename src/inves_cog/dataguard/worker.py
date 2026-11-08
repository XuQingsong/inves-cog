"""One bounded recovery worker. No model calls, historical plan reruns, or parallel children."""

import argparse
import os
import resource
import signal
import sys
from dataclasses import replace
from datetime import date, timedelta

from inves_cog.clock import SystemClock
from inves_cog.dataguard.reader import barometer_drifts, findings, load, read, wide_scope
from inves_cog.dataguard.receipts import ReceiptWriter
from inves_cog.dataguard.recovery import attempt, eligible, limited_run, slice_resources
from inves_cog.dataguard.service import ROOT, connect, load_values
from inves_cog.dataguard.store import Store


def recover(item, day, now, values, *, evidence=None, trace=None):
    evidence = {} if evidence is None else evidence
    entry = item.backfill["entry"]
    if entry in {"bars_full", "wide_universe", "vix_daily"}:
        return limited_run(
            [sys.executable, "-m", "inves_cog.ingest.cli", "run", "--tasks", entry, "--trade-date", str(day)],
            cwd=ROOT,
            env={**os.environ, **values},
            timeout=600,
        )
    if entry == "barometer":
        from inves_cog.dataguard.restatement import restate, verified

        with connect(values, writer=True) as db:
            revision = restate(db, day, now)
            evidence["restatement"] = revision
            return verified(revision)
    from inves_cog.flows import backfill
    from inves_cog.flows.collectors import collect_occ
    from inves_cog.flows.store import DEFAULT_RAW, polite_http, upsert_many

    with connect(values, writer=True) as db, db.transaction():
        receipt = ReceiptWriter(db, day=day, now=now, filters=item.filter)
        http = trace.wrap(polite_http()) if trace else polite_http()
        if entry == "finra_short":
            from inves_cog.dataguard.finra import collect

            result = collect(http, db, DEFAULT_RAW, day=day, tickers=item.filter.get("ticker", ()), now=now)
            evidence["candidate_rows"] = result["rows"]
        elif entry in ("yahoo_px", "ecb_fx"):
            getattr(backfill, "backfill_" + entry)(http, receipt, DEFAULT_RAW, day, day, now)
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
            from inves_cog.ingest.providers import FRED
            from inves_cog.ingest.repository import Repository

            fred = FRED(key=values.get("FRED_API_KEY"), clock=SystemClock())
            if "macro_observations" in item.table:
                repo = Repository(db)
                recovered = 0
                for key in item.filter.get("series_id", ()):
                    for row in fred.collect(key):
                        if row["observation_date"] == day:
                            repo.write("macro_observations", row)
                            recovered += 1
                if recovered:
                    evidence["candidate_rows"] = recovered
            else:
                rows = []
                for key in item.filter.get("series_id", ()):
                    sid = key.removeprefix("fred_").upper()
                    latest = {}
                    for r in fred.collect(sid):
                        if r["observation_date"] != day or r["value"] is None:
                            continue
                        prev = latest.get(r["observation_date"])
                        if prev is None or r["realtime_start"] > prev["realtime_start"]:
                            latest[r["observation_date"]] = r
                    rows += [
                        {
                            "series_id": key,
                            "obs_date": r["observation_date"],
                            "value": float(r["value"]),
                            "published_at": backfill.published_at_fred(sid, r["observation_date"]),
                            "vintage": "recovery",
                        }
                        for r in latest.values()
                    ]
                if rows:
                    upsert_many(
                        receipt,
                        "observations",
                        ("series_id", "obs_date", "value", "published_at", "vintage"),
                        rows,
                        "update",
                    )
        elif entry == "ofr":
            backfill.backfill_ofr(http, receipt, DEFAULT_RAW, now)
        elif entry == "finra_margin":
            backfill.backfill_finra_margin(http, receipt, DEFAULT_RAW, now)
        else:
            return False
        if entry != "finra_short":
            evidence["candidate_rows"] = evidence.get("candidate_rows", receipt.filtered_rows)
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
        if values.get("INVES_DATAGUARD_BACKFILL") != "1" or not first or first["detect_only"]:
            return
        row = writer.execute(
            "SELECT * FROM ops.data_gaps WHERE dataset=%s AND data_date=%s AND kind=%s",
            (args.dataset, args.date, args.kind),
        ).fetchone()
        if not row or not eligible(row, now, detect_only=False, resources=slice_resources()):
            return
        entry = item.backfill.get("entry")
        if entry in {"bars_full", "wide_universe", "vix_daily"}:
            original = writer.execute(
                "SELECT id FROM ingest.job_runs WHERE task_name=%s AND trade_date=%s "
                "AND status='running' AND ended_at IS NULL LIMIT 1",
                (entry, args.date),
            ).fetchone()
            if original:
                row["reason"] = "原采集任务尚未结束，未重复启动；需要核实原任务实际退出后再重试"
                row["detail"]["original_running_job_id"] = original["id"]
                Store(writer).transition(row, now)
                return
        store = Store(writer)

        def persist(row):
            stamp = clock.now_utc()
            if row["status"] == "resolved":
                row["resolved_at"] = stamp
            with writer.transaction():
                store.transition(row, stamp)

        from inves_cog.dataguard.trace import SourceTrace, reason

        evidence = {}

        def run_recovery():
            trace = SourceTrace()
            try:
                with trace:
                    return recover(item, args.date, clock.now_utc(), values, evidence=evidence, trace=trace)
            except Exception as exc:
                trace.record(exc)
                return False
            finally:
                evidence["source_errors"] = trace.errors
                row["detail"]["recovery_evidence"] = evidence
                row["reason"] = reason(evidence)

        def downstream():
            for name in item.backfill.get("depends_on", []):
                if name != "barometer" or not recover(
                    _barometer(items), args.date, clock.now_utc(), values, evidence=evidence
                ):
                    row["reason"] = reason(evidence)
                    return False
            return True

        def recheck():
            scoped = replace(item, expected_keys=wide_scope(reader, args.date)) if item.scope == "wide" else item
            grouped = read(reader, scoped, args.date - timedelta(days=10), args.date, clock.now_utc())
            left = findings(scoped, args.date, grouped, now=clock.now_utc())
            if item.table == "flows.barometer_daily":
                drift = barometer_drifts(reader, item, args.date, args.date, clock.now_utc())
                if args.date in drift:
                    left.append(drift[args.date])
            row["detail"]["remaining_checks"] = [f.kind for f in left]
            row["detail"]["verified_source_rows"] = sum(r["n"] for r in grouped.get(args.date, []))
            return not left

        maximum = item.backfill.get("max_attempts", 3)
        if row["attempts"] >= maximum:
            row.update(status="unrecoverable", reason="已达到重试上限，禁止再次自动启动")
            persist(row)
            return
        attempt(
            row,
            now,
            max_attempts=maximum,
            run=run_recovery,
            downstream=downstream,
            recheck=recheck,
            persist=persist,
        )
    signal.alarm(0)


def _barometer(items):
    return next(i for i in items if i.table == "flows.barometer_daily")


if __name__ == "__main__":
    main()
