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


def yahoo_symbols(now):
    local = now.astimezone(NY)
    minute = local.hour * 60 + local.minute
    if 240 <= minute < 1200:
        if trading_day(local.date()):
            return YAHOO_TICKERS
        # Sunday futures reopen at 18 ET before Monday's trading session.
        if local.weekday() == 6 and minute >= 1080 and trading_day(local.date() + timedelta(days=1)):
            return YAHOO_TICKERS
        return ()
    reference = local.date() + timedelta(days=1) if minute >= 1200 else local.date()
    return YAHOO_TICKERS if trading_day(reference) else ("BTC-USD",)


def snapshot_session(as_of):
    session = bar_session(as_of)
    return ("regular" if session == "intraday" else session) or "overnight"


def cached_previous(pipeline, http, headers, tickers, day):
    # Both stock and wide polling reuse verified adjusted daily closes.
    import hashlib

    signature = hashlib.sha256(",".join(tickers).encode()).hexdigest()[:16]
    key = "snapshot-previous:" + day.isoformat() + ":" + signature
    previous = pipeline.repo.get_cursor(key)
    previous = previous if isinstance(previous, dict) else {}
    missing = sorted(set(tickers) - set(previous))
    if missing:
        fetched = previous_closes(http, headers, missing, day)
        previous.update({ticker: fetched.get(ticker) for ticker in missing})
        pipeline.repo.set_cursor(key, previous, pipeline.clock.now_utc())
    return previous


def maintain(pipeline):
    now, repo = pipeline.clock.now_utc(), pipeline.repo
    key = "snapshot-maintenance"
    old = repo.get_cursor(key)
    day = now.astimezone(NY).date()
    if not isinstance(old, dict) or old.get("day") != day.isoformat():
        repo.compact_intraday(now)
        repo.cleanup_wide_snapshots(day, previous_session(day))
        repo.set_cursor(key, {"day": day.isoformat()}, now)


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
    return exchange(day.year).date_to_session(str(day - timedelta(days=1)), direction="previous").date()


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


def stock_tickers(pipeline):
    return sorted(set(pipeline.stocks) | set(pipeline.repo.holding_tickers()) | ETF_TICKERS)


