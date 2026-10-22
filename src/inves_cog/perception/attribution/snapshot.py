"""Append-only M8 snapshot for M9. The caller supplies the connection.

A snapshot is written only after the three attribution stages have ended
successfully. At that capture, a current value is kept and stamped with the
injected clock. A field with no value stays null and does not clear the
others. Historical backfill still requires each field's original time. The
reader returns the newest complete snapshot already generated at the cutoff.
A degraded row stays incomplete.
"""

import json
from datetime import datetime

from psycopg.types.json import Jsonb

STAGES = ("attribution_candidates", "attribution_tracks", "attribution_labels")
_REQUIRED = (
    "lifecycle",
    "mechanism",
    "ticker",
    "exposure",
    "direction",
    "divergence_tag",
    "dimensions",
    "next_filing_at",
    "systemic_tag",
    "deadline_outcome",
)
_DB_REASONS = {
    "lifecycle": "没有不晚于 cutoff 的历史时间",
    "mechanism": "linkage_events.mechanism 只有当前值，历史里没有当时的机制",
    "ticker": "perception.ticker_status 没有生成时间，不能证明当时的标的",
    "exposure": "perception.ticker_status 没有生成时间，不能证明当时的暴露",
    "direction": "联动事件表没有方向；异常表的涨跌方向不是这件事的方向",
    "divergence_tag": "perception.reports 是可变的当前结果，没有生成时间",
    "dimensions": "现有表没有五维状态的历史快照",
    "next_filing_at": "现有表没有下一份财报的生效时间",
    "systemic_tag": "perception.market_day 没有生成时间，不能证明当时的系统性标记",
    "deadline_outcome": "linkage_events.deadline_outcome 只有当前值，没有 cutoff 前的版本",
}

_JOBS = """
SELECT id, task_name, trade_date, status, ended_at
FROM ingest.job_runs
WHERE trade_date = %s AND task_name = ANY(%s)
"""

_EVENTS = """
SELECT e.event_id, e.anomaly_id, e.history, a.generated_at, e.mechanism, e.deadline_outcome,
       tickers.rows AS tickers, candidates.rows AS candidates, tracks.rows AS tracks,
       claims.rows AS claims, r.report, m.systemic_event_tag
FROM perception.linkage_events AS e
LEFT JOIN perception.anomalies AS a ON a.anomaly_id = e.anomaly_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object('ticker', ticker, 'exposure', exposure, 'mechanism', mechanism)) AS rows
    FROM perception.ticker_status
    WHERE anomaly_id = e.anomaly_id
) AS tickers ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object('mechanism', mechanism, 'affected', affected)) AS rows
    FROM perception.candidates
    WHERE anomaly_id = e.anomaly_id
) AS candidates ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'trade_date', trade_date, 'emotion', emotion, 'capital', capital, 'fundamental', fundamental
    )) AS rows
    FROM perception.tracks
    WHERE event_id = e.event_id
) AS tracks ON true
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object('direction', direction)) AS rows
    FROM perception.claims
    WHERE info_id IN (
        SELECT unnest(info_ids) FROM perception.candidates WHERE anomaly_id = e.anomaly_id
    )
) AS claims ON true
LEFT JOIN perception.reports AS r ON r.anomaly_id = e.anomaly_id
LEFT JOIN perception.market_day AS m ON m.trade_date = %s
"""

_INSERT = """
INSERT INTO perception.m9_input_snapshots (
    trade_date, snapshot_generated_at, source_asof, status, kind, jobs, events, missing
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
RETURNING snapshot_id
"""

_SNAPSHOTS = """
SELECT snapshot_id, trade_date, snapshot_generated_at, source_asof, status, kind, jobs, events, missing
FROM perception.m9_input_snapshots
WHERE trade_date = %s AND snapshot_generated_at <= %s AND source_asof <= %s
ORDER BY snapshot_generated_at DESC, snapshot_id DESC
"""


def m8_provider(connection):
    """Return the (target, cutoff) reader. It only reads the supplied connection."""

    def read(target, cutoff):
        return read_snapshot(connection, target, cutoff)

    return read


def read_snapshot(connection, target, cutoff):
    """Newest complete snapshot with snapshot_generated_at and source_asof at or before cutoff."""
    connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
    try:
        return _snapshot(connection, target, cutoff)
    finally:
        connection.execute("ROLLBACK")


def capture_if_ready(connection, trade_date, clock, *, events=None):
    """Append one stage snapshot when all three jobs ended successfully by the clock."""
    now = _require_now(clock)
    chosen, gaps = _ready_stages(connection, trade_date, now)
    if gaps:
        return None
    source_asof = max(_aware(_cell(row, "ended_at", 4)) for row in chosen.values())
    built, missing = _bundle(connection, events, now, trade_date)
    return _insert(connection, trade_date, now, source_asof, "complete", "stage_completion", chosen, built, missing)


def capture_backfill(connection, trade_date, clock, events):
    """Append a backfill only when original field times prove what was visible."""
    now = _require_now(clock)
    built, missing = _from_supplied(events or [], now)
    times = _proven_times(built)
    if not times or max(times) > now:
        return None
    chosen, _gaps = _ready_stages(connection, trade_date, now)
    status = "complete" if _bundle_complete(missing) else "degraded"
    return _insert(connection, trade_date, now, max(times), status, "historical_backfill", chosen, built, missing)


def _snapshot(connection, target, cutoff):
    moment = _aware(cutoff)
    if moment is None:
        return _gap(None)
    rows = connection.execute(_SNAPSHOTS, (str(target)[:10], moment, moment)).fetchall()
    visible = [item for item in (_stored(row) for row in rows) if _visible(item, moment)]
    visible.sort(key=lambda item: (item["snapshot_generated_at"], item["snapshot_id"]), reverse=True)
    complete = next((item for item in visible if _usable(item, moment)), None)
    if complete is not None:
        return _from_complete(complete, moment)
    degraded = next((item for item in visible if item["status"] == "degraded"), None)
    return _gap(degraded)


def _ready_stages(connection, trade_date, now):
    rows = connection.execute(_JOBS, (str(trade_date)[:10], list(STAGES))).fetchall()
    return _stages(rows, now)


def _bundle(connection, events, now, trade_date):
    if events is None:
        day = str(trade_date)[:10]
        rows = connection.execute(_EVENTS, (day,)).fetchall()
        return _from_rows(rows, now, day)
    return _from_supplied(events, now)


def _from_rows(rows, now, day):
    built = []
    unproven = []
    fields = {}
    for row in rows:
        event, reason = _row_event(row, now, day)
        if reason:
            unproven.append(reason)
            continue
        if event is None:
            continue
        built.append(event)
        gaps = _gaps(event)
        if gaps:
            fields[event["event_id"]] = gaps
    return built, {"stages": [], "events": unproven, "fields": fields}


def _row_event(row, now, day):
    event_id = _cell(row, "event_id", 0)
    generated = _aware(_cell(row, "generated_at", 3))
    if generated is not None and generated > now:
        return None, None
    version = _version(_history(_cell(row, "history", 2)), now)
    if version is None:
        when, entry = None, {}
        lifecycle = _empty("lifecycle")
    else:
        when, entry = version
        lifecycle = _lifecycle(entry, when)
    divergence = _report_value(row, "divergence_label", "divergence_tag")
    filing = _report_value(row, "next_filing_at")
    members, member_gaps = _members(row, divergence, filing)
    ticker, exposure = _event_targets(members)
    fields = {
        "lifecycle": lifecycle,
        "mechanism": _observed(_mechanism(row), now, _DB_REASONS["mechanism"]),
        "ticker": _observed(ticker, now, _DB_REASONS["ticker"]),
        "exposure": _observed(exposure, now, _DB_REASONS["exposure"]),
        "direction": _direction_field(row, now),
        "divergence_tag": _observed(divergence, now, _DB_REASONS["divergence_tag"]),
        "dimensions": _observed(_dimensions(row, day), now, _DB_REASONS["dimensions"]),
        "next_filing_at": _observed(filing, now, _DB_REASONS["next_filing_at"]),
        "systemic_tag": _observed(_cell(row, "systemic_event_tag", 11), now, _DB_REASONS["systemic_tag"]),
        "deadline_outcome": _observed(_deadline(row), now, _DB_REASONS["deadline_outcome"]),
    }
    observed = when.isoformat() if when is not None else None
    event = _event_row(event_id, _cell(row, "anomaly_id", 1), observed, entry.get("evidence_ids"), fields)
    event["members"] = [item for item in members if item["exposure"] not in (None, "")]
    event["member_gaps"] = member_gaps
    return event, None


def _from_supplied(events, now):
    built = []
    fields = {}
    for raw in events:
        event = _supplied_event(raw, now)
        if event is None:
            continue
        built.append(event)
        gaps = _gaps(event)
        if gaps:
            fields[event["event_id"]] = gaps
    return built, {"stages": [], "events": [], "fields": fields}


