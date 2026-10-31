"""B-072: one card per core-company earnings report (§3 of the brief).

`build_card` is pure-ish: callers fetch nothing beyond the connection; the
function computes stage/card/missing deterministically so the disposable-DB
test and the production read-only replay share the same code path.
"""

import json
from datetime import datetime, timedelta
from statistics import median

from inves_cog.ingest.market import NY

STRONG_REPORT_KINDS = ("earnings_result", "guidance", "capex")


def _trading_days(connection, day, back=10, forward=8):
    rows = connection.execute("SELECT DISTINCT trade_date FROM ingest.bars_daily ORDER BY trade_date").fetchall()
    days = [r["trade_date"] for r in rows]
    return days


def _next_session(connection, day):
    row = connection.execute(
        "SELECT min(trade_date) AS d FROM ingest.bars_daily WHERE trade_date > %s", (day,)
    ).fetchone()
    return row["d"]


def _prev_session(connection, day):
    row = connection.execute(
        "SELECT max(trade_date) AS d FROM ingest.bars_daily WHERE trade_date < %s", (day,)
    ).fetchone()
    return row["d"]


def _close(connection, ticker, day):
    row = connection.execute(
        "SELECT close FROM ingest.bars_daily WHERE ticker=%s AND trade_date=%s",
        (ticker, day),
    ).fetchone()
    return float(row["close"]) if row and row["close"] is not None else None


def _window_start(report_date, report_time):
    if report_time == "post":
        return datetime(report_date.year, report_date.month, report_date.day, 15, 30, tzinfo=NY)
    prev = previous_trading_day(report_date)
    return datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)


def previous_trading_day(day):
    d = day - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def stage_of(connection, ticker, report_date, report_time, now):
    """voted once the voting-day close exists; released inside the report
    window; upcoming otherwise."""
    local_now = now.astimezone(NY)
    if report_time == "pre":
        vote_day = report_date
    else:
        vote_day = _next_session(connection, report_date)
    if vote_day is not None and _close(connection, ticker, vote_day) is not None:
        if local_now.date() > vote_day or (
            local_now.date() == vote_day and (local_now.hour, local_now.minute) >= (20, 0)
        ):
            return "voted"
    if now >= _window_start(report_date, report_time):
        return "released"
    return "upcoming"


def candidates(connection, today):
    """Core-company calendar rows with report_date in [today-3 trading
    days, today+7 calendar days]."""
    lo = today - timedelta(days=7)  # cover 3 trading days incl. weekends
    return connection.execute(
        "SELECT ticker, report_date, time FROM ingest.earnings_calendar "
        "WHERE report_date >= %s AND report_date <= %s ORDER BY report_date",
        (lo, today + timedelta(days=7)),
    ).fetchall()


