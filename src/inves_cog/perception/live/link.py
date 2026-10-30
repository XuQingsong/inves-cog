"""B-070 §2 anomaly<->event linking and §3 event reaction."""

import json
from datetime import timedelta

from inves_cog.ingest.intraday import previous_session
from inves_cog.ingest.market import NY

STRONG = {"earnings_result", "guidance", "capex", "supply_shock", "mna", "regulatory"}
LINK_GRACE = timedelta(minutes=30)


def _window_start(day):
    prev = previous_session(day)
    from datetime import datetime

    return datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)


def link_causes(connection, day, core):
    """Re-link every pass while cause_event_id is null. Window:
    prev-session 16:00 ET -> anomaly first_seen_at + 30 min.
    cause_lag_minutes signed (negative = price moved before the news)."""
    rows = connection.execute(
        """SELECT scope, subject, direction, first_seen_at
           FROM perception.live_anomalies
           WHERE trade_date=%s AND cause_event_id IS NULL
           ORDER BY first_seen_at""",
        (day,),
    ).fetchall()
    start = _window_start(day)
    linked = 0
    for row in rows:
        end = row["first_seen_at"] + LINK_GRACE
        scope = row["scope"]
        if scope == "stock":
            cand = connection.execute(
                """SELECT event_id, kind, first_seen_at FROM perception.news_events
                   WHERE subject=%s AND kind = ANY(%s)
                     AND first_seen_at >= %s AND first_seen_at <= %s
                   ORDER BY importance DESC, first_seen_at ASC LIMIT 1""",
                (row["subject"], sorted(STRONG), start, end),
            ).fetchone()
        elif scope == "basket":
            cand = connection.execute(
                """SELECT event_id, kind, first_seen_at FROM perception.news_events
                   WHERE kind = ANY(%s) AND first_seen_at >= %s AND first_seen_at <= %s
                     AND (subject = ANY(%s) OR subject = ANY(%s))
                   ORDER BY importance DESC, first_seen_at ASC LIMIT 1""",
                (
                    sorted(STRONG),
                    start,
                    end,
                    _basket_member_tickers(connection, row["subject"]),
                    _basket_core(connection, row["subject"], core),
                ),
            ).fetchone()
        else:  # market
            cand = connection.execute(
                """SELECT event_id, kind, first_seen_at FROM perception.news_events
                   WHERE first_seen_at >= %s AND first_seen_at <= %s
                     AND (kind='regulatory'
                          OR (kind IN ('earnings_result','guidance') AND subject = ANY(%s)))
                   ORDER BY importance DESC, first_seen_at ASC LIMIT 1""",
                (start, end, sorted(core)),
            ).fetchone()
        if cand is None:
            continue
        lag = (row["first_seen_at"] - cand["first_seen_at"]).total_seconds() / 60.0
        connection.execute(
            """UPDATE perception.live_anomalies
               SET cause_event_id=%s, cause_kind=%s, cause_lag_minutes=%s, updated_at=now()
               WHERE trade_date=%s AND scope=%s AND subject=%s AND direction=%s""",
            (cand["event_id"], cand["kind"], lag, day, scope, row["subject"], row["direction"]),
        )
        linked += 1
    return linked


def _basket_member_tickers(connection, basket_id):
    row = connection.execute("SELECT members FROM graph.baskets WHERE basket_id=%s", (basket_id,)).fetchone()
    if not row:
        return ["__none__"]
    return [m["ticker"] if isinstance(m, dict) else m for m in row["members"]]


def _basket_core(connection, basket_id, core):
    members = set(_basket_member_tickers(connection, basket_id))
    return sorted(t for t in members if t in core) or ["__none__"]


