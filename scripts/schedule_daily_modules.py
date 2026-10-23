"""Poll accepted module entry points; ET windows and persisted job guards own dispatch."""

import argparse
import time
from datetime import datetime, timezone

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.market import NY, exchange, trading_day
from inves_cog.ingest.repository import json_text
from inves_cog.ingest.settings import read_environment

TASKS = (
    "bars_full",
    "m6_market_inputs",
    "financials",
    "m2_financials",
    "market_structure",
    "rule_a_scores",
    "bars_prefill",
)


def dependencies_met(name, records):
    def completed(row):
        return bool(row and row["status"] in {"ok", "degraded"} and row.get("ended_at") is not None)

    required = {
        "market_structure": ("bars_full", "m6_market_inputs"),
        "anomaly_daily": ("bars_full", "market_structure"),
        "premarket_review": ("bars_prefill",),
        "paper_plan": ("rule_a_scores",),
    }
    if name in required:
        return all(completed(records.get(task)) for task in required[name])
    if name in {"rule_a_scores", "valuation_v1"}:
        financial = [records[task] for task in ("financials", "m2_financials") if task in records]
        floor = datetime.min.replace(tzinfo=timezone.utc)
        latest = max(financial, key=lambda row: row.get("started_at") or row.get("ended_at") or floor, default=None)
        return completed(latest) and (name != "valuation_v1" or completed(records.get("bars_full")))
    raise ValueError("Unknown module task")


def readiness(values):
    records = {}

    def ready(name, day):
        if day not in records:
            with connect(values) as connection:
                rows = connection.execute(
                    "SELECT DISTINCT ON (task_name) task_name,status,started_at,ended_at "
                    "FROM ingest.job_runs WHERE trade_date=%s AND task_name=ANY(%s) "
                    "ORDER BY task_name,started_at DESC",
                    (day, list(TASKS)),
                ).fetchall()
                records[day] = {row["task_name"]: row for row in rows}
        return dependencies_met(name, records[day])

    return ready


def _perception_connection(values):
    key = "INVES_COG_PERCEPTION_DATABASE_URL"
    if not values.get(key):
        raise ValueError(key + " is required; do not borrow another module's login")
    return connect({**values, "INVES_COG_DATABASE_URL": values[key]})


def _already_attempted(connection, name, day):
    return (
        connection.execute(
            "SELECT id,status FROM ingest.job_runs WHERE task_name=%s AND trade_date=%s LIMIT 1",
            (name, day),
        ).fetchone()
        is not None
    )


def run_anomalies(*, clock, values):
    from collections import Counter

    from inves_cog.perception.anomaly.database import DatabasePanel
    from inves_cog.perception.anomaly.replay import _identify
    from inves_cog.perception.anomaly.service import run_recorded, write_anomalies

    day = clock.today_trade_date()
    with _perception_connection(values) as connection:
        if _already_attempted(connection, "anomaly_daily", day):
            return {"status": "already_attempted"}
        summary = {}

        def operation():
            current = connection.execute(
                "SELECT 1 FROM marketstate.market WHERE trade_date=%s LIMIT 1",
                (day,),
            ).fetchone()
            if current is None:
                raise ValueError("current marketstate is missing; no previous-day substitution")
            panel = DatabasePanel.from_connection(connection, end=day)
            rows = []
            for session in ("close", "post"):
                rows.extend(_identify(day, panel.detect(day, session)))
            with connection.transaction():
                write_anomalies(connection, rows, generated_at=clock.now_utc())
            summary.update(
                entry_paths=dict(Counter(path for row in rows for path in row["entry_paths"])),
                data_quality=dict(Counter(key for row in rows for key in row["data_quality"])),
            )
            return len(rows)

        job = run_recorded(
            connection,
            clock=clock,
            task_name="anomaly_daily",
            trade_date=day,
            params_version="p-2026.10",
            operation=operation,
        )
        return {"status": "ok", "job_id": job, **summary}


def premarket_scope(connection, *, clock):
    day = clock.today_trade_date()
    previous = exchange(day.year).previous_session(str(day)).date()
    stamp = clock.now_utc()
    ledger = connection.execute(
        "SELECT state FROM trading.ledger WHERE portfolio_id='paper-fixed' AND extractor='fixed' "
        "AND rule_set='A' AND trade_date<=%s AND observed_at<=%s "
        "ORDER BY trade_date DESC,observed_at DESC LIMIT 1",
        (day, stamp),
    ).fetchone()
    holdings = sorted((ledger["state"].get("positions") or {}) if ledger else {})
    linked = connection.execute(
        "SELECT DISTINCT member->>'ticker' AS ticker FROM perception.linkage_events e "
        "JOIN perception.anomalies a ON a.anomaly_id=e.anomaly_id "
        "CROSS JOIN LATERAL jsonb_array_elements(a.members) member "
        "WHERE e.lifecycle IN ('假设中','市场确认','基本面核查中') AND a.trade_date<=%s",
        (day,),
    ).fetchall()
    names = sorted(set(holdings) | {r["ticker"] for r in linked if r["ticker"]})
    quotes = connection.execute(
        "SELECT DISTINCT ON (m.ticker) m.ticker,b.close AS prev_close,m.close AS premarket_last,d.sigma "
        "FROM ingest.bars_minute m JOIN ingest.bars_daily b ON b.ticker=m.ticker AND b.trade_date=%s "
        "LEFT JOIN marketstate.daily d ON d.ticker=m.ticker AND d.trade_date=%s AND d.session='close' "
        "WHERE m.ticker=ANY(%s) AND m.session='pre' AND m.ts_utc<=%s "
        "AND m.ts_utc>=(%s::date+time '04:00') AT TIME ZONE 'America/New_York' "
        "ORDER BY m.ticker,m.ts_utc DESC",
        (previous, previous, names, stamp, day),
    ).fetchall()
    valid = {
        r["ticker"]: r
        for r in quotes
        if r["prev_close"] is not None
        and r["prev_close"] > 0
        and r["premarket_last"] is not None
        and r["sigma"] is not None
        and r["sigma"] > 0
    }
    return {"holdings": holdings, "linked": [r["ticker"] for r in linked], "quotes": valid}, sorted(
        set(names) - set(valid)
    )


