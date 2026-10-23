"""M9 native scheduling or explicit offline snapshot replay; no order entry points."""

import argparse
import json
from contextlib import ExitStack
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from psycopg import Error as DatabaseError

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import trading_day
from inves_cog.ingest.repository import Repository as Operations
from inves_cog.ingest.settings import read_environment
from inves_cog.overlay.rules import timestamp
from inves_cog.perception.attribution.snapshot import m8_provider as native_m8_provider
from inves_cog.shadow.inputs import ReadInputs, validate_snapshot
from inves_cog.shadow.outputs import DatabaseOutputs
from inves_cog.shadow.pipeline import MemoryOutputs, run_overlay, run_shadows
from inves_cog.shadow.replay import replay_m8
from inves_cog.shadow.scheduling import due_stages
from inves_cog.shadow.settings import settings

ROOT = Path(__file__).resolve().parents[3]


def _scoped(values, key):
    if not values.get(key):
        raise ValueError(key + " is required; do not borrow another module login")
    return connect({**values, "INVES_COG_DATABASE_URL": values[key]})


def _summary(result):
    keys = ("status", "processed_count", "null_factors", "note", "source_ids", "missing", "source_events_asof")
    summary = {key: result[key] for key in keys if key in result}
    summary.update(signal_count=len(result.get("signals") or []), n9_count=len(result.get("n9") or []))
    if result.get("overlay"):
        summary["overlay_version"] = result["overlay"]["version"]
    return summary


def _read_m8(values, target, cutoff):
    try:
        # The accepted provider owns BEGIN/ROLLBACK; never nest it in the M9 input transaction.
        with _scoped(values, "INVES_COG_SHADOW_DATABASE_URL") as reader:
            reader.execute("SET statement_timeout='10s'")
            return native_m8_provider(reader)(target, cutoff)
    except DatabaseError as exc:
        return {
            "complete": False,
            "source_events_asof": None,
            "events": [],
            "source_ids": {},
            "missing": {"reader": type(exc).__name__},
            "null_reason": "M8快照读取失败；保留缺失，不切换账号或扩大权限",
        }


def scheduled(*, clock, values, m8_provider=None):
    target = clock.today_trade_date()
    if not trading_day(target):
        return {"status": "not_due"}
    tickers = [row["ticker"] for row in yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]]
    with ExitStack() as stack:
        shadow = stack.enter_context(_scoped(values, "INVES_COG_SHADOW_DATABASE_URL"))
        operations = stack.enter_context(connect(values))
        cutoff = clock.now_utc()
        provider = m8_provider if m8_provider is not None else lambda day, at: _read_m8(values, day, at)
        with shadow.transaction():
            shadow.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            bundle = ReadInputs(shadow, m8_provider=provider).load(
                clock=clock, target=target, tickers=tickers, cutoff=cutoff
            )
        rows = operations.execute(
            "SELECT task_name,status,ended_at FROM ingest.job_runs WHERE trade_date=%s ORDER BY started_at DESC",
            (target,),
        ).fetchall()
        completed = {
            row["task_name"]
            for row in rows
            if row["status"] in ("ok", "degraded") and row["ended_at"] is not None and row["ended_at"] <= cutoff
        }
        attempted = {row["task_name"] for row in rows}
        stages = due_stages(
            clock,
            premarket_ready="premarket_review" in completed,
            plan_ready=bundle.get("plan") is not None,
            source_ready=(bundle.get("m8") or {}).get("complete") is True,
        )
        local = cutoff.astimezone(ZoneInfo("America/New_York"))
        deadline = time.fromisoformat(settings()["publish_window_et"][1])
        missed_overlay = local.time() >= deadline and "m9_overlay" not in attempted
        if missed_overlay:
            stages.insert(0, "overlay_deadline")
        output = {}
        overlay = None
        if any(stage.startswith("overlay") for stage in stages):
            overlay = stack.enter_context(_scoped(values, "INVES_COG_OVERLAY_DATABASE_URL"))
        folder = values.get("INVES_COG_OVERLAY_DIR")
        if not folder:
            raise ValueError("INVES_COG_OVERLAY_DIR is required")
        outputs = DatabaseOutputs(overlay_connection=overlay, shadow_connection=shadow, folder=folder)
        repo = Operations(operations)
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=repo.health_rows(), persist=repo.write_health),
            persist=repo.write_job,
            persist_start=repo.write_job,
        )
        for stage in stages:
            name = "m9_overlay" if stage.startswith("overlay") else "m9_shadow"
            if name in attempted:
                continue
            lock_name = "M9:" + str(target) + ":" + name
            locked = operations.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired", (lock_name,)
            ).fetchone()["acquired"]
            if not locked:
                continue
            try:
                already = operations.execute(
                    "SELECT id FROM ingest.job_runs WHERE task_name=%s AND trade_date=%s LIMIT 1", (name, target)
                ).fetchone()
                if already:
                    continue

                def operation(stage=stage):
                    if stage.startswith("overlay"):
                        source = bundle.get("m8") or {}
                        if stage == "overlay_deadline":
                            source = {**source, "complete": False, "null_reason": "自然发布窗口已过；不补造按时覆盖层"}
                        result = run_overlay(clock=clock, target=target, source=source, outputs=outputs)
                    else:
                        result = run_shadows(
                            clock=clock, target=target, bundle=bundle, tickers=tickers, outputs=outputs
                        )
                    return _summary(result)

                output[name] = runner.run(name, "M9", operation, trade_date=target)
            finally:
                operations.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (lock_name,))
        return output or {"status": "waiting_dependencies"}


