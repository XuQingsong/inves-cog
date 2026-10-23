"""Weekly and monthly review blocks. Numbers are copied from stored rows or counted from them."""

from datetime import datetime, timedelta

from psycopg.types.json import Jsonb

from inves_cog.perception.review.calendar import add_sessions, cutoff
from inves_cog.perception.review.samples import miss_report

MISSING = "数据暂缺"
WEEKLY_BLOCKS = (
    "漏检报告",
    "估值区间变化最大的10只",
    "待确认打标",
    "冷静期挡掉的买入此后表现",
    "估值仓位对照标黄持仓此后表现",
)
MONTHLY_BLOCKS = (
    "归因校准",
    "规则A与因子影子分歧",
    "影子信号如果当时这样做",
    "信源缺口排序",
    "原因未明占比趋势",
)
HORIZONS = (5, 21, 63)


def store_weekly(connection, week_ending, clock):
    payload = build_weekly(connection, week_ending, cutoff(week_ending))
    _store(connection, "perception.reports_weekly", "week:" + week_ending.isoformat(), week_ending, clock, payload)
    return payload


def store_monthly(connection, month_end, clock):
    payload = build_monthly(connection, month_end, cutoff(month_end))
    _store(connection, "perception.reports_monthly", "month:" + month_end.isoformat(), month_end, clock, payload)
    return payload


def build_weekly(connection, week_ending, visible):
    start = week_ending - timedelta(days=6)
    samples = _samples(connection, start, week_ending)
    forward = _shadow_rows(connection, start, week_ending, visible)
    return {
        "漏检报告": miss_report(samples),
        "估值区间变化最大的10只": _range_changes(connection, start, week_ending, visible),
        "待确认打标": _pending(connection, week_ending, visible),
        "冷静期挡掉的买入此后表现": _cooling(connection, start, week_ending, visible),
        "估值仓位对照标黄持仓此后表现": _yellow(connection, start, week_ending, visible),
        "后续收益": forward,
    }


def build_monthly(connection, month_end, visible):
    start = month_end.replace(day=1)
    samples = _samples(connection, start, month_end)
    signals, factors = _split_shadow(connection, start, month_end, visible)
    return {
        "归因校准": _calibration(connection, start, month_end, visible),
        "规则A与因子影子分歧": factors,
        "影子信号如果当时这样做": signals,
        "信源缺口排序": _gaps(samples),
        "原因未明占比趋势": _unknown_trend(connection, start, month_end, visible),
        "后续收益": signals + factors,
    }


def _store(connection, table, report_id, period_end, clock, payload):
    connection.execute(
        f"""
        INSERT INTO {table} (report_id, period_end, generated_at, payload)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (report_id) DO UPDATE
        SET generated_at = EXCLUDED.generated_at, payload = EXCLUDED.payload, period_end = EXCLUDED.period_end
        """,
        (report_id, period_end, clock.now_utc(), Jsonb(payload)),
    )


def _samples(connection, start, end):
    return list(
        connection.execute(
            """
            SELECT sample_id, item_ref, discovered, judgment, gap_ring, anomaly_id
            FROM perception.miss_samples
            WHERE period_end >= %s AND period_end <= %s
            ORDER BY sample_id
            """,
            (start, end),
        ).fetchall()
    )


def _pending(connection, week_ending, visible):
    rows = connection.execute(
        """
        SELECT case_id, as_of FROM perception.case_labels
        WHERE horizon = 'T+20' AND drafted IS TRUE AND confirmed_at IS NULL
          AND as_of <= %s AND written_at < %s
        ORDER BY case_id
        """,
        (week_ending, visible),
    ).fetchall()
    return [{"case_id": row["case_id"], "as_of": row["as_of"].isoformat()} for row in rows]


