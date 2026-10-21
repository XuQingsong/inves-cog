"""Read-only M8 snapshot for M9. The caller supplies the connection."""

import json
from datetime import datetime

STAGES = ("attribution_candidates", "attribution_tracks", "attribution_labels")

_JOBS = """
SELECT id, task_name, trade_date, status, ended_at
FROM ingest.job_runs
WHERE trade_date = %s AND task_name = ANY(%s)
"""

_EVENTS = """
SELECT e.event_id, e.anomaly_id, e.lifecycle, e.history, e.mechanism, e.deadline_outcome, a.generated_at
FROM perception.linkage_events AS e
LEFT JOIN perception.anomalies AS a ON a.anomaly_id = e.anomaly_id
"""

_FIELD_GAPS = {
    "mechanism": "linkage_events.mechanism 只有当前值，历史里没有当时的机制",
    "deadline_outcome": "linkage_events.deadline_outcome 只有当前值，没有 cutoff 前的版本",
    "exposure": "perception.ticker_status 没有生成时间，不能证明当时的暴露",
    "affected": "perception.candidates.affected 会原地更新，没有生成时间",
    "direction": "联动事件表没有方向；异常表的涨跌方向不是这件事的方向",
    "divergence_tag": "perception.reports 是可变的当前结果，没有生成时间",
    "dimensions": "现有表没有五维状态的历史快照",
    "next_filing_at": "现有表没有下一份财报的生效时间",
}


def m8_provider(connection):
    """Return the (target, cutoff) reader. It only reads the supplied connection."""

    def read(target, cutoff):
        return read_snapshot(connection, target, cutoff)

    return read


def read_snapshot(connection, target, cutoff):
    """Jobs must have ended successfully by the cutoff. Event versions come from history."""
    connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
    try:
        return _snapshot(connection, target, cutoff)
    finally:
        connection.execute("ROLLBACK")


def _snapshot(connection, target, cutoff):
    day = str(target)[:10]
    jobs = connection.execute(_JOBS, (day, list(STAGES))).fetchall()
    chosen, stage_gaps = _stages(jobs, cutoff)
    events, unproven = _events(connection.execute(_EVENTS).fetchall(), cutoff)
    complete = not stage_gaps and not unproven and not events
    times = [_aware(_cell(row, "ended_at", 4)) for row in chosen.values()]
    if events:
        times.extend(_aware(row["observed_at"]) for row in events)
    visible = [item for item in times if item is not None and item <= cutoff]
    source = max(visible).isoformat() if complete or (not stage_gaps and visible) else None
    if stage_gaps:
        source = None
    return {
        "complete": complete,
        "source_events_asof": source,
        "events": events,
        "source_ids": {
            "jobs": [_job_id(chosen[name]) for name in STAGES if name in chosen],
            "events": [
                {
                    "event_id": row["event_id"],
                    "anomaly_id": row["anomaly_id"],
                    "evidence_ids": list(row["evidence_ids"]),
                }
                for row in events
            ],
        },
        "missing": {
            "stages": stage_gaps,
            "events": unproven,
            "fields": dict(_FIELD_GAPS) if events else {},
        },
    }


def _stages(rows, cutoff):
    chosen = {}
    for row in rows:
        name = _cell(row, "task_name", 1)
        if name not in STAGES:
            continue
        ended = _aware(_cell(row, "ended_at", 4))
        if ended is None or ended > cutoff:
            continue
        current = chosen.get(name)
        if current is None or ended >= current[0]:
            chosen[name] = (ended, row)
    gaps = []
    kept = {}
    for name in STAGES:
        found = chosen.get(name)
        if found is None:
            gaps.append(f"{name} 没有在 cutoff 前结束")
            continue
        row = found[1]
        kept[name] = row
        if _cell(row, "status", 3) != "ok":
            gaps.append(f"{name} 结束状态是 {_cell(row, 'status', 3)}")
    return kept, gaps


def _events(rows, cutoff):
    emitted = []
    unproven = []
    for row in rows:
        event_id = _cell(row, "event_id", 0)
        generated = _aware(_cell(row, "generated_at", 6))
        if generated is not None and generated > cutoff:
            continue
        version = _version(_history(_cell(row, "history", 3)), cutoff)
        if version is None:
            unproven.append(f"{event_id} 没有不晚于 cutoff 的历史时间")
            continue
        when, entry = version
        emitted.append(
            {
                "event_id": event_id,
                "anomaly_id": _cell(row, "anomaly_id", 1),
                "lifecycle": entry.get("new"),
                "observed_at": when.isoformat(),
                "evidence_ids": list(entry.get("evidence_ids") or []),
            }
        )
    return emitted, unproven


def _version(history, cutoff):
    chosen = None
    for entry in history:
        if not isinstance(entry, dict):
            continue
        when = _aware(entry.get("at"))
        if when is None or when > cutoff:
            continue
        if chosen is None or when >= chosen[0]:
            chosen = (when, entry)
    return chosen


def _history(value):
    if isinstance(value, str):
        value = json.loads(value)
    return list(value or [])


def _job_id(row):
    ended = _aware(_cell(row, "ended_at", 4))
    return {
        "id": _cell(row, "id", 0),
        "task_name": _cell(row, "task_name", 1),
        "status": _cell(row, "status", 3),
        "ended_at": ended.isoformat() if ended is not None else None,
    }


def _cell(row, name, index):
    if isinstance(row, dict):
        return row.get(name)
    return row[index]


def _aware(value):
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed
