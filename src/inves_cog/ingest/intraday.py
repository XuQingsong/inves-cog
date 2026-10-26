"""A024 display-only delayed SIP observations. Never an input to rule A."""

import math
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from inves_cog.ingest.http import HTTPClient, SourceError, require_mapping
from inves_cog.ingest.market import NY, bar_session, exchange, trading_day
from inves_cog.ingest.providers import stamp

FEED = "delayed_sip"
# Verified with the existing key and official snapshots contract on 2026-10-26.
MIN_DELAY_MINUTES = 15
SOURCE = "Alpaca:" + FEED
ETF_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "SMH",
    "SOXX",
    "IGV",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLP",
    "XLY",
    "XLI",
    "XLU",
    "XLC",
    "XLRE",
    "XLB",
}
YAHOO_TICKERS = (
    "ES=F",
    "NQ=F",
    "RTY=F",
    "YM=F",
    "^FVX",
    "^TNX",
    "^TYX",
    "CL=F",
    "BZ=F",
    "GC=F",
    "DX-Y.NYB",
    "BTC-USD",
    "^VIX",
)


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def parse_snapshots(data, previous, tickers, clock):
    data = require_mapping(data)
    now = clock.now_utc()
    day = now.astimezone(NY).date()
    rows = []
    for ticker in tickers:
        snapshot = data.get(ticker)
        trade = snapshot.get("latestTrade") if isinstance(snapshot, dict) else None
        if not isinstance(trade, dict) or not positive(trade.get("p")) or not trade.get("t"):
            continue
        as_of = stamp(trade["t"])
        if as_of > now or as_of.astimezone(NY).date() != day:
            continue
        session = bar_session(as_of)
        if session is None:
            continue
        prev = previous.get(ticker)
        rows.append(
            dict(
                ticker=ticker,
                as_of=as_of,
                session="regular" if session == "intraday" else session,
                last=trade["p"],
                prev_close=prev if positive(prev) else None,
                delay_minutes=max(MIN_DELAY_MINUTES, math.ceil((now - as_of).total_seconds() / 60)),
                source=SOURCE,
                fetched_at=now,
            )
        )
    return rows


def previous_session(day):
    return exchange(day.year).previous_session(str(day)).date()


def previous_closes(http, headers, tickers, day):
    """Adjusted to the current date, so yesterday and today's trade share a basis."""
    prior = previous_session(day)
    params = dict(
        symbols=",".join(tickers),
        feed="sip",
        timeframe="1Day",
        adjustment="all",
        asof=day.isoformat(),
        start=datetime.combine(prior, datetime.min.time(), NY).isoformat(),
        end=datetime.combine(prior + timedelta(days=1), datetime.min.time(), NY).isoformat(),
        limit=10000,
    )
    result, tokens = {}, set()
    for _ in range(10):
        raw = require_mapping(
            http.get("https://data.alpaca.markets/v2/stocks/bars", params=dict(params), headers=headers)
        )
        if not isinstance(raw.get("bars"), dict):
            raise SourceError("Alpaca previous daily bars missing")
        for ticker, bars in raw["bars"].items():
            if ticker not in tickers or not isinstance(bars, list):
                continue
            for bar in bars:
                if stamp(bar["t"]).astimezone(NY).date() == prior and positive(bar.get("c")):
                    if ticker in result:
                        raise SourceError("Duplicate previous daily close")
                    result[ticker] = bar["c"]
        token = raw.get("next_page_token")
        if not token:
            return result
        if token in tokens:
            raise SourceError("Repeated previous daily pagination token")
        tokens.add(token)
        params["page_token"] = token
    raise SourceError("Previous daily pagination limit")


