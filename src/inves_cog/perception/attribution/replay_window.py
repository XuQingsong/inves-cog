"""Replay five trade days in memory. Live M8 tables are not written."""

import json
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.chain import _before_move, _closed_trade_date, _retrieved, job_slot, run_scheduled
from inves_cog.perception.attribution.snapshot import STAGES, append_replay_snapshot
from inves_cog.perception.attribution.store import _guard

DAYS = ("2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21")
_SLOTS = {
    "attribution_candidates": time(9, 15),
    "attribution_tracks": time(9, 30),
    "attribution_labels": time(12, 30),
}
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_FIELDS = (
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


class MemoryStore:
    """Cross-day lifecycle stays in this process. Nothing is sent to live M8 tables."""

    def __init__(self):
        self.bundles = {}

    def report(self, anomaly_id):
        bundle = self.bundles.get(anomaly_id)
        report = bundle.get("report") if bundle else None
        return dict(report) if isinstance(report, dict) else None

    def prior(self, event_id):
        for bundle in self.bundles.values():
            linkage = bundle.get("linkage") or {}
            if linkage.get("event_id") != event_id:
                continue
            report = bundle.get("report") if isinstance(bundle.get("report"), dict) else {}
            formed = linkage.get("deadline_outcome") is not None or linkage.get("closing_reason") is not None
            standing = report.get("fundamental_standing") if formed else None
            return {
                "lifecycle": linkage.get("lifecycle"),
                "history": list(linkage.get("history") or []),
                "deadline_outcome": linkage.get("deadline_outcome"),
                "closing_reason": linkage.get("closing_reason"),
                "unknowns": list(linkage.get("unknowns") or []),
                "fundamental": standing,
                "operating_impact_proven": report.get("operating_impact_proven") if formed else None,
            }
        return None

    def price_event(self, event_id, anomaly_id):
        linkage = (self.bundles.get(anomaly_id) or {}).get("linkage") or {}
        return linkage.get("event_id") == event_id

    def save(self, bundle):
        _guard(bundle)
        self.bundles[bundle["anomaly_id"]] = bundle


class Recording:
    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def call(self, task, payload):
        digest = sha256(canonical_payload(payload).encode()).hexdigest()
        output = self.inner.call(task, payload)
        self.calls.append({"task": task, "input_hash": digest, "output": output})
        return output


def visible_news(items, as_of):
    """News is usable only once it had been seen. Publication alone is not enough."""
    kept = []
    for item in items or []:
        seen = item.get("first_seen_at")
        if seen is None or seen > as_of:
            continue
        kept.append(item)
    return kept


def slot_moment(trade_date, task_name):
    """The real Beijing schedule instant whose closed US session is this trade date."""
    day = date.fromisoformat(str(trade_date)[:10])
    for offset in range(0, 5):
        local_day = day + timedelta(days=offset)
        base = datetime.combine(local_day, _SLOTS[task_name], tzinfo=_SHANGHAI)
        for extra in (0, 1):
            moment = base + timedelta(hours=extra)
            slot = job_slot(moment)
            if slot is None or slot["task_name"] != task_name:
                continue
            if _closed_trade_date(moment) == day.isoformat():
                return moment
    raise ValueError(f"没有{trade_date}的{task_name}时点")


def expected_calls(anomaly, items, as_of, stage):
    """Count the model calls this stage would make. It does not make them."""
    if stage != "attribution_candidates":
        return {}
    if anomaly.get("started_at") is None or "universe" not in anomaly:
        return {}
    if anomaly.get("capital_track") is not None or anomaly.get("universe") == "wide":
        return {}
    visible = _retrieved(anomaly, [item for item in items if item.get("published_at") is not None], as_of)
    if any(_before_move(item, anomaly.get("started_at")) for item in visible):
        return {"move_card": 1}
    if not visible:
        return {}
    return {"claim_extraction": 1, "anomaly_candidates": 1}


def replay_window(connection, clock, *, anomalies, items, days=DAYS, client=None, dry_run=False, log_path=None):
    """Plan or run the five days. Dry-run never calls the model and writes nothing."""
    store = MemoryStore()
    recorder = Recording(client) if client is not None and not dry_run else None
    played = []
    for trade_date in days:
        played.append(
            _day(
                connection,
                clock,
                store,
                recorder,
                trade_date,
                anomalies,
                items,
                dry_run=dry_run,
            )
        )
    if log_path is not None:
        body = {"dry_run": dry_run, "calls": [] if recorder is None else recorder.calls, "days": played}
        Path(log_path).write_text(json.dumps(body, ensure_ascii=False, default=_dump), encoding="utf-8")
    return {"dry_run": dry_run, "days": played, "calls": [] if recorder is None else recorder.calls}


def _day(connection, clock, store, recorder, trade_date, anomalies, items, *, dry_run):
    due = [row for row in anomalies or [] if str(row.get("trade_date") or "")[:10] == trade_date]
    stages = []
    for name in STAGES:
        moment = slot_moment(trade_date, name)
        seen = visible_news(items, moment)
        stages.append(
            {
                "task_name": name,
                "as_of": moment.isoformat(),
                "anomalies": len(due),
                "news": len(seen),
                "info_ids": [item.get("info_id") for item in seen],
                "calls": _sum_calls(due, seen, moment, name),
            }
        )
    result = {"trade_date": trade_date, "stages": stages, "snapshot_id": None}
    if dry_run:
        return result
    for stage in stages:
        rows = run_scheduled(
            datetime.fromisoformat(stage["as_of"]),
            anomalies=due,
            items=[item for item in items or [] if item.get("info_id") in stage["info_ids"]],
            client=recorder,
            store=store,
        )
        failed = [row for row in (rows or {}).get("rows") or [] if not row.get("saved")]
        if due and failed:
            result["error"] = "未保存"
            return result
    labels = datetime.fromisoformat(stages[-1]["as_of"])
    events, missing = _events(store, [row.get("anomaly_id") for row in due], labels)
    result["snapshot_id"] = append_replay_snapshot(
        connection,
        trade_date,
        clock,
        source_asof=labels,
        events=events,
        stages={stage["task_name"]: stage["as_of"] for stage in stages},
        missing=missing,
    )
    return result


def _sum_calls(anomalies, items, as_of, stage):
    totals = {}
    for anomaly in anomalies:
        for name, count in expected_calls(anomaly, items, as_of, stage).items():
            totals[name] = totals.get(name, 0) + count
    return totals


def _events(store, anomaly_ids, as_of):
    events = []
    fields = {}
    for anomaly_id in anomaly_ids:
        bundle = store.bundles.get(anomaly_id)
        if bundle is None:
            continue
        event, gaps = _event(bundle, as_of)
        events.append(event)
        if gaps:
            fields[event["event_id"]] = gaps
    return events, {"stages": [], "events": [], "fields": fields}


def _event(bundle, as_of):
    report = bundle.get("report") if isinstance(bundle.get("report"), dict) else {}
    linkage = bundle.get("linkage") or {}
    event_id = linkage.get("event_id") or f"evt-{bundle.get('anomaly_id')}"
    stamp = as_of.isoformat()
    values = {
        "lifecycle": linkage.get("lifecycle"),
        "mechanism": report.get("mechanism") or linkage.get("mechanism"),
        "ticker": _ticker(bundle),
        "exposure": _exposure(bundle),
        "direction": _direction(bundle),
        "divergence_tag": report.get("divergence_label") or report.get("divergence_tag"),
        "dimensions": report.get("dimensions"),
        "next_filing_at": report.get("next_filing_at"),
        "systemic_tag": (bundle.get("market_day") or {}).get("systemic_event_tag"),
        "deadline_outcome": linkage.get("deadline_outcome") or report.get("deadline_outcome"),
    }
    cells = {}
    gaps = {}
    for name in _FIELDS:
        value = values[name]
        if value in (None, ""):
            cells[name] = {"value": None, "at": stamp, "missing_reason": "回放没有该字段"}
            gaps[name] = "回放没有该字段"
        else:
            cells[name] = {"value": value, "at": stamp, "missing_reason": None}
    members = []
    for row in bundle.get("ticker_status") or []:
        if row.get("ticker") and row.get("exposure"):
            members.append(
                {
                    "ticker": row["ticker"],
                    "exposure": row["exposure"],
                    "divergence_tag": values["divergence_tag"],
                    "next_filing_at": values["next_filing_at"],
                }
            )
    return (
        {
            "event_id": event_id,
            "anomaly_id": bundle.get("anomaly_id"),
            "observed_at": stamp if linkage else None,
            "evidence_ids": [],
            "fields": cells,
            "members": members,
        },
        gaps,
    )


def _ticker(bundle):
    rows = [row.get("ticker") for row in bundle.get("ticker_status") or [] if row.get("ticker")]
    if len(rows) == 1:
        return rows[0]
    return rows or None


def _exposure(bundle):
    rows = [row.get("exposure") for row in bundle.get("ticker_status") or [] if row.get("exposure")]
    if len(rows) == 1:
        return rows[0]
    return rows or None


def _direction(bundle):
    found = []
    for row in bundle.get("claims") or []:
        if row.get("direction") and row["direction"] not in found:
            found.append(row["direction"])
    if len(found) == 1:
        return found[0]
    return None


def _dump(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)
