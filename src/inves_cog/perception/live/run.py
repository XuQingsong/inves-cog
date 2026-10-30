"""B-070: one live pass. Called from schedule_live_perception every 5 min
on trading days 04:00-20:00 ET. Read paths are also used by the replay."""

from datetime import time as dtime

import numpy as np

from inves_cog.ingest.market import NY, trading_day
from inves_cog.perception.anomaly.detect import limits
from inves_cog.perception.core_companies import core_companies
from inves_cog.perception.live.detect import apply_round, basket_hits, market_hits, stock_hits
from inves_cog.perception.live.link import link_causes, update_reactions


def in_window(now):
    local = now.astimezone(NY)
    return trading_day(local.date()) and dtime(4, 0) <= local.time() <= dtime(20, 0)


def _latest_quotes(connection, day):
    rows = connection.execute(
        """SELECT DISTINCT ON (ticker) ticker, last, prev_close, session, as_of
           FROM ingest.intraday_snapshots
           ORDER BY ticker, as_of DESC""",
    ).fetchall()
    quotes = {}
    for r in rows:
        pc = r["prev_close"]
        if r["last"] is None or not pc:
            continue
        quotes[r["ticker"]] = {
            "ret": float(r["last"]) / float(pc) - 1,
            "as_of": r["as_of"],
            "session": r["session"],
        }
    return quotes


def _sigmas(connection):
    return {
        r["ticker"]: r["sigma"]
        for r in connection.execute(
            """SELECT ticker, sigma FROM marketstate.daily WHERE session='close'
               AND trade_date = (SELECT max(trade_date) FROM marketstate.daily WHERE session='close')"""
        ).fetchall()
    }


def _basket_sigmas(connection, baskets):
    out = {}
    for b in baskets:
        rows = connection.execute(
            """SELECT ret_ew FROM marketstate.baskets WHERE basket_id=%s AND session='close'
               ORDER BY trade_date DESC LIMIT 120""",
            (b["basket_id"],),
        ).fetchall()
        if len(rows) >= 40:
            out[b["basket_id"]] = float(np.std([r["ret_ew"] for r in rows]))
            continue
        # fallback: equal-weight from bars_daily, >=40 sessions
        members = [(m["ticker"] if isinstance(m, dict) else m) for m in b["members"]]
        bars = connection.execute(
            """SELECT trade_date, avg(ret) AS ew FROM (
                   SELECT trade_date, ticker, close / lag(close) OVER (
                       PARTITION BY ticker ORDER BY trade_date) - 1 AS ret
                   FROM ingest.bars_daily WHERE ticker = ANY(%s)) q
               WHERE ret IS NOT NULL GROUP BY trade_date
               ORDER BY trade_date DESC LIMIT 120""",
            (members,),
        ).fetchall()
        if len(bars) >= 40:
            out[b["basket_id"]] = float(np.std([r["ew"] for r in bars]))
    return out


def _l3_of(baskets):
    l3 = {}
    for b in baskets:
        if str(b.get("level")).upper() in ("L3", "3"):
            for m in b["members"]:
                t = m["ticker"] if isinstance(m, dict) else m
                l3.setdefault(t, b)
    return l3


def live_pass(connection, now):
    """Returns counts; safe to call every loop iteration (no-op outside window)."""
    local = now.astimezone(NY)
    day = local.date()
    if not in_window(now):
        return {"skipped": True}
    quotes = _latest_quotes(connection, day)
    sigmas = _sigmas(connection)
    baskets = connection.execute("SELECT basket_id, members, level FROM graph.baskets").fetchall()
    bsig = _basket_sigmas(connection, baskets)
    rule = limits()[1]
    session = "post" if local.time() >= dtime(16, 0) else ("regular" if local.time() >= dtime(9, 30) else "pre")
    hits = (
        stock_hits(quotes, _l3_of(baskets), sigmas, rule, session)
        + basket_hits(quotes, baskets, bsig, rule)
        + market_hits(quotes, rule)
    )
    n = apply_round(connection, hits, now, day, session)
    linked = link_causes(connection, day, set(core_companies()))
    reacted = update_reactions(connection, now)
    return {"hits": n, "linked": linked, "reacted": reacted}