def _range_changes(connection, start, week_ending, visible):
    rows = connection.execute(
        """
        SELECT trade_date, ticker, neutral, payload->>'change_reason' AS change_reason
        FROM valuation_v1.ranges
        WHERE trade_date <= %s AND observed_at < %s AND neutral IS NOT NULL
        ORDER BY ticker, trade_date
        """,
        (week_ending, visible),
    ).fetchall()
    series = {}
    for row in rows:
        series.setdefault(row["ticker"], []).append(row)
    changes = []
    for ticker, items in series.items():
        latest = [item for item in items if item["trade_date"] >= start]
        if not latest:
            continue
        later = latest[-1]
        earlier_items = [item for item in items if item["trade_date"] < later["trade_date"]]
        if not earlier_items:
            continue
        earlier = earlier_items[-1]
        changes.append(
            {
                "ticker": ticker,
                "earlier": earlier["neutral"],
                "later": later["neutral"],
                "abs_change": abs(later["neutral"] - earlier["neutral"]),
                "reason": later["change_reason"] or MISSING,
            }
        )
    changes.sort(key=lambda item: (-item["abs_change"], item["ticker"]))
    return changes[:10]


def _cooling(connection, start, end, visible):
    rows = connection.execute(
        """
        SELECT trade_date, payload FROM trading.plan
        WHERE trade_date >= %s AND trade_date <= %s AND generated_at < %s
        """,
        (start, end, visible),
    ).fetchall()
    found, seen = [], set()
    for row in rows:
        payload = row["payload"] if isinstance(row["payload"], dict) else {}
        items = list(payload.get("skips") or []) + list(payload.get("cancels") or [])
        for item in items:
            if not isinstance(item, dict) or item.get("n_code") != "N5" or not isinstance(item.get("ticker"), str):
                continue
            key = (item["ticker"], row["trade_date"])
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "ticker": item["ticker"],
                    "trade_date": row["trade_date"].isoformat(),
                    "reason_zh": item.get("reason_zh"),
                    "horizons": _forward(_closes(connection, item["ticker"]), row["trade_date"], (5, 21)),
                }
            )
    return found


def _yellow(connection, start, end, visible):
    rows = connection.execute(
        """
        SELECT trade_date, ticker, payload FROM valuation_v1.position_panel
        WHERE trade_date >= %s AND trade_date <= %s AND observed_at < %s
        ORDER BY ticker
        """,
        (start, end, visible),
    ).fetchall()
    found = []
    for row in rows:
        payload = row["payload"] if isinstance(row["payload"], dict) else {}
        if payload.get("flag_yellow") is not True:
            continue
        found.append(
            {
                "ticker": row["ticker"],
                "trade_date": row["trade_date"].isoformat(),
                "horizons": _forward(_closes(connection, row["ticker"]), row["trade_date"], (5, 21)),
            }
        )
    return found


def _shadow_rows(connection, start, end, visible):
    signals, factors = _split_shadow(connection, start, end, visible)
    return signals + factors


def _split_shadow(connection, start, end, visible):
    signal_rows = connection.execute(
        """
        SELECT signal, ticker, date, shadow_action
        FROM perception_shadow.signals
        WHERE date >= %s AND date <= %s
        ORDER BY signal, ticker
        """,
        (start, end),
    ).fetchall()
    factor_rows = connection.execute(
        """
        SELECT ticker, date, factor_id, would_pass, rule_a_entry_pass
        FROM factor_shadow.daily
        WHERE date >= %s AND date <= %s AND generated_at < %s
          AND would_pass IS DISTINCT FROM rule_a_entry_pass
        ORDER BY ticker, factor_id
        """,
        (start, end, visible),
    ).fetchall()
    signals, factors = [], []
    for row in signal_rows:
        signals.append(
            {
                "kind": "signal",
                "signal": row["signal"],
                "ticker": row["ticker"],
                "shadow_action": row["shadow_action"],
                "horizons": _forward(_closes(connection, row["ticker"]), row["date"], HORIZONS),
            }
        )
    for row in factor_rows:
        factors.append(
            {
                "kind": "factor",
                "ticker": row["ticker"],
                "factor_id": row["factor_id"],
                "would_pass": row["would_pass"],
                "rule_a_entry_pass": row["rule_a_entry_pass"],
                "horizons": _forward(_closes(connection, row["ticker"]), row["date"], HORIZONS),
            }
        )
    return signals, factors


def _closes(connection, ticker):
    rows = connection.execute(
        "SELECT trade_date, close FROM ingest.bars_daily WHERE ticker = %s AND close IS NOT NULL",
        (ticker,),
    ).fetchall()
    return {row["trade_date"]: row["close"] for row in rows}


