"""A023 source-specific calendars and independent volatility fallbacks. No LLM."""

import csv
import html
import math
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from urllib.parse import quote

from inves_cog.ingest.http import HTTPClient, SourceError
from inves_cog.ingest.jobs import HealthBook
from inves_cog.ingest.market import NY, exchange

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*", "Origin": "https://www.nasdaq.com"}
BACKFILL_FROM = date(2026, 10, 1)


def number(value):
    text = str(value or "").strip().replace("$", "").replace(",", "")
    if text in {"", "N/A", "NA", "--", ".", "None"}:
        return None
    result = float(text.strip("()"))
    return -result if text.startswith("(") else result


def records(response):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise SourceError("Nasdaq calendar response missing data")
    data = response["data"]
    if "rows" not in data or data["rows"] is not None and not isinstance(data["rows"], list):
        raise SourceError("Nasdaq calendar response missing rows")
    return data["rows"] or []


def parse_earnings(response, day, clock):
    result = []
    for r in records(response):
        if not r.get("symbol"):
            raise SourceError("Nasdaq earnings ticker missing")
        estimates = number(r.get("noOfEsts"))
        result.append(
            dict(
                ticker=r["symbol"],
                report_date=day,
                time={"time-pre-market": "pre", "time-after-hours": "post"}.get(r.get("time"), "unknown"),
                eps_forecast=number(r.get("epsForecast")),
                n_estimates=int(estimates) if estimates is not None else None,
                market_cap=number(r.get("marketCap")),
                company=r.get("name"),
                source="Nasdaq",
                fetched_at=clock.now_utc(),
            )
        )
    return result


def text_value(value):
    return html.unescape(value or "").strip() or None


def parse_econ(response, day, clock):
    result = []
    for r in records(response):
        if r.get("country") != "United States":
            continue
        if not r.get("eventName"):
            raise SourceError("Nasdaq economic event name missing")
        # Nasdaq calls this field gmt, but the recorded US release times are ET
        # (08:30 durable goods, 10:00 consumer confidence); do not shift them again.
        result.append(
            dict(
                event_date=day,
                event_time_et=text_value(r.get("gmt")),
                country=r["country"],
                name=r["eventName"],
                actual=text_value(r.get("actual")),
                consensus=text_value(r.get("consensus")),
                previous=text_value(r.get("previous")),
                source="Nasdaq",
                fetched_at=clock.now_utc(),
            )
        )
    return result


def parse_yahoo_vix(response, series_id, clock):
    try:
        data = response["chart"]["result"][0]
        stamps = data["timestamp"]
        closes = data["indicators"]["quote"][0]["close"]
        if len(stamps) != len(closes):
            raise ValueError("length mismatch")
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise SourceError("Yahoo VIX daily bars missing or malformed") from exc
    now = clock.now_utc().astimezone(NY)
    result = []
    for stamp, value in zip(stamps, closes, strict=True):
        day = datetime.fromtimestamp(stamp, timezone.utc).astimezone(NY).date()
        if day < BACKFILL_FROM or day > now.date() or day == now.date() and now.hour < 16:
            continue
        if value is None or not math.isfinite(float(value)) or value <= 0:
            continue
        result.append(
            dict(
                series_id=series_id,
                observation_date=day,
                value=float(value),
                units="index",
                realtime_start=day,
                fetched_at=clock.now_utc(),
            )
        )
    return result


def source_run(pipeline, source, operation):
    """Each source fails independently; health never includes request keys/URLs."""
    health = HealthBook(clock=pipeline.clock, rows=pipeline.repo.health_rows(), persist=pipeline.repo.write_health)
    try:
        rows = operation()
        latest = max(
            (r.get("observation_date") or r.get("report_date") or r.get("event_date") for r in rows), default=None
        )
        health.record(
            source, success=True, count=len(rows), note=f"latest_data_at={latest.isoformat() if latest else 'none'}"
        )
        return rows, None
    except Exception as exc:
        completed = getattr(exc, "completed_rows", [])
        latest = max(
            (r.get("observation_date") or r.get("report_date") or r.get("event_date") for r in completed), default=None
        )
        code = getattr(exc, "status_code", None)
        health.record(
            source,
            success=False,
            degraded=True,
            count=len(completed),
            note=f"{type(exc).__name__}: source collection failed; status={code}; "
            f"latest_data_at={latest.isoformat() if latest else 'none'}",
        )
        return [], source + ":" + type(exc).__name__