def collect_intraday(pipeline, *, http=None):
    clock, repo = pipeline.clock, pipeline.repo
    day = clock.now_utc().astimezone(NY).date()
    if not trading_day(day) or bar_session(clock.now_utc()) is None:
        return dict(processed_count=0, note="outside authorized stock session; no collection")
    http = http or HTTPClient(timeout=15, retries=0)
    written = 0
    try:
        maintain(pipeline)
        tickers = stock_tickers(pipeline)
        if pipeline.alpaca is None:
            raise SourceError("Alpaca not configured")
        headers = pipeline.alpaca.headers
        raw = http.get(
            "https://data.alpaca.markets/v2/stocks/snapshots",
            params={"symbols": ",".join(tickers), "feed": FEED},
            headers=headers,
        )
        previous = cached_previous(pipeline, http, headers, tickers, day)
        rows = parse_snapshots(raw, previous, tickers, clock)
        for row in rows:
            repo.write("intraday_snapshots", row)
            written += 1
        missing = len(tickers) - len(rows)
        no_previous = sum(row["prev_close"] is None for row in rows)
        latest = max((row["as_of"] for row in rows), default=None)
        return dict(
            processed_count=len(rows),
            status="degraded" if missing or no_previous else "ok",
            source_success=bool(rows),
            latest_data_at=latest.isoformat() if latest else None,
            note=f"feed={FEED}; contractual_delay_minutes=15; missing_current_trade={missing}; "
            f"missing_previous_close={no_previous}; latest_data_at={latest.isoformat() if latest else 'none'}",
        )
    except Exception as exc:
        # Do not retry the failed source within the same polling slot or leak URLs/keys.
        return dict(
            processed_count=written,
            status="degraded",
            source_success=False,
            rate_limited=getattr(exc, "status_code", None) == 429,
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
        session = snapshot_session(as_of)
        overnight = snapshot_session(now) == "overnight"
        earliest = now.astimezone(NY).replace(hour=0, minute=0, second=0, microsecond=0)
        if overnight:
            earliest = now - timedelta(hours=30)
        if as_of > now or as_of < earliest:
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
    symbols = yahoo_symbols(now)
    if not symbols:
        return dict(processed_count=0, note="outside authorized macro session; no collection")
    http = http or HTTPClient(timeout=10, retries=0)
    maintain(pipeline)
    written, no_previous, failures, latest = 0, 0, [], None

    def fetch(ticker):
        try:
            raw = http.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(ticker, safe=""),
                params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            return ticker, parse_yahoo_snapshot(raw, ticker, clock), None
        except Exception as exc:
            return ticker, None, f"{type(exc).__name__}:status={getattr(exc, 'status_code', None)}"

    # Network waits overlap, but database writes stay on their owning thread.
    # Thirteen bounded 10s requests cannot serialize into a 130s poll.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=13) as executor:
        for ticker, row, error in executor.map(fetch, symbols):
            if error:
                failures.append(f"{ticker}:{error}")
                continue
            repo.write("intraday_snapshots", row)
            written += 1
            no_previous += row["prev_close"] is None
            latest = max(latest or row["as_of"], row["as_of"])
    return dict(
        processed_count=written,
        status="degraded" if failures or no_previous else "ok",
        source_success=bool(written),
        latest_data_at=latest.isoformat() if latest else None,
        note=f"missing_previous_close={no_previous}; failures={','.join(failures) or 'none'}; yield_unit=percent",
    )


def collect_wide(pipeline, *, http=None):
    now = pipeline.clock.now_utc()
    local = now.astimezone(NY)
    minute = local.hour * 60 + local.minute
    if not trading_day(local.date()) or not 570 <= minute < 960:
        return dict(processed_count=0, note="outside regular session; no collection")
    http = http or HTTPClient(timeout=10, retries=0)
    written, missing, latest = 0, 0, None
    try:
        maintain(pipeline)
        if pipeline.alpaca is None:
            raise SourceError("Alpaca not configured")
        tickers = sorted({r["ticker"] for r in pipeline.repo.latest_wide() if r["included"]})
        headers = pipeline.alpaca.headers
        for offset in range(0, len(tickers), 200):
            batch = tickers[offset : offset + 200]
            raw = http.get(
                "https://data.alpaca.markets/v2/stocks/snapshots",
                params={"symbols": ",".join(batch), "feed": FEED},
                headers=headers,
            )
            previous = cached_previous(pipeline, http, headers, batch, local.date())
            rows = parse_snapshots(raw, previous, batch, pipeline.clock)
            missing += len(batch) - len(rows) + sum(r["prev_close"] is None for r in rows)
            for row in rows:
                pipeline.repo.write(
                    "wide_snapshots", {k: v for k, v in row.items() if k not in {"session", "delay_minutes"}}
                )
                written += 1
                latest = max(latest or row["as_of"], row["as_of"])
        return dict(
            processed_count=written,
            source_success=bool(written) and not missing,
            status="degraded" if missing or not tickers else "ok",
            latest_data_at=latest.isoformat() if latest else None,
            note=f"feed={FEED}; requested={len(tickers)}; missing_trade_or_previous={missing}",
        )
    except Exception as exc:
        return dict(
            processed_count=written,
            status="degraded",
            source_success=False,
            rate_limited=getattr(exc, "status_code", None) == 429,
            note=f"{type(exc).__name__}; status={getattr(exc, 'status_code', None)}",
        )


def parse_iex_trades(raw, previous, tickers, clock):
    """IEX has no feed delay; the last price-updating print can still be old.

    Keep its original timestamp/session, including the previous day's last
    print before IEX opens at 08 ET. Never relabel that observation as today.
    """
    trades = require_mapping(require_mapping(raw).get("trades"))
    now, rows = clock.now_utc(), []
    for ticker in tickers:
        trade = trades.get(ticker)
        if not isinstance(trade, dict) or trade.get("x") != "V" or not positive(trade.get("p")) or not trade.get("t"):
            continue
        try:
            as_of = stamp(trade["t"])
        except (ValueError, TypeError, OverflowError):
            continue
        session = bar_session(as_of)
        if as_of > now or as_of < now - timedelta(days=30) or session is None:
            continue
        prev = previous.get(ticker)
        rows.append(
            dict(
                ticker=ticker,
                as_of=as_of,
                session="regular" if session == "intraday" else session,
                last=trade["p"],
                prev_close=prev if positive(prev) else None,
                delay_minutes=0,
                source="Alpaca:iex",
                fetched_at=now,
            )
        )
    return rows


def collect_iex_intraday(pipeline, *, http=None):
    """Same authorized scope/cadence as SIP, isolated failure and source health."""
    now, repo = pipeline.clock.now_utc(), pipeline.repo
    day = now.astimezone(NY).date()
    if not trading_day(day) or bar_session(now) is None:
        return dict(processed_count=0, note="outside authorized stock session; no IEX request")
    http = http or HTTPClient(timeout=15, retries=0)
    written = 0
    try:
        maintain(pipeline)
        tickers = stock_tickers(pipeline)
        if pipeline.alpaca is None:
            raise SourceError("Alpaca not configured")
        raw = http.get(
            "https://data.alpaca.markets/v2/stocks/trades/latest",
            params={"symbols": ",".join(tickers), "feed": "iex"},
            headers=pipeline.alpaca.headers,
        )
        previous = cached_previous(pipeline, http, pipeline.alpaca.headers, tickers, day)
        rows = parse_iex_trades(raw, previous, tickers, pipeline.clock)
        for row in rows:
            repo.write("intraday_snapshots", row)
            written += 1
        latest = max((r["as_of"] for r in rows), default=None)
        missing = len(tickers) - len(rows)
        no_previous = sum(r["prev_close"] is None for r in rows)
        age = max(((now - r["as_of"]).total_seconds() for r in rows), default=None)
        return dict(
            processed_count=written,
            source_success=bool(rows),
            status="degraded" if missing or no_previous else "ok",
            latest_data_at=latest.isoformat() if latest else None,
            note=f"feed=iex; feed_delay_minutes=0; IEX_equities_ET=08:00-17:00; "
            f"missing_last_trade={missing}; missing_previous_close={no_previous}; "
            f"max_trade_age_seconds={age}; original_trade_time_preserved=true",
        )
    except Exception as exc:
        return dict(
            processed_count=written,
            status="degraded",
            source_success=False,
            rate_limited=getattr(exc, "status_code", None) == 429,
            note=f"{type(exc).__name__}; status={getattr(exc, 'status_code', None)}; feed=iex",
        )
