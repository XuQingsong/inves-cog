"""B-069: incremental news-event builder. Runs every 2 minutes via supervisor;
--replay START END rebuilds a date range. Perception DSN only; no LLM."""

import argparse
import json
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
                facts=CASE WHEN EXCLUDED.importance > perception.news_events.importance
                      OR (EXCLUDED.importance = perception.news_events.importance
                          AND COALESCE(GREATEST(
                                  abs((EXCLUDED.facts->>'guide_gap_pct')::float),
                                  abs((EXCLUDED.facts->>'surprise_pct')::float),
                                  abs((EXCLUDED.facts->>'eps_gap_pct')::float),
                                  abs((EXCLUDED.facts->>'rev_gap_pct')::float)),0)
                          >= COALESCE(GREATEST(
                                  abs((perception.news_events.facts->>'guide_gap_pct')::float),
                                  abs((perception.news_events.facts->>'surprise_pct')::float),
                                  abs((perception.news_events.facts->>'eps_gap_pct')::float),
                                  abs((perception.news_events.facts->>'rev_gap_pct')::float)),0))
                    THEN perception.news_events.facts || COALESCE(EXCLUDED.facts,'{}'::jsonb)
                    ELSE COALESCE(EXCLUDED.facts,'{}'::jsonb) || perception.news_events.facts END,
                importance=GREATEST(perception.news_events.importance, EXCLUDED.importance),
                headline=CASE WHEN EXCLUDED.importance > perception.news_events.importance
                      OR (EXCLUDED.importance = perception.news_events.importance
                          AND COALESCE(GREATEST(
                                  abs((EXCLUDED.facts->>'guide_gap_pct')::float),
                                  abs((EXCLUDED.facts->>'surprise_pct')::float),
                                  abs((EXCLUDED.facts->>'eps_gap_pct')::float),
                                  abs((EXCLUDED.facts->>'rev_gap_pct')::float)),0)
                          >= COALESCE(GREATEST(
                                  abs((perception.news_events.facts->>'guide_gap_pct')::float),
                                  abs((perception.news_events.facts->>'surprise_pct')::float),
                                  abs((perception.news_events.facts->>'eps_gap_pct')::float),
                                  abs((perception.news_events.facts->>'rev_gap_pct')::float)),0))
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


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", nargs=2, metavar=("START", "END"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="compute in memory, print, no writes")
    return ap.parse_args()


def main(args):
    from inves_cog.ingest.cli import connect
    from inves_cog.ingest.settings import read_environment

    values = read_environment()
    with connect({**values, "INVES_COG_DATABASE_URL": values["INVES_COG_PERCEPTION_DATABASE_URL"]}) as connection:
        _pass(connection, args)


def _pass(connection, args):
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


def due(last_events, last_live, now):
    """Pure scheduling decision: events every 120 s, live every 300 s."""
    return now - last_events >= 120, now - last_live >= 300


if __name__ == "__main__":
    cli = parse_args()
    if cli.once or cli.replay or cli.dry_run:
        main(cli)
    else:
        from inves_cog.ingest.cli import connect
        from inves_cog.ingest.settings import read_environment
        from inves_cog.perception.live.run import live_pass

        last_events = 0.0
        last_live = 0.0
        while True:
            tick = time.time()
            run_events, run_live = due(last_events, last_live, tick)
            if run_events:
                last_events = tick
                try:
                    main(cli)
                except Exception as exc:
                    print(f"events pass failed: {type(exc).__name__}: {exc}", flush=True)
            if run_live:
                last_live = tick
                try:
                    from inves_cog.perception.earnings.cards import update_cards

                    values = read_environment()
                    with connect(
                        {**values, "INVES_COG_DATABASE_URL": values["INVES_COG_PERCEPTION_DATABASE_URL"]}
                    ) as connection:
                        print(live_pass(connection, datetime.now(timezone.utc)), flush=True)
                        from inves_cog.perception.core_companies import core_companies

                        cards = update_cards(connection, datetime.now(timezone.utc), core_companies())
                        print(f"earnings_cards={cards}", flush=True)
                except Exception as exc:
                    print(f"live pass failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(30)
