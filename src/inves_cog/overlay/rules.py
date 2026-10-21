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


def generate_overlay(events, *, clock, version, source_asof, source_complete=True, previous=None, market=None):
    now = clock.now_utc()
    if not source_complete:
        return deepcopy(previous)
    source = timestamp(source_asof)
    if source is None or source > now:
        raise ValueError("M8 completed snapshot needs a visible source_events_asof")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("overlay version must be a positive integer")
    tickers = {}
    for event in events:
        created = timestamp(event.get("created_at"))
        observed = timestamp(event.get("observed_at"))
        if (created and created > source) or (observed and observed > source):
            continue
        if not event.get("event_id"):
            raise ValueError("every linkage needs an event id")
        for affected in event.get("affected") or []:
            ticker = affected.get("ticker")
            if not ticker:
                continue
            cooling, gaps = cooling_condition(event, affected, asof=source)
            item = tickers.setdefault(
                ticker,
                {
                    "linkage_events": [],
                    "cooling_off": False,
                    "first_lot_multiplier": 1.0,
                    "divergence_tag": None,
                    "stop_review_eligible": False,
                    "reason": "",
                },
            )
            item["cooling_off"] |= cooling
            item["linkage_events"].append(
                {
                    "id": event["event_id"],
                    "lifecycle": event.get("lifecycle"),
                    "dimensions": deepcopy(event.get("dimensions")),
                    "mechanism": event.get("mechanism"),
                    "exposure": affected.get("exposure"),
                    "evidence_ids": list(event.get("evidence_ids") or []),
                }
            )
            tag = affected.get("divergence_tag")
            if tag is not None:
                # Conflicting tags remain explicit, never choose the more actionable one.
                if item["divergence_tag"] not in (None, tag):
                    gaps.append("不同事件背离标签冲突，未合成标签")
                    item["divergence_tag"] = None
                else:
                    item["divergence_tag"] = tag
            reason = "事件冷静期" if cooling else "该事件不触发冷静期"
            item["reason"] += ("；" if item["reason"] else "") + f"{reason}：联动事件 {event['event_id']}"
            if gaps:
                item["reason"] += "（" + "；".join(gaps) + "）"
    return {
        "version": version,
        "generated_at": now.isoformat(),
        "source_events_asof": source.isoformat(),
        "params_version": "p-2026.10",
        "tickers": tickers,
        "market": deepcopy(market)
        if market is not None
        else {"risk_level": None, "l1_state": None, "systemic_events": []},
    }
