"""Independent miss frame. Discovery flags are stored and never used to draw the sample."""

import random
from datetime import timedelta

from inves_cog.perception.review.calendar import cutoff
from inves_cog.perception.review.snapshots import pool_tickers

WEEKLY_DRAW = 20
MONTHLY_DRAW = 10
# Same entry line as the move board: a price move below it did not clear that bar.
MOVE_LINE = 0.07
JUDGMENTS = ("应发现", "不应发现", "未知", "数据不覆盖")


def sample_weekly(connection, period_end):
    visible = cutoff(period_end)
    start = visible - timedelta(days=7)
    rows = connection.execute(
        """
        SELECT info_id,
               COALESCE((payload->>'system_found')::boolean, false) AS discovered,
               NULLIF(payload->>'anomaly_id', '') AS anomaly_id
        FROM ingest.info_items
        WHERE first_seen_at >= %s AND first_seen_at < %s
          AND NOT ('attention' = ANY(flags))
        ORDER BY info_id
        """,
        (start, visible),
    ).fetchall()
    return _store(connection, "weekly_info", period_end, rows, "info_id", WEEKLY_DRAW)


def sample_monthly(connection, month_end):
    start = month_end.replace(day=1)
    moves = connection.execute(
        """
        SELECT ticker, trade_date, ret
        FROM marketstate.daily
        WHERE trade_date >= %s AND trade_date <= %s AND session = 'close'
          AND ret IS NOT NULL AND abs(ret) > 0 AND abs(ret) < %s
        ORDER BY ticker, trade_date
        """,
        (start, month_end, MOVE_LINE),
    ).fetchall()
    move_rows = []
    for row in moves:
        ref = row["ticker"] + ":" + row["trade_date"].isoformat()
        move_rows.append(
            {
                "info_id": ref,
                "discovered": _move_discovered(connection, row["ticker"], row["trade_date"]),
                "anomaly_id": None,
            }
        )
    companies = _company_rows(connection, month_end)
    return {
        "moves": _store(connection, "monthly_move", month_end, move_rows, "info_id", MONTHLY_DRAW),
        "companies": _store(connection, "monthly_company", month_end, companies, "info_id", MONTHLY_DRAW),
    }


def record_judgment(connection, sample_id, judgment, clock, gap_ring=None, anomaly_id=None):
    if judgment not in JUDGMENTS:
        raise ValueError("未知判定")
    updated = connection.execute(
        """
        UPDATE perception.miss_samples
        SET judgment = %s, gap_ring = %s, judged_at = %s, anomaly_id = COALESCE(%s, anomaly_id)
        WHERE sample_id = %s
        RETURNING sample_id
        """,
        (judgment, gap_ring, clock.now_utc(), anomaly_id, sample_id),
    ).fetchone()
    if updated is None:
        raise ValueError("样本不存在")
    return sample_id


def miss_report(rows):
    unknown = sum(row["judgment"] == "未知" for row in rows)
    uncovered = sum(row["judgment"] == "数据不覆盖" for row in rows)
    should = [row for row in rows if row["judgment"] == "应发现"]
    hits = [row for row in should if row["discovered"]]
    predicted = [row for row in rows if row["discovered"] and row["judgment"] in ("应发现", "不应发现")]
    correct = [row for row in predicted if row["judgment"] == "应发现"]
    return {
        "detection_rate": None if not should else len(hits) / len(should),
        "detection_denominator": len(should),
        "precision": None if not predicted else len(correct) / len(predicted),
        "unknown_count": unknown,
        "uncovered_count": uncovered,
    }


def choose_ids(ids, count, seed):
    ordered = sorted(set(ids))
    if len(ordered) <= count:
        return ordered
    return sorted(random.Random(seed).sample(ordered, count))


def _store(connection, frame, period_end, rows, key, count):
    picked = choose_ids([row[key] for row in rows], count, frame + ":" + period_end.isoformat())
    by_ref = {row[key]: row for row in rows}
    connection.execute(
        """
        DELETE FROM perception.miss_samples
        WHERE frame = %s AND period_end = %s AND judgment IS NULL AND NOT (item_ref = ANY(%s))
        """,
        (frame, period_end, picked or [""]),
    )
    stored = []
    for ref in picked:
        row = by_ref[ref]
        sample_id = frame + ":" + period_end.isoformat() + ":" + ref
        connection.execute(
            """
            INSERT INTO perception.miss_samples (
                sample_id, frame, period_end, item_ref, discovered, anomaly_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (frame, period_end, item_ref) DO UPDATE
            SET discovered = EXCLUDED.discovered
            WHERE perception.miss_samples.judgment IS NULL
            """,
            (sample_id, frame, period_end, ref, bool(row["discovered"]), row.get("anomaly_id")),
        )
        stored.append({"sample_id": sample_id, "item_ref": ref, "discovered": bool(row["discovered"])})
    return stored


def _move_discovered(connection, ticker, day):
    rows = connection.execute(
        """
        SELECT members FROM perception.anomalies
        WHERE trade_date = %s AND (generated_at IS NULL OR generated_at < %s)
        """,
        (day, cutoff(day)),
    ).fetchall()
    for row in rows:
        if ticker in _names(row["members"]):
            return True
    return False


def _company_rows(connection, month_end):
    pool = set(pool_tickers())
    rows = connection.execute(
        """
        SELECT ticker FROM ingest.wide_universe
        WHERE trade_date = %s AND included AND exclude_reason IS DISTINCT FROM 'non_common'
        ORDER BY ticker
        """,
        (month_end,),
    ).fetchall()
    found = _month_members(connection, month_end)
    return [
        {"info_id": row["ticker"], "discovered": row["ticker"] in found, "anomaly_id": None}
        for row in rows
        if row["ticker"] not in pool
    ]


def _month_members(connection, month_end):
    start = month_end.replace(day=1)
    rows = connection.execute(
        """
        SELECT members FROM perception.anomalies
        WHERE trade_date >= %s AND trade_date <= %s
          AND (generated_at IS NULL OR generated_at < %s)
        """,
        (start, month_end, cutoff(month_end)),
    ).fetchall()
    names = set()
    for row in rows:
        names.update(_names(row["members"]))
    return names


def _names(members):
    if isinstance(members, dict):
        return {key for key in members if isinstance(key, str)}
    names = set()
    for item in members or []:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict) and isinstance(item.get("ticker"), str):
            names.add(item["ticker"])
    return names