def _supplied_event(raw, now):
    if not isinstance(raw, dict) or not raw.get("event_id"):
        return None
    fields = {}
    for name in _REQUIRED:
        fields[name] = _accept(raw, name, now)
    observed = fields["lifecycle"]["at"]
    if observed is None:
        times = [item for item in (_aware(fields[name]["at"]) for name in _REQUIRED) if item is not None]
        observed = max(times).isoformat() if times else None
    return _event_row(raw.get("event_id"), raw.get("anomaly_id"), observed, raw.get("evidence_ids"), fields)


def _accept(raw, name, now):
    cell = raw.get(name)
    value = cell.get("value") if isinstance(cell, dict) else None
    at = _aware(cell.get("at")) if isinstance(cell, dict) else None
    if value is not None and at is not None and at <= now:
        return {"value": _plain(value), "at": at.isoformat(), "missing_reason": None}
    reason = _DB_REASONS[name]
    if at is not None and at > now:
        reason = "来源时间晚于 cutoff"
    elif value is not None and at is None:
        reason = "没有来源时间"
    return {"value": None, "at": None, "missing_reason": reason}


def _event_row(event_id, anomaly_id, observed_at, evidence_ids, fields):
    return {
        "event_id": event_id,
        "anomaly_id": anomaly_id,
        "observed_at": observed_at,
        "evidence_ids": list(evidence_ids or []),
        "fields": fields,
    }


def _empty(name):
    return {"value": None, "at": None, "missing_reason": _DB_REASONS[name]}


def _observed(value, now, reason):
    if value is None or value == "" or value == [] or value == {}:
        return {"value": None, "at": None, "missing_reason": reason}
    return {"value": _plain(value), "at": now.isoformat(), "missing_reason": None}


def _lifecycle(entry, when):
    if entry.get("new") is None:
        return _empty("lifecycle")
    return {"value": entry.get("new"), "at": when.isoformat(), "missing_reason": None}


def _mechanism(row):
    direct = _cell(row, "mechanism", 4)
    if direct:
        return direct
    tickers = _distinct(item.get("mechanism") for item in _dicts(row, "tickers", 6))
    if len(tickers) == 1:
        return tickers[0]
    candidates = _distinct(item.get("mechanism") for item in _dicts(row, "candidates", 7))
    if len(candidates) == 1:
        return candidates[0]
    return None


def _direction_field(row, now):
    found = _distinct(item.get("direction") for item in _dicts(row, "claims", 9))
    if len(found) == 1:
        return _observed(found[0], now, _DB_REASONS["direction"])
    if len(found) > 1:
        return {"value": None, "at": None, "missing_reason": "多条说法的方向不一致"}
    return _empty("direction")


def _members(row, divergence, filing):
    grouped = {}
    order = []

    def add(ticker, exposure, extra):
        if not isinstance(ticker, str) or not ticker:
            return
        slot = grouped.get(ticker)
        if slot is None:
            slot = {"exposures": [], "divergence": [], "filing": []}
            grouped[ticker] = slot
            order.append(ticker)
        if exposure not in (None, ""):
            slot["exposures"].append(exposure)
        if isinstance(extra, dict) and extra.get("divergence_tag") not in (None, ""):
            slot["divergence"].append(extra.get("divergence_tag"))
        if isinstance(extra, dict) and extra.get("next_filing_at") not in (None, ""):
            slot["filing"].append(extra.get("next_filing_at"))

    for item in _dicts(row, "tickers", 6):
        add(item.get("ticker"), item.get("exposure"), item)
    named = set(grouped)
    for candidate in _dicts(row, "candidates", 7):
        for item in candidate.get("affected") or []:
            if not isinstance(item, dict):
                continue
            if named and item.get("ticker") not in named:
                continue
            add(item.get("ticker"), item.get("exposure"), item)
    members = []
    gaps = {}
    for ticker in order:
        slot = grouped[ticker]
        exposures = _distinct(slot["exposures"])
        if len(exposures) > 1:
            exposure = None
            gaps[f"{ticker}.exposure"] = "同一标的的暴露不一致"
        elif len(exposures) == 1:
            exposure = exposures[0]
        else:
            exposure = None
            gaps[f"{ticker}.exposure"] = _DB_REASONS["exposure"]
        tag, tag_reason = _own_or_shared(slot["divergence"], divergence, "同一标的的背离标签不一致")
        when, when_reason = _own_or_shared(slot["filing"], filing, "同一标的的下一份财报时间不一致")
        if tag_reason:
            gaps[f"{ticker}.divergence_tag"] = tag_reason
        if when_reason:
            gaps[f"{ticker}.next_filing_at"] = when_reason
        members.append({"ticker": ticker, "exposure": exposure, "divergence_tag": tag, "next_filing_at": when})
    return members, gaps


def _own_or_shared(own, shared, conflict):
    found = _distinct(own)
    if len(found) > 1:
        return None, conflict
    if len(found) == 1 and shared not in (None, "", found[0]):
        return None, conflict
    if len(found) == 1:
        return found[0], None
    return shared, None


def _event_targets(members):
    if not members:
        return None, None
    names = [item["ticker"] for item in members]
    exposures = [item["exposure"] for item in members]
    ticker = names[0] if len(names) == 1 else names
    exposure = exposures[0] if len(exposures) == 1 and exposures[0] else None
    if len(exposures) > 1 and all(exposures):
        exposure = exposures
    return ticker, exposure


def _dimensions(row, day):
    matched = []
    for item in _dicts(row, "tracks", 8):
        if str(item.get("trade_date"))[:10] != day:
            continue
        value = {key: item.get(key) for key in ("emotion", "capital", "fundamental") if item.get(key) is not None}
        if value:
            matched.append(value)
    if len(matched) == 1:
        return matched[0]
    return None


def _deadline(row):
    direct = _cell(row, "deadline_outcome", 5)
    if direct:
        return direct
    return _report(row).get("deadline_outcome")


def _report_value(row, *names):
    report = _report(row)
    for name in names:
        value = report.get(name)
        if value is not None and value != "":
            return value
    return None


def _report(row):
    value = _loads(_cell(row, "report", 10))
    return value if isinstance(value, dict) else {}


def _dicts(row, name, index):
    return [item for item in _list(_cell(row, name, index)) if isinstance(item, dict)]


def _list(value):
    loaded = _loads(value)
    return list(loaded or [])


def _distinct(values):
    found = []
    for value in values:
        if value is None or value == "" or value in found:
            continue
        found.append(value)
    return found


def _gaps(event):
    found = {}
    for name in _REQUIRED:
        cell = event["fields"][name]
        if cell["value"] is None or cell["at"] is None:
            found[name] = cell["missing_reason"]
    for key, reason in (event.get("member_gaps") or {}).items():
        found[key] = reason
    return found


def _bundle_complete(missing):
    return not missing["events"] and not missing["fields"]


def _proven_times(events):
    times = []
    for event in events:
        for name in _REQUIRED:
            cell = event["fields"][name]
            at = _aware(cell["at"])
            if cell["value"] is not None and at is not None:
                times.append(at)
    return times


def _insert(connection, trade_date, generated, source_asof, status, kind, chosen, events, missing):
    jobs = [_job_id(chosen[name]) for name in STAGES if name in chosen]
    inserted = connection.execute(
        _INSERT,
        (str(trade_date)[:10], generated, source_asof, status, kind, _json(jobs), _json(events), _json(missing)),
    ).fetchone()
    if inserted is None:
        raise RuntimeError("snapshot insert did not return an id")
    return inserted["snapshot_id"] if isinstance(inserted, dict) else inserted[0]


def _json(value):
    return Jsonb(value, dumps=lambda item: json.dumps(item, default=_dump, ensure_ascii=False))