def _forward(closes, day, horizons):
    points = []
    for count in horizons:
        later = add_sessions(day, count)
        start = closes.get(day)
        end = closes.get(later)
        if start in (None, 0) or end is None:
            points.append({"horizon": count, "reason": MISSING})
        else:
            points.append({"horizon": count, "start_close": start, "end_close": end, "ret": end / start - 1})
    return points


def _calibration(connection, start, end, visible):
    candidates = connection.execute(
        """
        SELECT candidate.anomaly_id, candidate.confidence
        FROM perception.candidates AS candidate
        JOIN perception.anomalies AS anomaly ON anomaly.anomaly_id = candidate.anomaly_id
        WHERE anomaly.trade_date >= %s AND anomaly.trade_date <= %s
          AND (anomaly.generated_at IS NULL OR anomaly.generated_at < %s)
        """,
        (start, end, visible),
    ).fetchall()
    hits = {
        row["anomaly_id"]
        for row in connection.execute(
            """
            SELECT event.anomaly_id
            FROM perception.second_hits AS hit
            JOIN perception.linkage_events AS event ON event.event_id = hit.event_id
            WHERE hit.outcome = '确认' AND hit.published_at < %s
            """,
            (visible,),
        ).fetchall()
    }
    buckets = {}
    for row in candidates:
        slot = buckets.setdefault(row["confidence"] or "未标注", {"candidates": 0, "confirmed_hits": 0})
        slot["candidates"] += 1
        if row["anomaly_id"] in hits:
            slot["confirmed_hits"] += 1
    deadlines = connection.execute(
        """
        SELECT COALESCE(event.deadline_outcome, '未结') AS outcome, count(*) AS n
        FROM perception.linkage_events AS event
        JOIN perception.anomalies AS anomaly ON anomaly.anomaly_id = event.anomaly_id
        WHERE anomaly.trade_date >= %s AND anomaly.trade_date <= %s
          AND (anomaly.generated_at IS NULL OR anomaly.generated_at < %s)
        GROUP BY 1
        ORDER BY 1
        """,
        (start, end, visible),
    ).fetchall()
    return {
        "buckets": [{"confidence": key, **value} for key, value in sorted(buckets.items())],
        "deadline_outcomes": [{"outcome": row["outcome"], "count": int(row["n"])} for row in deadlines],
    }


def _gaps(samples):
    counts = {}
    for row in samples:
        if row["judgment"] == "应发现" and row["gap_ring"]:
            counts[row["gap_ring"]] = counts.get(row["gap_ring"], 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"ring": ring, "count": count} for ring, count in ordered]


def _unknown_trend(connection, start, end, visible):
    anomalies = connection.execute(
        """
        SELECT anomaly_id, trade_date FROM perception.anomalies
        WHERE trade_date >= %s AND trade_date <= %s
          AND (generated_at IS NULL OR generated_at < %s)
        ORDER BY trade_date, anomaly_id
        """,
        (start, end, visible),
    ).fetchall()
    ids = [row["anomaly_id"] for row in anomalies] or [""]
    events = connection.execute(
        "SELECT anomaly_id, history FROM perception.linkage_events WHERE anomaly_id = ANY(%s)",
        (ids,),
    ).fetchall()
    known = {row["anomaly_id"] for row in events if _known(row["history"], visible)}
    by_day = {}
    for row in anomalies:
        slot = by_day.setdefault(row["trade_date"], {"unknown": 0, "total": 0})
        slot["total"] += 1
        if row["anomaly_id"] not in known:
            slot["unknown"] += 1
    return [
        {"trade_date": day.isoformat(), "unknown": slot["unknown"], "total": slot["total"]}
        for day, slot in sorted(by_day.items())
    ]


def _known(history, visible):
    latest = None
    seen = False
    for item in history or []:
        if not isinstance(item, dict):
            continue
        moment = _stamp(item.get("at"))
        if moment is not None and moment < visible:
            seen = True
            latest = item.get("new")
    return seen and latest not in (None, "已发现")


def _stamp(value):
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else None
