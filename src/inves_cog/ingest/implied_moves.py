"""Free indicative pre-earnings straddles; stale/misaligned quotes fail closed."""

import re
from datetime import datetime, timedelta

from inves_cog.ingest.earnings_news import core_tickers
from inves_cog.ingest.http import HTTPClient, RateLimiter, SourceError
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.providers import stamp


def capture_targets(clock, earnings, core):
    now = clock.now_utc().astimezone(NY)
    if not trading_day(now.date()) or not (15, 50) <= (now.hour, now.minute) <= (15, 57):
        return []
    unique = {}
    for row in earnings:
        day = row["report_date"]
        # A pre-market release has already happened on report day at 15:50.
        if row["ticker"] in core and now.date() <= day <= now.date() + timedelta(days=7):
            if day == now.date() and row.get("time") == "pre":
                continue
            unique[(row["ticker"], day)] = row
    return [unique[k] for k in sorted(unique)]


def positive(value):
    import math

    if value is None or isinstance(value, bool):
        return None
    result = float(value)
    return result if math.isfinite(result) and result > 0 else None


def select_move(ticker, report_date, report_time, snapshots, captured_at, spot_at):
    pairs = {}
    for symbol, snapshot in snapshots.items():
        match = re.fullmatch(re.escape(ticker) + r"(\d{6})([CP])(\d{8})", symbol)
        if not match:
            continue
        expiry = datetime.strptime(match[1], "%y%m%d").date()
        earliest = report_date + timedelta(days=0 if report_time == "pre" else 1)
        if expiry < earliest:
            continue
        pairs.setdefault((expiry, int(match[3]) / 1000), {})[match[2]] = snapshot
    if not pairs:
        return None
    nearest_expiry = min(key[0] for key in pairs)
    valid = []
    for (expiry, strike), pair in pairs.items():
        if expiry != nearest_expiry or set(pair) != {"C", "P"}:
            continue
        quotes = [pair[s].get("latestQuote") or {} for s in ("C", "P")]
        try:
            times = [stamp(q["t"]) for q in quotes]
        except (KeyError, TypeError, ValueError):
            continue
        at = max(times)
        if abs((times[0] - times[1]).total_seconds()) > 1 or not 0 <= (captured_at - at).total_seconds() <= 120:
            continue
        spot = spot_at(at)
        if not spot or spot["as_of"].astimezone(NY).date() != at.astimezone(NY).date():
            continue
        # Within one second, same regular session, including the boundary check.
        local = at.astimezone(NY)
        if abs((spot["as_of"] - at).total_seconds()) > 1 or not (9, 30) <= (local.hour, local.minute) < (16, 0):
            continue
        px = positive(spot["last"])
        source = {"AlpacaIEX": "IEX", "IEX": "IEX", "AlpacaSIP": "SIP", "Alpaca": "SIP", "SIP": "SIP"}.get(
            spot["source"]
        )
        mids = []
        for q in quotes:
            bid, ask = positive(q.get("bp")), positive(q.get("ap"))
            mids.append((bid + ask) / 2 if bid and ask and bid <= ask else None)
        if not px or not source or None in mids:
            continue
        valid.append(
            (
                expiry,
                abs(strike - px),
                strike,
                dict(
                    ticker=ticker,
                    report_date=report_date,
                    report_time=report_time,
                    captured_at=captured_at,
                    quote_time=at,
                    expiry=expiry,
                    strike=strike,
                    spot=px,
                    spot_source=source,
                    call_mid=mids[0],
                    put_mid=mids[1],
                    straddle_pct=sum(mids) / px,
                    iv_call=positive(pair["C"].get("impliedVolatility")),
                    iv_put=positive(pair["P"].get("impliedVolatility")),
                    feed="indicative",
                ),
            )
        )
    return min(valid, key=lambda r: r[:3])[3] if valid else None