def run_premarket(*, clock, values):
    from inves_cog.perception.anomaly.premarket import review_premarket
    from inves_cog.perception.anomaly.service import run_recorded, write_premarket

    day = clock.today_trade_date()
    with _perception_connection(values) as connection:
        if _already_attempted(connection, "premarket_review", day):
            return {"status": "already_attempted"}
        missing = []

        def operation():
            scope, gaps = premarket_scope(connection, clock=clock)
            missing.extend(gaps)
            rows = review_premarket(scope)
            with connection.transaction():
                return write_premarket(connection, day, rows, "p-2026.10")

        job = run_recorded(
            connection,
            clock=clock,
            task_name="premarket_review",
            trade_date=day,
            params_version="p-2026.10",
            operation=operation,
        )
        if missing:
            connection.execute(
                "UPDATE ingest.job_runs SET status='degraded',error_summary=%s WHERE id=%s",
                ("missing premarket inputs: " + ",".join(missing), job),
            )
        return {"status": "degraded" if missing else "ok", "job_id": job, "missing_count": len(missing)}


def _operation(name):
    if name == "market_structure":
        from inves_cog.marketstate.cli import run
    elif name == "rule_a_scores":
        from inves_cog.trading.scoring.cli import run
    elif name == "valuation_v1":
        from inves_cog.valuation_v1.cli import scheduled as run
    elif name == "paper_plan":
        from inves_cog.trading.execution.cli import scheduled as run
    else:
        run = {"anomaly_daily": run_anomalies, "premarket_review": run_premarket}[name]
    return run


def run_once(
    *,
    clock,
    values,
    ready=None,
    market_run=None,
    score_run=None,
    anomaly_run=None,
    valuation_run=None,
    paper_run=None,
    premarket_run=None,
    names=None,
):
    local = clock.now_utc().astimezone(NY)
    if not trading_day(local.date()):
        return {}
    ready, result = ready or readiness(values), {}
    tasks = []
    hm = (local.hour, local.minute)
    if (20, 45) <= hm:
        tasks.append(("market_structure", market_run, "day"))
    # Leave five minutes for M7 after M6; do not claim a late run met the 21:00 deadline.
    if (20, 55) <= hm < (21, 0):
        tasks.append(("anomaly_daily", anomaly_run, None))
    if hm >= (22, 30):
        tasks.extend([("rule_a_scores", score_run, "signal_date"), ("valuation_v1", valuation_run, None)])
    if (8, 0) <= hm < (8, 30):
        tasks.append(("premarket_review", premarket_run, None))
    # M4 owns its score waiting/deadline decision, including the final 09:05 poll.
    from inves_cog.trading.execution.cli import polling_due as paper_due

    if paper_due(clock):
        tasks.append(("paper_plan", paper_run, None))
    allowed = {"market_structure", "rule_a_scores", "anomaly_daily", "valuation_v1", "paper_plan", "premarket_review"}
    if names is not None and set(names) - allowed:
        raise ValueError("Unknown module task filter")
    for name, operation, day_key in tasks:
        if names is not None and name not in names:
            continue
        try:
            dependency_day = (
                exchange(local.year).previous_session(str(local.date())).date()
                if name == "paper_plan"
                else local.date()
            )
            if name != "paper_plan" and not ready(name, dependency_day):
                result[name] = {"status": "waiting_dependencies"}
                continue
            kwargs = {"clock": clock, "values": values}
            if day_key:
                kwargs.update(schedule=True, **{day_key: local.date()})
            output = (operation or _operation(name))(**kwargs)
            result[name] = {
                key: output[key]
                for key in (
                    "status",
                    "processed_count",
                    "coverage",
                    "expected",
                    "observed_at",
                    "job_id",
                    "entry_paths",
                    "data_quality",
                    "missing_count",
                )
                if key in output
            }
        except Exception as exc:
            result[name] = {"status": "failed", "error_type": type(exc).__name__}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", nargs="+")
    args = parser.parse_args()
    clock = SystemClock()
    while True:
        result = run_once(clock=clock, values=read_environment(), names=args.tasks)
        if any(row.get("status") != "not_due" for row in result.values()):
            print(json_text(result), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