def _dump(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _plain(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _require_now(clock):
    if clock is None or not hasattr(clock, "now_utc"):
        raise ValueError("snapshot requires an injected clock")
    now = clock.now_utc()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("snapshot clock must be timezone-aware")
    return now


def _stored(row):
    return {
        "snapshot_id": _cell(row, "snapshot_id", 0) or 0,
        "snapshot_generated_at": _aware(_cell(row, "snapshot_generated_at", 2)),
        "source_asof": _aware(_cell(row, "source_asof", 3)),
        "status": _cell(row, "status", 4),
        "jobs": _loads(_cell(row, "jobs", 6)) or [],
        "events": _loads(_cell(row, "events", 7)) or [],
        "missing": _loads(_cell(row, "missing", 8)) or {},
    }


def _visible(item, cutoff):
    generated = item["snapshot_generated_at"]
    source = item["source_asof"]
    return generated is not None and generated <= cutoff and source is not None and source <= cutoff


def _usable(item, cutoff):
    return item["status"] == "complete" and _visible(item, cutoff)


def _from_complete(item, cutoff):
    events = []
    missing = _returned_missing(item.get("missing"))
    for event in item["events"]:
        observed = _aware(event.get("observed_at"))
        if observed is not None and observed > cutoff:
            continue
        flat, late = _flatten(event, cutoff)
        events.append(flat)
        if late:
            bucket = dict(missing["fields"].get(event.get("event_id")) or {})
            bucket.update(late)
            missing["fields"][event.get("event_id")] = bucket
    return {
        "complete": True,
        "source_events_asof": item["source_asof"].isoformat(),
        "events": events,
        "source_ids": {
            "jobs": list(item["jobs"]),
            "events": [_source_event(event) for event in item["events"] if _kept_event(event, cutoff)],
        },
        "missing": missing,
    }


def _kept_event(event, cutoff):
    observed = _aware(event.get("observed_at"))
    return observed is None or observed <= cutoff


def _returned_missing(stored):
    data = stored if isinstance(stored, dict) else {}
    fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    copied = {}
    for key, value in fields.items():
        copied[key] = dict(value) if isinstance(value, dict) else value
    return {
        "stages": list(data.get("stages") or []),
        "events": list(data.get("events") or []),
        "fields": copied,
    }


def _gap(degraded):
    missing = {"stages": ["没有不晚于 cutoff 的完整快照"], "events": [], "fields": {}}
    source_ids = {"jobs": [], "events": []}
    if degraded is not None:
        stored = degraded["missing"] if isinstance(degraded["missing"], dict) else {}
        missing["events"] = list(stored.get("events") or [])
        missing["fields"] = dict(stored.get("fields") or {})
        source_ids = {
            "jobs": list(degraded["jobs"] or []),
            "events": [_source_event(event) for event in degraded["events"] or []],
        }
        kept = [_flatten(event)[0] for event in degraded["events"] or []]
    else:
        kept = []
    return {
        "complete": False,
        "source_events_asof": None,
        "events": kept,
        "source_ids": source_ids,
        "missing": missing,
    }


def _flatten(event, cutoff=None):
    fields = event.get("fields") or {}
    late = {}

    def value(name):
        cell = fields.get(name) or {}
        shown = cell.get("value")
        at = _aware(cell.get("at")) if isinstance(cell, dict) else None
        if cutoff is not None and at is not None and at > cutoff:
            late[name] = "来源时间晚于 cutoff"
            return None
        return shown

    shown_ticker = value("ticker")
    shown_exposure = value("exposure")
    divergence = value("divergence_tag")
    filing = value("next_filing_at")
    affected = []
    if "members" in event and "ticker" not in late:
        for item in event.get("members") or []:
            ticker = item.get("ticker")
            if not isinstance(ticker, str) or not ticker or item.get("exposure") in (None, ""):
                continue
            affected.append(
                {
                    "ticker": ticker,
                    "exposure": None if "exposure" in late else item.get("exposure"),
                    "divergence_tag": None if "divergence_tag" in late else item.get("divergence_tag"),
                    "next_filing_at": None if "next_filing_at" in late else item.get("next_filing_at"),
                }
            )
    elif shown_ticker is not None or shown_exposure is not None:
        affected.append(
            {
                "ticker": shown_ticker,
                "exposure": shown_exposure,
                "divergence_tag": divergence,
                "next_filing_at": filing,
            }
        )
    flat = {
        "event_id": event.get("event_id"),
        "anomaly_id": event.get("anomaly_id"),
        "lifecycle": value("lifecycle"),
        "observed_at": event.get("observed_at"),
        "mechanism": value("mechanism"),
        "affected": affected,
        "direction": value("direction"),
        "divergence_tag": divergence,
        "dimensions": value("dimensions"),
        "next_filing_at": filing,
        "systemic_tag": value("systemic_tag"),
        "deadline_outcome": value("deadline_outcome"),
        "evidence_ids": list(event.get("evidence_ids") or []),
    }
    return flat, late


def _source_event(event):
    return {
        "event_id": event.get("event_id"),
        "anomaly_id": event.get("anomaly_id"),
        "evidence_ids": list(event.get("evidence_ids") or []),
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


def _loads(value):
    if isinstance(value, str):
        return json.loads(value)
    if hasattr(value, "obj"):
        return value.obj
    return value


def _aware(value):
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed
