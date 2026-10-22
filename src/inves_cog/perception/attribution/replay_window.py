"""Replay five trade days in memory. Live M8 tables are not written."""

import json
import sys
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.chain import _closed_trade_date, job_slot, run_scheduled
from inves_cog.perception.attribution.snapshot import STAGES, _date_text, _null_deadline_reason, append_replay_snapshot
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
        """Upsert like the database store. A later report does not erase linkage."""
        _guard(bundle)
        current = dict(self.bundles.get(bundle["anomaly_id"]) or {})
        current.update(bundle)
        self.bundles[bundle["anomaly_id"]] = current


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


class Counting:
    """Walk the real chain and count calls. The reply is local and is not a model."""

    def __init__(self):
        self.tasks = []

    def call(self, task, payload):
        self.tasks.append(task)
        if task == "claim_extraction":
            return {
                "items": [
                    {
                        "info_id": row.get("info_id"),
                        "claims": [{"subject": "公司", "mechanism": "供给", "direction": "down"}],
                    }
                    for row in payload.get("items") or []
                    if isinstance(row, dict) and row.get("info_id")
                ]
            }
        if task == "anomaly_candidates":
            return {"candidates": [_counted_candidate(payload)]}
        return {"没有": True}


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
    actor = Counting() if dry_run else recorder
    holder = MemoryStore() if dry_run else store
    stages = []
    for name in STAGES:
        moment = slot_moment(trade_date, name)
        seen = visible_news(items, moment)
        info_ids = [item.get("info_id") for item in seen]
        before = _call_count(actor)
        rows = run_scheduled(
            moment,
            anomalies=due,
            items=[item for item in items or [] if item.get("info_id") in info_ids],
            client=actor,
            store=holder,
        )
        stages.append(
            {
                "task_name": name,
                "as_of": moment.isoformat(),
                "anomalies": len(due),
                "news": len(seen),
                "info_ids": info_ids,
                "calls": _tally(_new_calls(actor, before)),
            }
        )
        failed = [row for row in (rows or {}).get("rows") or [] if not row.get("saved")]
        if not dry_run and due and failed:
            return {"trade_date": trade_date, "stages": stages, "snapshot_id": None, "error": "未保存"}
    result = {"trade_date": trade_date, "stages": stages, "snapshot_id": None}
    if dry_run or not stages:
        return result
    labels = datetime.fromisoformat(stages[-1]["as_of"])
    events, missing = _events(holder, [row.get("anomaly_id") for row in due], labels)
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


def _call_count(actor):
    if actor is None:
        return 0
    return len(getattr(actor, "calls", None) or getattr(actor, "tasks", None) or [])


def _new_calls(actor, before):
    if actor is None:
        return []
    found = getattr(actor, "calls", None)
    if found is None:
        found = getattr(actor, "tasks", None) or []
    return list(found)[before:]


def _tally(calls):
    totals = {}
    for item in calls:
        name = item.get("task") if isinstance(item, dict) else item
        if not name:
            continue
        totals[name] = totals.get(name, 0) + 1
    return totals


def _counted_candidate(payload):
    anomaly = payload.get("anomaly") if isinstance(payload, dict) else {}
    anomaly = anomaly if isinstance(anomaly, dict) else {}
    info_ids = [
        row.get("info_id")
        for row in (payload.get("items") or [])
        if isinstance(row, dict) and isinstance(row.get("info_id"), str) and row.get("info_id")
    ]
    ticker = "NVDA"
    for member in anomaly.get("members") or []:
        name = member.get("ticker") if isinstance(member, dict) else member
        if isinstance(name, str) and name:
            ticker = name
            break
    return {
        "mechanism": "供给",
        "info_ids": info_ids[:1],
        "affected": [{"ticker": ticker}],
        "chain": [{"entity_id": ticker}],
        "control_baskets": [],
        "links": [
            {
                "kind": "声明的假设",
                "from": "新闻",
                "to": ticker,
                "hypothesis": "供应变化影响该标的",
                "hypothesis_type": "暴露关系",
                "falsify": {"metric": "收入", "direction": "下降", "window": "下一季"},
            }
        ],
        "竞争解释": [],
        "反证条件": "下一季收入没有下降",
        "证伪预测": [{"ticker": ticker, "control_basket": "存储", "direction": "down", "window": "下一季"}],
    }


def _events(store, anomaly_ids, as_of):
    events = []
    fields = {}
    for anomaly_id in anomaly_ids:
        bundle = store.bundles.get(anomaly_id)
        if bundle is None or not (bundle.get("linkage") or {}).get("lifecycle"):
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
    scope_ticker, scope_exposure = _scope_pair(report)
    values = {
        "lifecycle": linkage.get("lifecycle"),
        "mechanism": report.get("mechanism") or linkage.get("mechanism") or _lead(report),
        "ticker": _ticker(bundle) or scope_ticker,
        "exposure": _exposure(bundle) or scope_exposure,
        "direction": _direction(bundle),
        "divergence_tag": report.get("divergence_label") or report.get("divergence_tag"),
        "dimensions": report.get("dimensions") or _track_dimensions(bundle),
        "next_filing_at": report.get("next_filing_at"),
        "systemic_tag": (bundle.get("market_day") or {}).get("systemic_event_tag"),
        "deadline_outcome": linkage.get("deadline_outcome") or report.get("deadline_outcome"),
    }
    deadline_on = _date_text(report.get("deadline_on"))
    cells = {}
    gaps = {}
    for name in _FIELDS:
        value = values[name]
        if name == "deadline_outcome":
            continue
        if value in (None, ""):
            cells[name] = {"value": None, "at": stamp, "missing_reason": "回放没有该字段"}
            gaps[name] = "回放没有该字段"
        else:
            cells[name] = {"value": value, "at": stamp, "missing_reason": None}
    cells["deadline_on"] = _replay_deadline_on(deadline_on, stamp)
    cells["deadline_outcome"], outcome_gap = _replay_outcome(values["deadline_outcome"], deadline_on, as_of, stamp)
    if outcome_gap is not None:
        gaps["deadline_outcome"] = outcome_gap
    members = _members(bundle, report, values)
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


def _replay_deadline_on(deadline_on, stamp):
    if deadline_on is None:
        return {"value": None, "at": None, "missing_reason": None}
    return {"value": deadline_on, "at": stamp, "missing_reason": None}


def _replay_outcome(outcome, deadline_on, as_of, stamp):
    if outcome not in (None, ""):
        return {"value": outcome, "at": stamp, "missing_reason": None}, None
    reason = _null_deadline_reason(deadline_on, as_of)
    if reason is None:
        return {"value": None, "at": None, "missing_reason": None}, None
    return {"value": None, "at": None, "missing_reason": reason}, reason


def _lead(report):
    scored = [
        row
        for row in report.get("candidates") or []
        if isinstance(row, dict) and row.get("scored") and row.get("score") is not None
    ]
    if not scored:
        return None
    return max(scored, key=lambda row: row["score"]).get("mechanism")


def _scope_pair(report):
    """Tickers and exposures the chain already stamped. Several exposures stay a list."""
    names = []
    exposures = []
    for row in report.get("scope") or []:
        if not isinstance(row, dict) or not row.get("ticker") or not row.get("exposure"):
            continue
        names.append(row["ticker"])
        exposures.append(row["exposure"])
    ticker = names[0] if len(names) == 1 else names or None
    if len(exposures) == 1:
        exposure = exposures[0]
    elif exposures:
        exposure = exposures
    else:
        exposure = None
    return ticker, exposure


def _track_dimensions(bundle):
    matched = []
    for item in bundle.get("tracks") or []:
        if not isinstance(item, dict):
            continue
        value = {key: item.get(key) for key in ("emotion", "capital", "fundamental") if item.get(key) is not None}
        if value:
            matched.append(value)
    if len(matched) == 1:
        return matched[0]
    return None


def _members(bundle, report, values):
    members = []
    seen = set()
    for row in bundle.get("ticker_status") or []:
        ticker = row.get("ticker")
        exposure = row.get("exposure")
        if ticker and exposure:
            members.append(_member(ticker, exposure, values))
            seen.add(ticker)
    for row in report.get("scope") or []:
        if not isinstance(row, dict) or not row.get("ticker") or not row.get("exposure") or row["ticker"] in seen:
            continue
        members.append(_member(row["ticker"], row["exposure"], values))
        seen.add(row["ticker"])
    for candidate in bundle.get("candidates") or []:
        for affected in candidate.get("affected") or []:
            if not isinstance(affected, dict) or not affected.get("ticker") or not affected.get("exposure"):
                continue
            if affected["ticker"] in seen:
                continue
            members.append(_member(affected["ticker"], affected["exposure"], values))
            seen.add(affected["ticker"])
    return members


def _member(ticker, exposure, values):
    return {
        "ticker": ticker,
        "exposure": exposure,
        "divergence_tag": values["divergence_tag"],
        "next_filing_at": values["next_filing_at"],
    }


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


def main(argv=None, *, connection=None, perception=None, clock=None, client=None):
    """Read inputs on the default connection. --execute writes the replay snapshot on the perception connection."""
    args = list(sys.argv[1:] if argv is None else argv)
    mode = _cli_mode(args)
    days = _cli_days(args)
    from inves_cog.perception.attribution.morning import _connections

    borrowed, writer, owned = _connections(connection, perception)
    try:
        return _cli_run(borrowed, writer, days, mode, clock, client)
    finally:
        for item in owned:
            item.close()


def _cli_mode(args):
    dry = "--dry-run" in args
    execute = "--execute" in args
    if dry and execute:
        raise SystemExit("不能同时 --dry-run 和 --execute")
    if not dry and not execute:
        raise SystemExit("需要 --dry-run 或 --execute")
    return "dry-run" if dry else "execute"


def _cli_days(args):
    if "--days" not in args:
        return DAYS
    index = args.index("--days")
    if index + 1 >= len(args):
        raise SystemExit("需要 --days 后面的日期")
    found = tuple(part for part in args[index + 1].split(",") if part)
    if not found:
        raise SystemExit("需要 --days 后面的日期")
    return found


def _cli_run(connection, writer, days, mode, clock, client):
    from inves_cog.perception.attribution.morning import _require_writer

    if mode == "execute" and writer is None:
        raise SystemExit("缺少 INVES_COG_PERCEPTION_DATABASE_URL")
    if mode == "execute" and writer is not connection:
        _require_writer(writer)
    anomalies, items = _load_window(connection, days)
    if clock is None:
        from inves_cog.clock import SystemClock

        clock = SystemClock()
    actor = None
    if mode == "execute":
        if client is None:
            from inves_cog.llm.client import Client

            client = Client.from_environment()
        actor = client
    result = replay_window(
        writer if mode == "execute" else connection,
        clock,
        anomalies=anomalies,
        items=items,
        days=days,
        client=actor,
        dry_run=mode == "dry-run",
    )
    body = {"dry_run": result["dry_run"], "calls": result["calls"], "days": result["days"]}
    json.dump(body, sys.stdout, default=_dump)
    sys.stdout.write("\n")
    return 0


def _load_window(connection, days):
    from inves_cog.perception.attribution.morning import _load

    anomalies = []
    items = []
    seen_anomalies = set()
    seen_items = set()
    for day in days:
        loaded = _load(connection, slot_moment(day, "attribution_labels"), day)
        for row in loaded["anomalies"]:
            identity = row.get("anomaly_id")
            if identity in seen_anomalies:
                continue
            seen_anomalies.add(identity)
            anomalies.append(row)
        for item in loaded["items"]:
            identity = item.get("info_id")
            if identity in seen_items:
                continue
            seen_items.add(identity)
            items.append(item)
    return anomalies, items


if __name__ == "__main__":
    raise SystemExit(main())