def option_chain(http, headers, ticker, report_date, report_time):
    params = {
        "feed": "indicative",
        "expiration_date_gte": (report_date + timedelta(days=0 if report_time == "pre" else 1)).isoformat(),
        "limit": 1000,
    }
    result, seen = {}, set()
    for _ in range(20):
        data = http.get(
            "https://data.alpaca.markets/v1beta1/options/snapshots/" + ticker,
            params=dict(params),
            headers=headers,
            retry_rate_limit=False,
        )
        if not isinstance(data, dict) or not isinstance(data.get("snapshots"), dict):
            raise SourceError("Indicative option snapshots missing")
        result.update(data["snapshots"])
        token = data.get("next_page_token")
        if not token:
            return result
        if token in seen:
            raise SourceError("Repeated indicative option pagination")
        seen.add(token)
        params["page_token"] = token
    raise SourceError("Indicative option page budget exhausted")


def collect_moves(*, clock, db, values, http=None):
    now = clock.now_utc()
    rows = db.execute(
        "SELECT ticker,report_date,time FROM ingest.earnings_calendar "
        "WHERE report_date BETWEEN %s AND %s ORDER BY fetched_at,ticker",
        (now.astimezone(NY).date(), now.astimezone(NY).date() + timedelta(days=7)),
    ).fetchall()
    http = http or HTTPClient(retries=0, timeout=15, limiter=RateLimiter(200, 60), pool=True)
    headers = {"APCA-API-KEY-ID": values["APCA_API_KEY_ID"], "APCA-API-SECRET-KEY": values["APCA_API_SECRET_KEY"]}
    saved, missing = 0, 0
    for event in capture_targets(clock, rows, core_tickers()):
        ticker, day, slot = event["ticker"], event["report_date"], event.get("time") or "unknown"
        if db.execute(
            "SELECT 1 FROM ingest.earnings_implied_moves WHERE ticker=%s AND report_date=%s "
            "AND captured_at>=%s LIMIT 1",
            (ticker, day, now.astimezone(NY).replace(hour=0, minute=0, second=0, microsecond=0)),
        ).fetchone():
            continue
        try:
            chain = option_chain(http, headers, ticker, day, slot)
        except SourceError as exc:
            exc.degraded = True
            exc.processed_count = saved
            raise
        spots = {}

        def spot_at(at, ticker=ticker, spots=spots):
            if at not in spots:
                spots[at] = aligned_spot(db, http, headers, ticker, at)
            return spots[at]

        try:
            row = select_move(ticker, day, slot, chain, clock.now_utc(), spot_at)
        except SourceError as exc:
            exc.degraded = True
            exc.processed_count = saved
            raise
        if row is None:
            missing += 1
            continue
        columns = tuple(row)
        db.execute(
            "INSERT INTO ingest.earnings_implied_moves ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join(["%s"] * len(columns))
            + ") ON CONFLICT DO NOTHING",
            tuple(row[c] for c in columns),
        )
        saved += 1
    return {
        "processed_count": saved,
        "status": "degraded" if missing else "ok",
        "note": f"{missing} events missing aligned indicative quotes" if missing else None,
    }


def aligned_spot(db, http, headers, ticker, at):
    row = db.execute(
        "SELECT last,as_of,source FROM ingest.intraday_snapshots WHERE ticker=%s "
        "AND as_of BETWEEN %s AND %s ORDER BY abs(extract(epoch FROM as_of-%s)) LIMIT 1",
        (ticker, at - timedelta(seconds=1), at + timedelta(seconds=1), at),
    ).fetchone()
    if row:
        return row
    data = http.get(
        "https://data.alpaca.markets/v2/stocks/trades",
        params={
            "feed": "iex",
            "symbols": ticker,
            "start": (at - timedelta(seconds=1)).isoformat(),
            "end": (at + timedelta(seconds=1)).isoformat(),
            "limit": 1000,
        },
        headers=headers,
        retry_rate_limit=False,
    )
    trades = (data.get("trades") or {}).get(ticker, [])
    valid = [r for r in trades if abs((stamp(r["t"]) - at).total_seconds()) <= 1 and positive(r.get("p"))]
    if not valid:
        return None
    trade = min(valid, key=lambda r: abs((stamp(r["t"]) - at).total_seconds()))
    return {"last": trade["p"], "as_of": stamp(trade["t"]), "source": "IEX"}