def collect_intraday(pipeline, *, http=None):
    clock, repo = pipeline.clock, pipeline.repo
    day = clock.now_utc().astimezone(NY).date()
    if not trading_day(day) or bar_session(clock.now_utc()) is None:
        return dict(processed_count=0, note="outside authorized stock session; no collection")
    http = http or HTTPClient(timeout=15, retries=0)
    written = 0
    try:
        repo.cleanup_intraday(clock.now_utc() - timedelta(days=30))
        tickers = sorted(set(pipeline.stocks) | set(repo.holding_tickers()) | ETF_TICKERS)
        if pipeline.alpaca is None:
            raise SourceError("Alpaca not configured")
        headers = pipeline.alpaca.headers
        raw = http.get(
            "https://data.alpaca.markets/v2/stocks/snapshots",
            params={"symbols": ",".join(tickers), "feed": FEED},
            headers=headers,
        )
        previous = previous_closes(http, headers, tickers, day)
        rows = parse_snapshots(raw, previous, tickers, clock)
        for row in rows:
            repo.write("intraday_snapshots", row, update=("last", "prev_close", "delay_minutes", "fetched_at"))
            written += 1
        missing = len(tickers) - len(rows)
        no_previous = sum(row["prev_close"] is None for row in rows)
        latest = max((row["as_of"] for row in rows), default=None)
        return dict(
            processed_count=len(rows),
            status="degraded" if missing or no_previous else "ok",
            source_success=bool(rows),
            note=f"feed={FEED}; contractual_delay_minutes=15; missing_current_trade={missing}; "
            f"missing_previous_close={no_previous}; latest_data_at={latest.isoformat() if latest else 'none'}",
        )
    except Exception as exc:
        # Do not retry the failed source within the same polling slot or leak URLs/keys.
        return dict(
            processed_count=written,
            status="degraded",
            source_success=False,
            note=f"{type(exc).__name__}; status={getattr(exc, 'status_code', None)}; feed={FEED}",
        )


def parse_yahoo_snapshot(raw, ticker, clock):
    """Yahoo yields are percentage points (4.98 means 4.98%), without rescaling.

    Recorded 2026-10-26 responses and Yahoo's own yield reporting establish the
    chart scale. Consumers use (last - prev_close) * 100 for basis points. Cboe
    interest-rate option index specifications use a different, tenfold scale.
    """
    try:
        chart = raw["chart"]
        if chart.get("error"):
            raise ValueError("Yahoo chart error")
        result = chart["result"][0]
        meta = result["meta"]
        if meta.get("symbol") != ticker:
            raise ValueError("Yahoo symbol mismatch")
        value, timestamp = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
        if value is None or timestamp is None:
            # Pair the close and timestamp of the same final non-null minute.
            closes = result["indicators"]["quote"][0]["close"]
            times = result["timestamp"]
            if len(times) != len(closes):
                raise ValueError("Yahoo minute arrays mismatch")
            timestamp, value = next((t, c) for t, c in reversed(list(zip(times, closes, strict=True))) if positive(c))
        if not positive(value) or not positive(timestamp):
            raise ValueError("Yahoo invalid quote")
        as_of = datetime.fromtimestamp(timestamp, timezone.utc)
        now = clock.now_utc()
        session = bar_session(as_of)
        if as_of > now or as_of.astimezone(NY).date() != now.astimezone(NY).date() or session is None:
            raise ValueError("Yahoo stale or out-of-session quote")
        previous = meta.get("chartPreviousClose")
        if not positive(previous):
            previous = meta.get("previousClose")
        return dict(
            ticker=ticker,
            as_of=as_of,
            session="regular" if session == "intraday" else session,
            last=value,
            prev_close=previous if positive(previous) else None,
            delay_minutes=math.ceil((now - as_of).total_seconds() / 60),
            source="Yahoo",
            fetched_at=now,
        )
    except (KeyError, IndexError, TypeError, StopIteration, OverflowError, OSError) as exc:
        raise ValueError("Yahoo snapshot missing or malformed") from exc


def collect_yahoo_intraday(pipeline, *, http=None):
    """Independent job/source health; at most one request per symbol and slot."""
    clock, repo = pipeline.clock, pipeline.repo
    now = clock.now_utc()
    if not trading_day(now.astimezone(NY).date()) or bar_session(now) is None:
        return dict(processed_count=0, note="outside authorized stock session; no collection")
    http = http or HTTPClient(timeout=10, retries=0)
    repo.cleanup_intraday(now - timedelta(days=30))
    written, no_previous, failures = 0, 0, []
    for ticker in YAHOO_TICKERS:
        try:
            raw = http.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(ticker, safe=""),
                params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            row = parse_yahoo_snapshot(raw, ticker, clock)
            repo.write("intraday_snapshots", row, update=("last", "prev_close", "delay_minutes", "fetched_at"))
            written += 1
            no_previous += row["prev_close"] is None
        except Exception as exc:
            failures.append(f"{ticker}:{type(exc).__name__}")
    return dict(
        processed_count=written,
        status="degraded" if failures or no_previous else "ok",
        source_success=bool(written),
        note=f"missing_previous_close={no_previous}; failures={','.join(failures) or 'none'}; yield_unit=percent",
    )