def collect_vix(pipeline, *, http=None):
    from inves_cog.ingest.market_structure import VIX_URLS, parse_cboe_csv

    http = http or HTTPClient(timeout=15, retries=1)
    count, failures = 0, []
    for series in ["VIX_CBOE", "VIX3M_CBOE", "VIX_YAHOO", "VIX3M_YAHOO"]:

        def collect(series=series):
            if series in VIX_URLS:
                rows = parse_cboe_csv(http.get(VIX_URLS[series]), series_id=series, clock=pipeline.clock)
                rows = [r for r in rows if r["observation_date"] >= BACKFILL_FROM and r["value"] is not None]
            else:
                symbol = "^VIX3M" if series == "VIX3M_YAHOO" else "^VIX"
                first = datetime.combine(BACKFILL_FROM, datetime.min.time(), timezone.utc)
                raw = http.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe=""),
                    params={
                        "period1": int(first.timestamp()),
                        "period2": int(pipeline.clock.now_utc().timestamp()),
                        "interval": "1d",
                    },
                    headers=HEADERS,
                )
                rows = parse_yahoo_vix(raw, series, pipeline.clock)
            if not rows:
                raise SourceError("No completed daily volatility observations")
            for row in rows:
                pipeline.repo.write("macro_observations", row, update=("value", "fetched_at"))
            return rows

        rows, error = source_run(pipeline, series, collect)
        count += len(rows)
        if error:
            failures.append(error)
    return dict(processed_count=count, status="degraded" if failures else "ok", note=";".join(failures) or None)


def calendar_days(day):
    return [d.date() for d in exchange(day.year).sessions_in_range(str(day), str(day + timedelta(days=25)))][:10]


def alpha_fallback(pipeline, days, http):
    """One bulk CSV request, filtered locally, and at most 25 attempts per ET day."""
    key = pipeline.values.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise SourceError("Alpha Vantage not configured")
    today = pipeline.clock.now_utc().astimezone(NY).date().isoformat()
    cursor = pipeline.repo.get_cursor("a023-alpha-calendar") or {}
    used = cursor.get("attempts", 0) if cursor.get("day") == today else 0
    if used >= 25:
        raise SourceError("Alpha Vantage calendar daily request limit")
    pipeline.repo.set_cursor("a023-alpha-calendar", {"day": today, "attempts": used + 1}, pipeline.clock.now_utc())
    raw = http.get(
        "https://www.alphavantage.co/query",
        params={"function": "EARNINGS_CALENDAR", "horizon": "3month", "apikey": key},
    )
    if not isinstance(raw, str):
        raise SourceError("Alpha Vantage calendar unavailable or rate limited")
    reader = csv.DictReader(StringIO(raw))
    if not {"symbol", "reportDate", "estimate"} <= set(reader.fieldnames or []):
        raise SourceError("Alpha Vantage earnings CSV malformed")
    allowed = set(pipeline.stocks) | set(pipeline.repo.holding_tickers())
    result = []
    for r in reader:
        day = date.fromisoformat(r["reportDate"])
        if r["symbol"] in allowed and day in days:
            result.append(
                dict(
                    ticker=r["symbol"],
                    report_date=day,
                    time="unknown",
                    eps_forecast=number(r["estimate"]),
                    n_estimates=None,
                    market_cap=None,
                    company=r.get("name"),
                    source="AlphaVantage",
                    fetched_at=pipeline.clock.now_utc(),
                )
            )
    return result


def collect_calendars(pipeline, kind, *, http=None):
    http = http or HTTPClient(timeout=15, retries=0)
    day = pipeline.clock.now_utc().astimezone(NY).date()
    if kind == "earnings":
        days = calendar_days(day)
        parser, table, source, endpoint = parse_earnings, "earnings_calendar", "NasdaqEarnings", "earnings"
    else:
        monday = day - timedelta(days=day.weekday())
        days = [monday + timedelta(days=n) for n in range(14)]
        parser, table, source, endpoint = parse_econ, "econ_calendar", "NasdaqEconomic", "economicevents"
    failed_days = []
    saved = []

    def collect():
        for target in days:
            try:
                raw = http.get(
                    "https://api.nasdaq.com/api/calendar/" + endpoint,
                    params={"date": target.isoformat()},
                    headers=HEADERS,
                )
                rows = parser(raw, target, pipeline.clock)
                for row in rows:
                    pipeline.repo.write(
                        table,
                        row,
                        update=tuple(
                            k
                            for k in row
                            if k not in {"ticker", "report_date", "source", "event_date", "country", "name"}
                        ),
                    )
                saved.extend(rows)
            except Exception:
                failed_days.append(target)
        if failed_days:
            failure = SourceError("Nasdaq calendar has failed dates")
            failure.completed_rows = saved
            raise failure
        return saved

    _, error = source_run(pipeline, source, collect)
    if kind == "earnings" and failed_days:

        def fallback():
            rows = alpha_fallback(pipeline, failed_days, http)
            for row in rows:
                pipeline.repo.write(
                    table, row, update=("time", "eps_forecast", "n_estimates", "market_cap", "company", "fetched_at")
                )
            return rows

        rows, fallback_error = source_run(pipeline, "AlphaVantageCalendar", fallback)
        saved.extend(rows)
        error = error or fallback_error
    return dict(processed_count=len(saved), status="degraded" if error else "ok", note=error)
