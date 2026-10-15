"""M6-authorized price/SIC collectors using M1's existing clients and tables."""

import csv
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import StringIO

from inves_cog.ingest.adapters import alpaca_splits, cik_mapping
from inves_cog.ingest.http import HTTPClient
from inves_cog.ingest.market import split_factors

EXTRA_ETFS = ["XLB", "XLRE", "XLC", "RSP", "KRE", "MTUM", "VLUE"]
VIX_URLS = {
    "VIX_CBOE": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "VIX3M_CBOE": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
}


def price_universe(connection, day):
    return [
        r["ticker"]
        for r in connection.execute(
            "SELECT ticker FROM ingest.wide_universe WHERE trade_date=(SELECT max(trade_date) "
            "FROM ingest.wide_universe WHERE trade_date<=%s) AND included",
            (day,),
        ).fetchall()
    ]


def parse_cboe_csv(raw, *, series_id, clock):
    rows = []
    for original in csv.DictReader(StringIO(raw)):
        data = {key.strip().upper(): value for key, value in original.items() if key}
        stamp = data.get("DATE")
        if not stamp:
            continue
        try:
            day = datetime.strptime(stamp, "%m/%d/%Y").date()
        except ValueError:
            day = datetime.strptime(stamp, "%Y-%m-%d").date()
        value = data.get("CLOSE", data.get("VIX3M", data.get("VIX")))
        try:
            value = float(value) if value not in {None, "", "."} else None
        except ValueError:
            value = None
        if day <= clock.today_trade_date():
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": day,
                    "value": value,
                    "units": "index",
                    "realtime_start": day,
                    "fetched_at": clock.now_utc(),
                }
            )
    return rows


def collect_market_inputs(pipeline):
    from inves_cog.ingest.jobs import HealthBook

    health = HealthBook(clock=pipeline.clock, rows=pipeline.repo.health_rows(), persist=pipeline.repo.write_health)
    count, failures = 0, []
    http = HTTPClient(pool=True)
    for series, url in VIX_URLS.items():
        try:
            rows = parse_cboe_csv(http.get(url), series_id=series, clock=pipeline.clock)
            for row in rows:
                pipeline.repo.write("macro_observations", row, update=("value", "fetched_at"))
            count += len(rows)
            health.record(series, success=bool(rows), count=len(rows), degraded=not rows)
        except Exception as exc:
            failures.append({"source": series, "reason": type(exc).__name__ + ": " + str(exc)})
            health.record(series, success=False, note=str(exc), degraded=True)
    try:
        from datetime import timedelta

        day = pipeline.day
        rows = pipeline.alpaca.daily_bars(EXTRA_ETFS, day - timedelta(days=8), day)
        splits = alpaca_splits(pipeline.alpaca, EXTRA_ETFS, day - timedelta(days=8), day)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["ticker"]].append(row)
        for ticker, items in grouped.items():
            factors = split_factors([r["trade_date"] for r in items], splits.get(ticker, []))
            for row, factor in zip(items, factors, strict=True):
                row["adj_factor"] = factor
                pipeline.repo.write("bars_daily", row, update=("open", "high", "low", "close", "volume", "adj_factor"))
        count += len(rows)
        missing = set(EXTRA_ETFS) - set(grouped)
        if missing:
            failures.append({"source": "AlpacaExtraETFs", "reason": "missing:" + ",".join(sorted(missing))})
        health.record(
            "AlpacaExtraETFs",
            success=not missing,
            count=len(rows),
            degraded=bool(missing),
            note=str(sorted(missing)) if missing else None,
        )
    except Exception as exc:
        health.record("AlpacaExtraETFs", success=False, note=str(exc), degraded=True)
        failures.append({"source": "AlpacaExtraETFs", "reason": type(exc).__name__ + ": " + str(exc)})
    return {
        "processed_count": count,
        "status": "degraded" if failures else "ok",
        "failures": failures,
        "note": str(failures) if failures else None,
    }


def collect_issuer_profiles(pipeline):
    from pathlib import Path

    import yaml

    sec = pipeline.require(pipeline.sec, "SEC")
    mapping = cik_mapping(sec)
    seeds = yaml.safe_load((Path(__file__).resolve().parents[3] / "config/universe.yaml").read_text())["stocks"]
    tickers = sorted(set(price_universe(pipeline.repo.connection, pipeline.day)) | {r["ticker"] for r in seeds})
    existing = {
        r["ticker"]: r
        for r in pipeline.repo.connection.execute("SELECT ticker,fetched_at FROM ingest.issuer_profiles").fetchall()
    }
    month = pipeline.clock.today_trade_date().replace(day=1)
    selected = [t for t in tickers if t not in existing or existing[t]["fetched_at"].date() < month]

    def fetch(ticker):
        try:
            cik = mapping.get(ticker)
            if not cik:
                raise ValueError("SEC ticker/CIK mapping unavailable")
            return ticker, cik, sec.submissions(cik), None
        except Exception as exc:
            return ticker, None, None, type(exc).__name__ + ": " + str(exc)

    count, failures = 0, []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for ticker, cik, profile, error in executor.map(fetch, selected):
            if error:
                failures.append({"ticker": ticker, "reason": error})
                continue
            pipeline.repo.connection.execute(
                "INSERT INTO ingest.issuer_profiles (cik,ticker,sic,sic_description,fetched_at) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (ticker) DO UPDATE SET cik=EXCLUDED.cik,"
                "sic=EXCLUDED.sic,sic_description=EXCLUDED.sic_description,fetched_at=EXCLUDED.fetched_at",
                (
                    cik,
                    ticker,
                    int(profile["sic"]) if str(profile.get("sic", "")).isdigit() else None,
                    profile.get("sicDescription"),
                    pipeline.clock.now_utc(),
                ),
            )
            count += 1
    return {
        "processed_count": count,
        "reused_current_month": len(tickers) - len(selected),
        "status": "degraded" if failures else "ok",
        "failures": failures,
        "note": str(failures[:10]) if failures else None,
    }