def _consensus(connection, ticker):
    row = connection.execute(
        "SELECT as_of, eps_cq, raw FROM fundamentals.consensus_snapshot WHERE ticker=%s ORDER BY as_of DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if not row:
        return None
    rev = (row.get("raw") or {}).get("revenue_estimate", {}).get("0q", {})
    return {
        "as_of": str(row["as_of"]),
        "eps": float(row["eps_cq"]) if row["eps_cq"] is not None else None,
        "rev": rev.get("avg"),
    }


def _implied_move(connection, ticker, report_date):
    row = connection.execute(
        "SELECT captured_at, quote_time, straddle_pct, spot FROM ingest.earnings_implied_moves "
        "WHERE ticker=%s AND report_date=%s ORDER BY captured_at DESC LIMIT 1",
        (ticker, report_date),
    ).fetchone()
    if not row:
        return None
    return {
        "straddle_pct": float(row["straddle_pct"]),
        "captured_at": str(row["captured_at"]),
        "quote_time": str(row["quote_time"]) if row["quote_time"] else None,
        "note": "参考报价，非实时成交",
    }


def _history(connection, ticker, report_date):
    """Past earnings vote returns for this ticker from calendar history
    (shallow on this deployment -> '历史不足' below 4)."""
    rows = connection.execute(
        "SELECT report_date, time FROM ingest.earnings_calendar "
        "WHERE ticker=%s AND report_date < %s ORDER BY report_date DESC LIMIT 8",
        (ticker, report_date),
    ).fetchall()
    votes = []
    for r in rows:
        v = _vote_return(connection, ticker, r["report_date"], r["time"])
        if v is not None:
            votes.append({"report_date": str(r["report_date"]), "ret": v})
    return votes


def _vote_return(connection, ticker, report_date, report_time):
    """post: next-session close / report-date close - 1;
    pre: report-date close / prior-session close - 1."""
    if report_time == "pre":
        base_day = _prev_session(connection, report_date)
        vote_day = report_date
    else:
        base_day = report_date
        vote_day = _next_session(connection, report_date)
    if base_day is None or vote_day is None:
        return None
    base, vote = _close(connection, ticker, base_day), _close(connection, ticker, vote_day)
    if base is None or vote is None or base == 0:
        return None
    return vote / base - 1


def _events(connection, ticker, report_date, report_time, now):
    start = _window_start(report_date, report_time)
    rows = connection.execute(
        "SELECT event_id, kind, headline, facts, importance, first_seen_at, reaction "
        "FROM perception.news_events WHERE subject=%s AND kind = ANY(%s) "
        "AND first_seen_at >= %s AND first_seen_at <= %s "
        "ORDER BY importance DESC, first_seen_at ASC",
        (ticker, list(STRONG_REPORT_KINDS), start, now),
    ).fetchall()
    out = []
    for e in rows:
        out.append(
            {
                "event_id": e["event_id"],
                "kind": e["kind"],
                "headline": e["headline"],
                "facts": e.get("facts") or {},
                "importance": e["importance"],
                "first_seen_at": str(e["first_seen_at"]),
                "reaction": e.get("reaction") or {},
            }
        )
    return out


def _live_anomalies(connection, event_ids):
    if not event_ids:
        return []
    rows = connection.execute(
        "SELECT scope, subject, direction, peak_ret, peak_z, status "
        "FROM perception.live_anomalies WHERE cause_event_id = ANY(%s)",
        (event_ids,),
    ).fetchall()
    return [
        {
            "scope": r["scope"],
            "subject": r["subject"],
            "direction": r["direction"],
            "peak_ret": float(r["peak_ret"]) if r["peak_ret"] is not None else None,
            "peak_z": float(r["peak_z"]) if r["peak_z"] is not None else None,
            "status": r["status"],
        }
        for r in rows
    ]


def _segment_reaction(connection, ticker, segment, members, report_date, report_time):
    """Same-window equal-weight return of segment peers + the ticker's
    L2/L3 baskets; counts followers (same sign & |ret| >= |vote|/3)."""
    if report_time == "pre":
        base_day = _prev_session(connection, report_date)
        vote_day = report_date
    else:
        base_day = report_date
        vote_day = _next_session(connection, report_date)
    if base_day is None or vote_day is None:
        return None
    peer_rets = []
    for peer in members:
        if peer == ticker:
            continue
        b, v = _close(connection, peer, base_day), _close(connection, peer, vote_day)
        if b and v:
            peer_rets.append((peer, v / b - 1))
    baskets = connection.execute(
        "SELECT basket_id, name, members FROM graph.baskets WHERE layer IN ('L2','L3')",
    ).fetchall()
    basket_rets = []
    for b in baskets:
        tickers = [m["ticker"] if isinstance(m, dict) else m for m in (b["members"] or [])]
        if ticker not in tickers:
            continue
        rets = []
        for t in tickers:
            bc, vc = _close(connection, t, base_day), _close(connection, t, vote_day)
            if bc and vc:
                rets.append(vc / bc - 1)
        if rets:
            basket_rets.append({"basket_id": b["basket_id"], "name": b["name"], "ret": sum(rets) / len(rets)})
    return {"peers": peer_rets, "baskets": basket_rets}


def build_card(connection, ticker, report_date, report_time, now, segment="", peers=()):
    """-> (stage, card dict, missing list). No writes."""
    missing = []
    stage = stage_of(connection, ticker, report_date, report_time, now)
    card = {"ticker": ticker, "report_date": str(report_date), "report_time": report_time}

    cons = _consensus(connection, ticker)
    if cons and (cons["eps"] is not None or cons["rev"] is not None):
        card["consensus"] = cons
    else:
        missing.append("一致预期")

    imp = _implied_move(connection, ticker, report_date)
    if imp:
        card["implied_move"] = imp
    else:
        missing.append("期权预期")

    card["segment"] = segment or None
    card["peers"] = [p for p in peers if p != ticker]

    if stage == "upcoming":
        hist = _history(connection, ticker, report_date)
        if len(hist) >= 4:
            card["history"] = {
                "votes": hist,
                "median_abs": median(abs(v["ret"]) for v in hist),
            }
        else:
            card["history"] = {"votes": hist, "median_abs": None, "note": "历史不足"}
    else:
        events = _events(connection, ticker, report_date, report_time, now)
        card["events"] = events or missing.append("报道事件") or []
        card["live_anomalies"] = _live_anomalies(connection, [e["event_id"] for e in events])
        if stage == "voted":
            vote = _vote_return(connection, ticker, report_date, report_time)
            if vote is None:
                missing.append("投票涨跌")
            else:
                card["vote_ret"] = vote
                if imp:
                    ratio = abs(vote) / imp["straddle_pct"] if imp["straddle_pct"] else None
                    card["vs_implied"] = (
                        (
                            "超出期权预期"
                            if ratio and ratio >= 1.0
                            else "远小于期权预期"
                            if ratio and ratio < 0.5
                            else "在预期内"
                        )
                        if ratio is not None
                        else "无期权参照"
                    )
                else:
                    card["vs_implied"] = "无期权参照"
                seg = _segment_reaction(connection, ticker, segment, peers, report_date, report_time)
                if seg:
                    followed = sum(1 for _, r in seg["peers"] if r * vote > 0 and abs(r) >= abs(vote) / 3)
                    card["segment_reaction"] = {
                        "peers": seg["peers"],
                        "baskets": seg["baskets"],
                        "followed": followed,
                        "not_followed": len(seg["peers"]) - followed,
                    }
    return stage, card, missing


def update_cards(connection, now, core_segments):
    """Recompute one card per candidate; upsert. Returns row count."""
    today = now.astimezone(NY).date()
    rows = connection.execute(
        """SELECT DISTINCT c.ticker, c.report_date, c.time
           FROM ingest.earnings_calendar c WHERE c.report_date >= %s AND c.report_date <= %s""",
        (today - timedelta(days=7), today + timedelta(days=7)),
    ).fetchall()
    written = 0
    for r in rows:
        ticker = r["ticker"]
        if ticker not in core_segments:
            continue
        # restrict window to [today-3 trading days, today+7d] using bars sessions
        stage, card, missing = build_card(
            connection,
            ticker,
            r["report_date"],
            r["time"] or "unknown",
            now,
            segment=core_segments[ticker],
            peers=_segment_peers(core_segments, ticker),
        )
        connection.execute(
            """INSERT INTO perception.earnings_cards
               (ticker, report_date, report_time, stage, card, missing, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,now())
               ON CONFLICT (ticker, report_date) DO UPDATE SET
                 report_time=EXCLUDED.report_time, stage=EXCLUDED.stage,
                 card=EXCLUDED.card, missing=EXCLUDED.missing, updated_at=now()""",
            (ticker, r["report_date"], r["time"] or "unknown", stage, json.dumps(card, default=str), missing),
        )
        written += 1
    return written


def _segment_peers(core_segments, ticker):
    seg = core_segments.get(ticker)
    return sorted(t for t, s in core_segments.items() if s == seg and t != ticker)
