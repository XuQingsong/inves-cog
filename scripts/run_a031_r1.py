"""A031 risk study on the supplied historical panel and Mac-local price database."""

import argparse
import csv
import gzip
import hashlib
import json
import signal
import time
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from inves_cog.backtest.risk_study import PriceSeries, horizon_metrics, monthly_portfolio, risk_summary

# Explicit, reviewable bank/insurer classification. Payment networks and asset managers remain included.
BANK_INSURANCE = set(
    (
        "ACGL ADS AET AFL AIG AIZ ALL AXP BAC BHF BNY C CB CFG CI CINF CMA CNC COF DFS EG ERIE ETFC FITB FRC "
        "GL GS HBAN HIG HUM "
        "JPM KEY L LNC MET MOH MS MTB NTRS PBCT PFG PGR PNC PRU RF SBNY SCHW SIVB STI STT SYF TFC TRV "
        "UNH UNM USB WCG WRB XL ZION ELV"
    ).split()
)


def save(path, value):
    path.write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", type=Path, required=True)
    p.add_argument("--coverage", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--memberships", type=Path, required=True)
    a = p.parse_args()
    signal.alarm(900)
    started = time.monotonic()
    a.output.mkdir(parents=True, exist_ok=True)
    from inves_cog.backtest.membership import is_member

    membership_metadata = json.loads(a.memberships.read_text())
    memberships = membership_metadata["events"]
    removed_pre_membership = {}
    panel, excluded, raw_counts = {}, set(), {}
    with a.panel.open() as f:
        for row in csv.DictReader(f):
            day = date.fromisoformat(row["date"])
            ticker = row["ticker"]
            raw_counts[day.year] = raw_counts.get(day.year, 0) + 1
            if is_member(memberships.get(ticker, []), day) is False:
                removed_pre_membership[ticker] = removed_pre_membership.get(ticker, 0) + 1
                continue
            if ticker in BANK_INSURANCE:
                excluded.add(ticker)
                continue
            value = float(row["m8"]) if row.get("m8") and float(row.get("ev") or 0) > 0 else None
            panel.setdefault(day, {})[ticker] = value
    names = {t for week in panel.values() for t in week}
    prices = {t: {} for t in names | {"SPY"}}
    with psycopg.connect(
        host="127.0.0.1",
        dbname="inves_cog_bt",
        row_factory=dict_row,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=30000",
    ) as db:
        with db.cursor(name="a031_r1_prices") as cur:
            cur.execute(
                "SELECT ticker,trade_date,close,adj_factor FROM ingest.bars_daily "
                "WHERE ticker=ANY(%s) AND trade_date<=%s ORDER BY ticker,trade_date",
                (sorted(prices), max(panel)),
            )
            for row in cur:
                if row["close"] and row["close"] > 0:
                    prices[row["ticker"]][row["trade_date"]] = float(row["close"]) * float(row["adj_factor"] or 1)
    series = {t: PriceSeries.from_prices(rows) for t, rows in prices.items()}
    spy = series["SPY"]
    results = []
    yearly = {}
    for day, week in sorted(panel.items()):
        valid = [v for v in week.values() if v is not None]
        # Same tie-inclusive ceiling quintile as monthly portfolio weights.
        ranked = sorted(valid)
        cutoff = ranked[-((len(ranked) + 4) // 5)] if ranked else None
        stat = yearly.setdefault(
            day.year, dict(observed_names=set(), valid_names=set(), weekly_rows=0, valid_weekly_rows=0)
        )
        stat["observed_names"].update(week)
        stat["valid_names"].update(t for t, v in week.items() if v is not None)
        stat["weekly_rows"] += len(week)
        stat["valid_weekly_rows"] += len(valid)
        for ticker, value in week.items():
            if value is None:
                continue
            group = "top_fifth" if cutoff is not None and value >= cutoff else "rest"
            for weeks in (52, 104):
                result = horizon_metrics(series[ticker], spy, day, weeks)
                if result:
                    results.append(
                        dict(ticker=ticker, date=day, year=day.year, weeks=weeks, group=group, m8=value, **result)
                    )
    with gzip.open(a.output / "individual.csv.gz", "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    save(a.output / "individual-summary.json", risk_summary(results))
    original = json.loads(a.coverage.read_text())
    removed = set(original.get("truncations", {}))
    for year, stats in yearly.items():
        stats["observed_names"] = sorted(stats["observed_names"])
        stats["valid_names"] = sorted(stats["valid_names"])
        stats["removed_valid_names"] = sorted(set(stats["valid_names"]) & removed)
        stats["supplied_coverage"] = original.get(str(year))
    save(
        a.output / "data-audit.json",
        dict(
            panel_sha256=hashlib.sha256(a.panel.read_bytes()).hexdigest(),
            excluded_bank_insurers=sorted(excluded),
            yearly=yearly,
            known_removed_in_input=len(removed & names),
            membership_contract="official events filter panel; no-event names retain supplied weekly membership",
            official_membership=membership_metadata,
            excluded_outside_membership=removed_pre_membership,
            coverage_limit=(
                "portfolios cover observable supplied-panel members, not unavailable company prices/fundamentals"
            ),
            terminal_limit="last available adjusted quote carried as cash proxy; actual delisting payouts unavailable",
            missing_m_policy="included at full weight in A/B/C; excluded only from m ranking",
            dividend_limit="uses stored split-adjusted close; dividends are not separately credited",
        ),
    )
    portfolios = {}
    with gzip.open(a.output / "portfolios.csv.gz", "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["start", "variant", "date", "equity"])
        w.writeheader()
        for month in range(1, 13):
            for variant in ("A", "B", "C"):
                start = date(2018, month, 1)
                result = monthly_portfolio(panel, series, spy, start, variant, memberships=memberships)
                key = f"{start}-{variant}"
                portfolios[key] = dict(metrics=result["metrics"], rebalances=result["rebalances"])
                w.writerows(dict(start=start, variant=variant, **row) for row in result["curve"])
    save(a.output / "portfolios-summary.json", portfolios)
    save(
        a.output / "progress.json",
        dict(
            phase="complete",
            elapsed=time.monotonic() - started,
            individual_rows=len(results),
            portfolios=len(portfolios),
        ),
    )


if __name__ == "__main__":
    main()
