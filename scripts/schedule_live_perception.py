"""B-069: incremental news-event builder. Runs every 2 minutes via supervisor;
--replay START END rebuilds a date range. Perception DSN only; no LLM."""

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone

from inves_cog.perception.events.events import build_events

CURSOR = "live_perception_events"


def _scope(connection):
    pool = {
        r["ticker"]
        for r in connection.execute(
            "SELECT DISTINCT m->>'ticker' AS ticker FROM graph.baskets, jsonb_array_elements(members) m"
        ).fetchall()
    }
    held = {
        r["ticker"]
        for r in connection.execute(
            "SELECT jsonb_object_keys(coalesce(state->'positions','{}'::jsonb)) AS ticker"
            " FROM (SELECT state FROM trading.ledger WHERE portfolio_id='paper-fixed'"
            " ORDER BY observed_at DESC LIMIT 1) latest"
        ).fetchall()
    }
    from inves_cog.perception.core_companies import core_companies

    return set(pool) | set(held) | set(core_companies())


def _items(connection, since=None, start=None, end=None):
    sql = (
        "SELECT info_id, headline, tickers, kind, first_seen_at"
        " FROM ingest.info_items WHERE kind='news' AND first_seen_at IS NOT NULL"
    )
    args = ()
    if since is not None:
        sql += " AND first_seen_at > %s"
        args += (since,)
    elif start is not None:
        sql += " AND first_seen_at >= %s AND first_seen_at < %s + INTERVAL '2 days'"
        args += (start, end)
    sql += " ORDER BY first_seen_at"
    return connection.execute(sql, args).fetchall()


def _persist(connection, events):
    for ev in events:
        connection.execute(
            """INSERT INTO perception.news_events
               (event_id, subject, kind, et_date, session, first_seen_at, last_seen_at,
                info_ids, headline, facts, segment, importance, importance_parts, updated_at)
               VALUES (%(event_id)s,%(subject)s,%(kind)s,%(et_date)s,%(session)s,
                       %(first_seen_at)s,%(last_seen_at)s,%(info_ids)s,%(headline)s,
                       %(facts)s,%(segment)s,%(importance)s,%(importance_parts)s,now())
               ON CONFLICT (event_id) DO UPDATE SET
                first_seen_at=LEAST(perception.news_events.first_seen_at, EXCLUDED.first_seen_at),
                last_seen_at=GREATEST(perception.news_events.last_seen_at, EXCLUDED.last_seen_at),
                info_ids=(SELECT array_agg(DISTINCT x) FROM unnest(
                    perception.news_events.info_ids || EXCLUDED.info_ids) x),
                facts=perception.news_events.facts || COALESCE(EXCLUDED.facts,'{}'::jsonb),
                importance=GREATEST(perception.news_events.importance, EXCLUDED.importance),
                headline=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.headline ELSE perception.news_events.headline END,
                importance_parts=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.importance_parts ELSE perception.news_events.importance_parts END,
                segment=CASE WHEN EXCLUDED.importance >= perception.news_events.importance
                              THEN EXCLUDED.segment ELSE perception.news_events.segment END,
                updated_at=now()""",
            {
                **ev,
                "facts": json.dumps(ev["facts"], default=str),
                "importance_parts": json.dumps(ev["importance_parts"], default=str),
            },
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", nargs=2, metavar=("START", "END"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="compute in memory, print, no writes")
    args = ap.parse_args()
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment

    values = read_environment()
    connection = connect({**values, "INVES_COG_DATABASE_URL": values["INVES_COG_PERCEPTION_DATABASE_URL"]})
    scope = _scope(connection)
    now = datetime.now(timezone.utc)
    if args.replay:
        start, end = date.fromisoformat(args.replay[0]), date.fromisoformat(args.replay[1])
        items = _items(connection, start=start, end=end)
    else:
        row = connection.execute("SELECT value FROM perception.live_cursors WHERE cursor_key=%s", (CURSOR,)).fetchone()
        since = row["value"] if row else None
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=2)
        else:
            since = since - timedelta(minutes=10)  # overlap: upsert is idempotent
        items = _items(connection, since=since)
    events = build_events(items, scope, now)
    if args.dry_run:
        print(json.dumps(events, default=str, indent=1))
        return
    _run(connection, scope, items, events, args)


def _run(connection, scope, items, events, args):
    with connection.transaction():
        _persist(connection, events)
        latest = max((i["first_seen_at"] for i in items), default=None)
        if latest:
            connection.execute(
                "INSERT INTO perception.live_cursors (cursor_key,value,updated_at) VALUES (%s,%s,now())"
                " ON CONFLICT (cursor_key) DO UPDATE SET value=EXCLUDED.value,updated_at=now()",
                (CURSOR, latest),
            )
    print(f"events={len(events)} items={len(items)}")


if __name__ == "__main__":
    if "--once" in sys.argv or "--replay" in sys.argv or "--dry-run" in sys.argv:
        main()
    else:
        while True:
            try:
                main()
            except Exception as exc:  # keep the loop alive; report and retry
                print(f"pass failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(120)
