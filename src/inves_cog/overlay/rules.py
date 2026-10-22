"""Pure tightening-only overlay generation from explicitly visible M8 conclusions."""

from copy import deepcopy
from datetime import datetime


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed is not None and (parsed.tzinfo is None or parsed.utcoffset() is None):
        raise ValueError("source timestamp must include timezone")
    return parsed


def cooling_condition(event, affected, *, asof):
    reasons = []
    if affected.get("exposure") != "直接" or event.get("mechanism") in (None, "估值倍数"):
        return False, reasons
    state = event.get("lifecycle")
    if event.get("deadline_outcome") == "条件风险":
        return False, reasons
    if state in ("市场确认", "基本面核查中"):
        return True, reasons
    if state == "已验证·有影响" and event.get("direction") in ("不利", "down"):
        filing = timestamp(affected.get("next_filing_at", event.get("next_filing_at")))
        if filing is None:
            reasons.append("下一份10-Q/10-K生效时间未知，保留已验证不利事件冷静期")
        return filing is None or filing > asof, reasons
    return False, reasons


def _affected_with_gaps(event, fields):
    affected = {row["ticker"]: deepcopy(row) for row in event.get("affected") or [] if row.get("ticker")}
    for key in fields:
        if "." in key:
            ticker, field = key.rsplit(".", 1)
            if field == "exposure" and ticker:
                affected.setdefault(ticker, {"ticker": ticker})
    return affected.values()


def _ticker_gaps(event, ticker, fields):
    gaps = []
    for key, reason in fields.items():
        field = key
        if "." in key:
            symbol, field = key.rsplit(".", 1)
            if symbol != ticker:
                continue
        gaps.append({"event_id": event["event_id"], "field": field, "reason": reason})
    return gaps


def _add_event(item, event, affected, fields, source):
    gaps = _ticker_gaps(event, affected["ticker"], fields)
    missing = {gap["field"] for gap in gaps}
    required = {"lifecycle", "mechanism", "exposure", "deadline_outcome"}
    if event.get("lifecycle") == "已验证·有影响":
        required.add("direction")
    decision_gaps = sorted(missing & required)
    # Only the provider knows whether a NULL is normal, unavailable, or not yet due.
    visible_event = {**event, **{key: None for key in missing}}
    visible_affected = {**affected, **{key: None for key in missing}}
    cooling, notes = (False, []) if decision_gaps else cooling_condition(visible_event, visible_affected, asof=source)
    item["cooling_off"] |= cooling
    if item["cooling_off"]:
        item["cooling_status"] = "on"
    elif decision_gaps:
        item["cooling_status"] = "unknown"
    item["m8_gaps"].extend(gaps)
    item["linkage_events"].append(
        {
            "id": event["event_id"],
            "lifecycle": visible_event.get("lifecycle"),
            "dimensions": deepcopy(visible_event.get("dimensions")),
            "mechanism": visible_event.get("mechanism"),
            "exposure": visible_affected.get("exposure"),
            "divergence_tag": visible_affected.get("divergence_tag"),
            "systemic_tag": visible_event.get("systemic_tag"),
            "evidence_ids": list(event.get("evidence_ids") or []),
        }
    )
    if decision_gaps:
        reason = "冷静期判断未完成：缺 " + ", ".join(decision_gaps)
    else:
        reason = "事件冷静期" if cooling else "已完成冷静期判定：不触发"
    item["reason"] += ("；" if item["reason"] else "") + f"{reason}：联动事件 {event['event_id']}"
    if notes:
        item["reason"] += "（" + "；".join(notes) + "）"
    return visible_affected.get("divergence_tag")


def generate_overlay(
    events, *, clock, version, source_asof, source_complete=True, previous=None, market=None, missing=None
):
    now = clock.now_utc()
    if not source_complete:
        return deepcopy(previous)
    source = timestamp(source_asof)
    if source is None or source > now:
        raise ValueError("M8 completed snapshot needs a visible source_events_asof")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("overlay version must be a positive integer")
    tickers, tags_by_ticker = {}, {}
    for event in events:
        created = timestamp(event.get("created_at"))
        observed = timestamp(event.get("observed_at"))
        if (created and created > source) or (observed and observed > source):
            continue
        if not event.get("event_id"):
            raise ValueError("every linkage needs an event id")
        fields = ((missing or {}).get("fields") or {}).get(event["event_id"], {})
        for affected in _affected_with_gaps(event, fields):
            ticker = affected.get("ticker")
            if not ticker:
                continue
            item = tickers.setdefault(
                ticker,
                {
                    "linkage_events": [],
                    "cooling_off": False,
                    "cooling_status": "off",
                    "m8_gaps": [],
                    "first_lot_multiplier": 1.0,
                    "divergence_tag": None,
                    "stop_review_eligible": False,
                    "reason": "",
                },
            )
            tag = _add_event(item, event, affected, fields, source)
            if tag is not None:
                tags_by_ticker.setdefault(ticker, set()).add(tag)
    for ticker, tags in tags_by_ticker.items():
        tickers[ticker]["divergence_tag"] = next(iter(tags)) if len(tags) == 1 else None
        if len(tags) > 1:
            tickers[ticker]["reason"] += "（不同事件背离标签冲突，未合成标签）"
    unknown = sorted(ticker for ticker, item in tickers.items() if item["cooling_status"] == "unknown")
    return {
        "version": version,
        "generated_at": now.isoformat(),
        "source_events_asof": source.isoformat(),
        "params_version": "p-2026.10",
        "tickers": tickers,
        "m8_completeness": {
            "complete": True,
            "source_events_asof": source_asof.isoformat() if isinstance(source_asof, datetime) else source_asof,
            "unknown_ticker_count": len(unknown),
            "unknown_tickers": unknown,
        },
        "market": deepcopy(market)
        if market is not None
        else {"risk_level": None, "l1_state": None, "systemic_events": []},
    }
