"""Resumable historical earnings events, verified against every official index."""

from datetime import date

from inves_cog.ingest.sec import accepted_from_index, earnings_event


def verify_index(original, *, sec, clock):
    row = {**original, "raw": dict(original.get("raw", {}))}
    try:
        verified = row["raw"].get("accepted_index_source", {}).get("verified")
        if row.get("accepted_at") is None or not verified:
            if not str(row["cik"]).isdigit() or any(c not in "0123456789-" for c in row["accession"]):
                raise ValueError("Unsafe filing identity")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(row['cik'])}/"
                f"{row['accession'].replace('-', '')}/{row['accession']}-index.html"
            )
            row["accepted_at"] = accepted_from_index(sec.get(url))
            row["raw"]["accepted_index_source"] = {
                "verified": True,
                "url": url,
                "checked_at": clock.now_utc().isoformat(),
            }
        return row, None
    except Exception as exc:
        return row, exc


def backfill_events(filings, *, sec, clock, closes_for, persist_filing, persist_event, workers=1):
    count, unverified, errors = 0, [], []
    closes = {}
    selected = [
        row
        for row in filings
        if row["form"] == "8-K" and "2.02" in row["items"] and row["filing_date"] >= date(2015, 1, 1)
    ]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as executor:
        verified_rows = list(executor.map(lambda row: verify_index(row, sec=sec, clock=clock), selected))
    for row, error in verified_rows:
        try:
            if error is not None:
                raise error
            persist_filing(row)
            ticker = row["ticker"]
            if ticker not in closes:
                closes[ticker] = closes_for(ticker)
            event = earnings_event(row, closes=closes[ticker], clock=clock)
            event.update(
                event_id="SEC:" + row["accession"],
                fiscal_period=str(row["report_date"]) if row.get("report_date") else None,
            )
            if event["ref_close"] is None:
                event["flags"].append("ref_close_missing")
            persist_event(event)
            count += 1
        except Exception as exc:
            unverified.append(row["accession"])
            errors.append({"accession": row["accession"], "reason": type(exc).__name__ + ": " + str(exc)})
    return {
        "processed_count": count,
        "unverified": unverified,
        "errors": errors,
        "status": "degraded" if unverified else "ok",
    }


def run_history(*, clock, values, workers=5):
    """Repeatable repair; already verified Accepted sources are reused, never guessed."""
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.http import HTTPClient
    from inves_cog.ingest.jobs import HealthBook, JobRunner
    from inves_cog.ingest.repository import Repository
    from inves_cog.ingest.sec_client import SECClient

    with connect(values) as connection:
        repo = Repository(connection)
        filings = connection.execute(
            "SELECT * FROM ingest.sec_filings WHERE form='8-K' AND '2.02'=ANY(items) "
            "AND filing_date>='2015-01-01' ORDER BY filing_date,accession"
        ).fetchall()
        sec = SECClient(user_agent=values["SEC_USER_AGENT"], http=HTTPClient(pool=True))
        runner = JobRunner(
            clock=clock,
            health=HealthBook(clock=clock, rows=repo.health_rows(), persist=repo.write_health),
            persist=repo.write_job,
        )
        return runner.run(
            "earnings_history_backfill",
            "SECEarningsHistory",
            lambda: backfill_events(
                filings,
                sec=sec,
                clock=clock,
                closes_for=repo.closes,
                workers=workers,
                persist_filing=lambda r: repo.write("sec_filings", r, update=("accepted_at", "raw")),
                persist_event=lambda r: repo.write(
                    "earnings_events",
                    r,
                    update=("accepted_at", "session", "reaction_day", "ref_close", "fiscal_period", "flags"),
                ),
            ),
        )


def main():
    import argparse
    from pathlib import Path

    from inves_cog.clock import SystemClock
    from inves_cog.ingest.repository import json_text
    from inves_cog.ingest.settings import read_environment

    parser = argparse.ArgumentParser(description="Verify historical SEC earnings events")
    parser.add_argument("--workers", type=int, default=5, choices=range(1, 6))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_history(clock=SystemClock(), values=read_environment(), workers=args.workers)
    rendered = json_text(result)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
