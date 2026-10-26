"""A024 display-only delayed SIP observations. Never an input to rule A."""

import math
from datetime import datetime, timedelta

from inves_cog.ingest.http import HTTPClient, SourceError, require_mapping
from inves_cog.ingest.market import NY, bar_session, exchange, trading_day
from inves_cog.ingest.providers import stamp

FEED = "delayed_sip"
# Verified with the existing key and official snapshots contract on 2026-10-26.
MIN_DELAY_MINUTES = 15
SOURCE = "Alpaca:" + FEED


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
    if not trading_day(day):
        return dict(processed_count=0, note="non-session; no collection")
    http = http or HTTPClient(timeout=15, retries=0)
    written = 0
    try:
        repo.cleanup_intraday(clock.now_utc() - timedelta(days=30))
        tickers = sorted(set(pipeline.stocks) | set(repo.holding_tickers()) | {"SPY", "QQQ", "IWM"})
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
