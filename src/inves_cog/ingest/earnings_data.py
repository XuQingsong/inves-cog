"""A028 daily fundamentals snapshots, independent of the A020 estimate quota."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from inves_cog.ingest.earnings_news import core_tickers
from inves_cog.ingest.fundamentals.providers import YFinance, fiscal_years
from inves_cog.ingest.fundamentals.repository import Repository as Fundamentals
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import Repository as Operations


def target_tickers(universe, holdings, core):
    return sorted(set(universe) | set(holdings) | set(core))


def consensus_fields(snapshot):
    quarter = (snapshot.get("raw") or {}).get("revenue_estimate", {}).get("0q", {})
    return {"rev_cq": quarter.get("avg"), "rev_cq_currency": quarter.get("revenueCurrency")}


class Repository(Fundamentals):
    def snapshot_today(self, ticker, now):
        return (
            self.connection.execute(
                "SELECT 1 FROM fundamentals.consensus_snapshot WHERE ticker=%s AND captured_at>=%s LIMIT 1",
                (ticker, now.astimezone(NY).replace(hour=0, minute=0, second=0, microsecond=0)),
            ).fetchone()
            is not None
        )

    def annual_years(self, ticker, now):
        row = self.connection.execute(
            "SELECT report_date FROM ingest.sec_filings WHERE ticker=%s AND form IN ('10-K','20-F','40-F') "
            "AND filing_date<=%s AND report_date IS NOT NULL ORDER BY filing_date DESC LIMIT 1",
            (ticker, now.astimezone(NY).date()),
        ).fetchone()
        return fiscal_years(row["report_date"] if row else None)

    def latest_snapshot(self, ticker, cutoff):
        row = self.connection.execute(
            "SELECT * FROM fundamentals.consensus_snapshot WHERE ticker=%s AND captured_at<=%s "
            "ORDER BY captured_at DESC,source LIMIT 1",
            (ticker, cutoff),
        ).fetchone()
        return {**row, **consensus_fields(row)} if row else None


def collect_consensus(*, clock, repository, tickers, provider):
    processed, failed = 0, []
    for ticker in sorted(set(tickers)):
        now = clock.now_utc()
        if repository.snapshot_today(ticker, now):
            continue
        try:
            cy, ny = repository.annual_years(ticker, now)
            snapshot = provider.collect(ticker, fy_cy=cy, fy_ny=ny)
            put_analyst_actions(getattr(repository, "connection", None), ticker, snapshot)
            repository.put_snapshot(snapshot)
            processed += 1
        except Exception as exc:
            failed.append({"ticker": ticker, "error_type": type(exc).__name__})
    return {
        "processed_count": processed,
        "status": "degraded" if failed else "ok",
        "note": f"{len(failed)} symbols failed" if failed else None,
        "failures": failed,
    }


def put_analyst_actions(connection, ticker, snapshot, keep_days=730):
    """Persist upgradeDowngradeHistory (Yahoo JSON or yfinance frame keys) into
    ingest.analyst_actions; rows older than keep_days are skipped."""
    raw = snapshot.get("raw") or {}
    rows = raw.pop("upgrade_history", None) or []
    if connection is None:
        return 0
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=keep_days)

    def pick(r, *keys):
        for k in keys:
            if r.get(k) not in (None, ""):
                return r[k]
        return None

    def price(v):
        try:
            return float(v) if v not in (None, "", 0) else None
        except (TypeError, ValueError):
            return None

    written = 0
    for r in rows:
        try:
            when = datetime.fromtimestamp(int(r["epochGradeDate"]), timezone.utc).date()
        except (KeyError, TypeError, ValueError):
            continue
        firm = pick(r, "firm", "Firm")
        if when < cutoff or not firm:
            continue
        connection.execute(
            "INSERT INTO ingest.analyst_actions "
            "(ticker, action_date, firm, action, from_grade, to_grade, pt_action, prior_pt, current_pt, source) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'yahoo') ON CONFLICT DO NOTHING",
            (
                ticker,
                when,
                firm,
                str(pick(r, "action", "Action") or "").lower(),
                pick(r, "fromGrade", "FromGrade"),
                pick(r, "toGrade", "ToGrade"),
                pick(r, "priceTargetAction"),
                price(pick(r, "priorPriceTarget")),
                price(pick(r, "currentPriceTarget")),
            ),
        )
        written += 1
    return written


def scheduled(*, clock, values, connect=None):
    from inves_cog.ingest.cli import connect as default_connect
    from inves_cog.ingest.implied_moves import collect_moves

    now = clock.now_utc().astimezone(NY)
    if not trading_day(now.date()):
        return {"status": "not_due"}
    with (connect or default_connect)(values) as db:
        if not db.execute("SELECT pg_try_advisory_lock(hashtextextended('A028:earnings-data',0)) AS ok").fetchone()[
            "ok"
        ]:
            return {"status": "already_running"}
        ops, repo = Operations(db), Repository(db)
        last = ops.last_runs(trade_date=now.date())
        root = Path(__file__).resolve().parents[3]
        universe = [r["ticker"] for r in yaml.safe_load((root / "config/universe.yaml").read_text())["stocks"]]
        # Position symbols only; no account values leave the database adapter.
        holdings = [
            r["ticker"]
            for r in db.execute(
                "SELECT DISTINCT jsonb_object_keys(coalesce(state->'positions','{}'::jsonb)) AS ticker "
                "FROM (SELECT DISTINCT ON (portfolio_id) state FROM trading.ledger "
                "ORDER BY portfolio_id,observed_at DESC) x"
            ).fetchall()
        ]
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=ops.health_rows(), persist=ops.write_health),
            persist=ops.write_job,
            persist_start=ops.write_job,
            timeout_seconds=1200,
        )
        out = {}
        if (15, 50) <= (now.hour, now.minute) <= (15, 57) and "earnings_implied_moves" not in last:
            out["implied_moves"] = runner.run(
                "earnings_implied_moves", "AlpacaIndicative", lambda: collect_moves(clock=clock, db=db, values=values)
            )
        if now.hour >= 6 and not (15, 10) <= (now.hour, now.minute) < (15, 59) and "earnings_consensus" not in last:
            tickers = target_tickers(universe, holdings, core_tickers())
            out["consensus"] = runner.run(
                "earnings_consensus",
                "EarningsConsensus",
                lambda: collect_consensus(
                    clock=clock, repository=repo, tickers=tickers, provider=YFinance(clock=clock)
                ),
            )
        return out or {"status": "not_due"}


def calendar_missing(rows, today, core=None):
    covered = {r["ticker"] for r in rows if today <= r["report_date"] <= today + timedelta(days=90)}
    return sorted((core or core_tickers()) - covered)