def update_reactions(connection, now):
    """§3 reaction for strong events seen in the last 24h. Filled fields
    are never recomputed; missing data -> null."""
    events = connection.execute(
        """SELECT event_id, subject, first_seen_at, reaction FROM perception.news_events
           WHERE kind = ANY(%s) AND first_seen_at >= %s - interval '24 hours'
             AND first_seen_at <= %s""",
        (sorted(STRONG), now, now),
    ).fetchall()
    written = 0
    for ev in events:
        reaction = dict(ev.get("reaction") or {})
        fs = ev["first_seen_at"]
        if "base" not in reaction:
            pub = connection.execute(
                """SELECT min(i.published_at) AS at FROM ingest.info_items i
                   WHERE i.info_id = ANY(
                       (SELECT info_ids FROM perception.news_events WHERE event_id=%s))""",
                (ev["event_id"],),
            ).fetchone()
            base_time, source = (pub["at"], "published_at") if pub and pub["at"] else (fs, "first_seen_at")
            base = connection.execute(
                """SELECT last, as_of, prev_close FROM ingest.intraday_snapshots
                   WHERE ticker=%s AND as_of <= %s ORDER BY as_of DESC LIMIT 1""",
                (ev["subject"], base_time),
            ).fetchone()
            if base:
                reaction["base"] = {
                    "px": float(base["last"]),
                    "at": str(base["as_of"]),
                    "prev_close": float(base["prev_close"]) if base["prev_close"] else None,
                    "source": source,
                }
            elif pub or fs:
                close = connection.execute(
                    """SELECT prev_close, close FROM ingest.bars_daily
                       WHERE ticker=%s AND trade_date < %s::date ORDER BY trade_date DESC LIMIT 1""",
                    (ev["subject"], base_time),
                ).fetchone()
                if close:
                    px = float(close["close"] or close["prev_close"] or 0)
                    reaction["base"] = {"px": px, "at": str(base_time), "prev_close": px, "source": "prev_close"}
                else:
                    reaction["base"] = None
            else:
                reaction["base"] = None
        base_at = reaction["base"]["at"] if reaction.get("base") else None
        for key, minutes in (("m15", 15), ("m60", 60)):
            if key not in reaction:
                px = connection.execute(
                    """SELECT last, as_of FROM ingest.intraday_snapshots
                       WHERE ticker=%s AND as_of >= %s ORDER BY as_of ASC LIMIT 1""",
                    (ev["subject"], (base_at or fs) + timedelta(minutes=minutes)),
                ).fetchone()
                if px and reaction.get("base"):
                    last = float(px["last"])
                    pc = reaction["base"].get("prev_close") or reaction["base"]["px"]
                    reaction[key] = {
                        "ret": last / reaction["base"]["px"] - 1,
                        "ret_vs_prev_close": last / pc - 1 if pc else None,
                        "at": str(px["as_of"]),
                    }
                else:
                    reaction[key] = None
        if "session_end" not in reaction and reaction.get("base") and now >= _session_end(fs):
            end_px = connection.execute(
                """SELECT last, as_of, session FROM ingest.intraday_snapshots
                   WHERE ticker=%s AND as_of <= %s ORDER BY as_of DESC LIMIT 1""",
                (ev["subject"], _session_end(fs)),
            ).fetchone()
            if end_px and reaction.get("base"):
                last = float(end_px["last"])
                pc = reaction["base"].get("prev_close") or reaction["base"]["px"]
                reaction["session_end"] = {
                    "ret": last / reaction["base"]["px"] - 1,
                    "ret_vs_prev_close": last / pc - 1 if pc else None,
                    "at": str(end_px["as_of"]),
                }
            else:
                reaction["session_end"] = None
        connection.execute(
            "UPDATE perception.news_events SET reaction=%s WHERE event_id=%s",
            (json.dumps(reaction), ev["event_id"]),
        )
        written += 1
    return written


def _session_end(fs):
    """Session end in ET: post->20:00, regular->16:00, pre->09:30 of the same day."""
    local = fs.astimezone(NY)
    if local.hour < 9 or (local.hour == 9 and local.minute < 30):
        h, m = 9, 30
    elif local.hour < 16:
        h, m = 16, 0
    else:
        h, m = 20, 0
    from datetime import datetime

    return datetime(local.year, local.month, local.day, h, m, tzinfo=NY).astimezone(fs.tzinfo)
