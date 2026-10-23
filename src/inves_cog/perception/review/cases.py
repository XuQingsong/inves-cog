"""One case per pool anomaly, with an independent label on T+1, T+5 and T+20."""

from psycopg.types.json import Jsonb

from inves_cog.ingest.market import regular_bounds
from inves_cog.perception.review.calendar import HORIZONS, add_sessions, cutoff

MISSING_PRICE = "T+5 缺少行情"


def member_tickers(members):
    if isinstance(members, dict):
        return [key for key in members if isinstance(key, str)]
    names = []
    for item in members or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and isinstance(item.get("ticker"), str):
            names.append(item["ticker"])
    return names


def run_labels(connection, as_of, clock):
    """Create due cases and labels. A horizon uses only rows visible on that horizon day."""
    visible = cutoff(as_of)
    created = _ensure_cases(connection, as_of, visible, clock)
    written = 0
    for case in _cases(connection, as_of):
        for horizon, offset in HORIZONS:
            due = add_sessions(case["trade_date"], offset)
            if as_of < due or _label_exists(connection, case["case_id"], horizon):
                continue
            _write_label(connection, case, horizon, due, clock)
            written += 1
        _refresh_case(connection, case["case_id"], clock)
    return created + written


def _cases(connection, as_of):
    return list(
        connection.execute(
            """
            SELECT case_id, anomaly_id, trade_date
            FROM perception.cases
            WHERE trade_date <= %s
            ORDER BY case_id
            """,
            (as_of,),
        ).fetchall()
    )


def _ensure_cases(connection, as_of, visible, clock):
    rows = connection.execute(
        """
        SELECT anomaly_id, trade_date
        FROM perception.anomalies
        WHERE universe = 'pool' AND trade_date <= %s
          AND (generated_at IS NULL OR generated_at < %s)
        ORDER BY anomaly_id
        """,
        (as_of, visible),
    ).fetchall()
    count = 0
    now = clock.now_utc()
    for row in rows:
        inserted = connection.execute(
            """
            INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, reason, updated_at)
            VALUES (%s, %s, %s, '未完成', %s, %s)
            ON CONFLICT (anomaly_id) DO NOTHING
            RETURNING case_id
            """,
            (row["anomaly_id"], row["anomaly_id"], row["trade_date"], "缺少 T+1、T+5、T+20", now),
        ).fetchone()
        if inserted:
            count += 1
    return count


def _label_exists(connection, case_id, horizon):
    return (
        connection.execute(
            "SELECT 1 FROM perception.case_labels WHERE case_id = %s AND horizon = %s",
            (case_id, horizon),
        ).fetchone()
        is not None
    )


def _write_label(connection, case, horizon, due, clock):
    visible = cutoff(due)
    labels, reason = _label_body(connection, case, horizon, due, visible)
    connection.execute(
        """
        INSERT INTO perception.case_labels (
            case_id, horizon, as_of, drafted, confirmed_at, labels, reason, visible_until, written_at
        ) VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s)
        """,
        (
            case["case_id"],
            horizon,
            due,
            horizon == "T+20",
            Jsonb(labels),
            reason,
            visible,
            clock.now_utc(),
        ),
    )


def _label_body(connection, case, horizon, due, visible):
    hits = _visible_hits(connection, case["anomaly_id"], visible)
    confirmed = [row["info_id"] for row in hits if row["outcome"] == "确认"]
    denied = [row["info_id"] for row in hits if row["outcome"] == "否定"]
    if confirmed:
        market = "确认"
    elif denied:
        market = "否定"
    else:
        market = "未检验"
    body = {
        "消息内容": "仍未知",
        "市场连接": market,
        "经营连接": "尚未到期",
        "可见二次命中": [row["info_id"] for row in hits],
    }
    reason = None
    if horizon == "T+5":
        reason = _price_gap(connection, case["anomaly_id"], due, visible)
    return body, reason


def _visible_hits(connection, anomaly_id, visible):
    return list(
        connection.execute(
            """
            SELECT hit.info_id, hit.outcome
            FROM perception.second_hits AS hit
            JOIN perception.linkage_events AS event ON event.event_id = hit.event_id
            WHERE event.anomaly_id = %s AND hit.published_at < %s
            ORDER BY hit.info_id
            """,
            (anomaly_id, visible),
        ).fetchall()
    )


def _price_gap(connection, anomaly_id, due, visible):
    members = connection.execute(
        "SELECT members FROM perception.anomalies WHERE anomaly_id = %s",
        (anomaly_id,),
    ).fetchone()
    names = member_tickers(members["members"] if members else None)
    if not names:
        return MISSING_PRICE + "：无成员"
    bounds = regular_bounds(due)
    if bounds is None or bounds[1] >= visible:
        return MISSING_PRICE + " " + "、".join(names)
    found = {
        row["ticker"]
        for row in connection.execute(
            "SELECT ticker FROM ingest.bars_daily WHERE ticker = ANY(%s) AND trade_date = %s",
            (names, due),
        ).fetchall()
    }
    missing = [name for name in names if name not in found]
    if missing:
        return MISSING_PRICE + " " + "、".join(missing)
    return None


def _refresh_case(connection, case_id, clock):
    rows = list(
        connection.execute(
            "SELECT horizon, reason FROM perception.case_labels WHERE case_id = %s",
            (case_id,),
        ).fetchall()
    )
    present = {row["horizon"] for row in rows}
    missing = [name for name, _ in HORIZONS if name not in present]
    gaps = [row["reason"] for row in rows if row["reason"]]
    if missing:
        status, reason = "未完成", "缺少 " + "、".join(missing)
    elif gaps:
        status, reason = "未完成", gaps[0]
    else:
        status, reason = "已完成", None
    connection.execute(
        "UPDATE perception.cases SET status = %s, reason = %s, updated_at = %s WHERE case_id = %s",
        (status, reason, clock.now_utc(), case_id),
    )