def _replay_m8(args, clock):
    values = read_environment()
    live = values.get("INVES_COG_OVERLAY_DIR")
    if not args.trade_dates or not args.output_directory or not live:
        raise ValueError("replay-m8 requires explicit trade dates, output directory, and configured live directory")
    with _scoped(values, "INVES_COG_SHADOW_DATABASE_URL") as reader:
        reader.execute("SET statement_timeout='10s'")
        return replay_m8(
            reader,
            days=args.trade_dates,
            clock=clock,
            output_directory=args.output_directory,
            live_directory=live,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["scheduled", "replay", "replay-m8"])
    parser.add_argument("--trade-dates", nargs="+", type=date.fromisoformat)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--cutoff")
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    clock = SystemClock()
    try:
        if args.action == "scheduled":
            result = scheduled(clock=clock, values=read_environment())
        elif args.action == "replay-m8":
            result = _replay_m8(args, clock)
        else:
            if not args.snapshot or not args.cutoff or not args.output_directory:
                raise ValueError("replay requires snapshot, original cutoff, and separate output directory")
            bundle = json.loads(args.snapshot.read_text())
            target = date.fromisoformat(bundle["target"])
            cutoff = timestamp(args.cutoff)
            if cutoff > clock.now_utc():
                raise ValueError("historical replay cannot claim a future cutoff")
            bundle = validate_snapshot(bundle, cutoff=cutoff, target=target)
            bundle["decision_cutoff"] = cutoff.isoformat()
            outputs = MemoryOutputs(args.output_directory)
            names = [row["ticker"] for row in yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]]
            # Generation time is the actual execution clock; only input selection uses historical cutoff.
            result = {
                "kind": "offline_replay_not_natural",
                "actual_generated_at": clock.now_utc().isoformat(),
                "overlay": _summary(
                    run_overlay(clock=clock, target=target, source=bundle.get("m8") or {}, outputs=outputs)
                ),
                "shadows": _summary(
                    run_shadows(clock=clock, target=target, bundle=bundle, tickers=names, outputs=outputs)
                ),
            }
        print(json.dumps(result, ensure_ascii=False, default=str, allow_nan=False))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
