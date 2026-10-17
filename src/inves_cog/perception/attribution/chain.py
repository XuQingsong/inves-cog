"""Run one attribution pass. A failed anomaly does not stop the next one.

The model may propose a mechanism. Scores, lifecycle, and the report come
from the rules. This module does not open a database URL and does not deploy
the morning schedule.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from inves_cog.perception.attribution.candidates import validate_candidates
from inves_cog.perception.attribution.claims import attach_claims
from inves_cog.perception.attribution.evidence import evidence_score
from inves_cog.perception.attribution.lifecycle import transition
from inves_cog.perception.attribution.propose import propose_candidates
from inves_cog.perception.attribution.replay import replay_mode
from inves_cog.perception.attribution.report import explanation_report
from inves_cog.perception.attribution.retrieve import retrieval_mode, window_items

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_NEW_YORK = ZoneInfo("America/New_York")
_SLOTS = (
    ("attribution_candidates", time(9, 15)),
    ("attribution_tracks", time(9, 30)),
    ("attribution_labels", time(12, 30)),
)
_CLAIM_FIELDS = ("subject", "variable", "mechanism", "direction", "quantity", "horizon", "certainty", "source_level")


def attribute_all(anomalies, items, *, as_of, client, store=None, components_by_id=None):
    """Retrieve, score, report, and save each anomaly. One failure stays on that row."""
    usable = [item for item in items if item.get("published_at") is not None]
    scores = components_by_id or {}
    rows = []
    for anomaly in anomalies:
        try:
            rows.append(
                _one(
                    anomaly,
                    usable,
                    as_of=as_of,
                    client=client,
                    store=store,
                    components=scores.get(anomaly.get("anomaly_id")),
                )
            )
        except Exception as exc:
            rows.append(
                {
                    "anomaly_id": anomaly.get("anomaly_id"),
                    "status": "待分析",
                    "degraded": str(exc),
                    "saved": False,
                    "operating_impact_proven": False,
                }
            )
    return rows


def replay_days(anomalies, items, days, *, client, store=None, components_by_id=None):
    """Replay each as-of with only the items visible then."""
    played = []
    for as_of in days:
        mode = replay_mode(items, as_of)
        batch = attribute_all(
            anomalies,
            items,
            as_of=as_of,
            client=client,
            store=store,
            components_by_id=components_by_id,
        )
        played.append({"as_of": as_of, "replay": mode, "anomalies": batch})
    return played


def job_slot(when):
    """Beijing clock for the three FR-M8-28 jobs. Winter adds one hour. Nothing is deployed."""
    shanghai = when.astimezone(_SHANGHAI)
    winter = when.astimezone(_NEW_YORK).utcoffset() == timedelta(hours=-5)
    shift = timedelta(hours=1) if winter else timedelta(0)
    clock = shanghai.timetz().replace(second=0, microsecond=0, tzinfo=None)
    for name, slot in _SLOTS:
        scheduled = (datetime.combine(shanghai.date(), slot) + shift).time()
        if clock == scheduled:
            return {"task_name": name, "beijing": clock.strftime("%H:%M"), "winter": winter}
    return None


def run_scheduled(when, *, connection=None, clock=None, trade_date=None, params_version=None, operation=None):
    """Name the job for this minute. A caller-supplied connection can record it."""
    slot = job_slot(when)
    if slot is None:
        return None
    if connection is None:
        return {**slot, "recorded": False}
    from inves_cog.perception.anomaly.service import run_recorded

    row_id = run_recorded(
        connection,
        clock=clock,
        task_name=slot["task_name"],
        trade_date=trade_date,
        params_version=params_version,
        operation=operation,
    )
    return {**slot, "recorded": True, "job_id": row_id}


def _one(anomaly, items, *, as_of, client, store, components):
    if anomaly.get("started_at") is None or "universe" not in anomaly:
        raise ValueError("异常缺少起点或范围")
    visible = window_items(items, anomaly["started_at"], as_of)
    claimed, claim_note = _claims(visible, client, anomaly.get("universe"))
    candidates, model_note = _candidates(anomaly, claimed, client)
    candidates = _apply_score(candidates, components)
    when = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
    state, history = _lifecycle(candidates, when)
    report = _report(anomaly, candidates, claimed, "待分析" if model_note else None)
    report["lifecycle"] = state
    report["history"] = history
    report["operating_impact_proven"] = False
    saved = False
    if store is not None:
        store.save(_bundle(anomaly, claimed, candidates, report, state, history))
        saved = True
    notes = [note for note in (claim_note, model_note) if note]
    return {
        "anomaly_id": anomaly.get("anomaly_id"),
        "status": report["status"],
        "report": report,
        "lifecycle": state,
        "history": history,
        "degraded": "；".join(notes) if notes else None,
        "saved": saved,
        "operating_impact_proven": False,
    }


def _claims(items, client, universe):
    if universe == "wide" or not items or client is None:
        return [dict(item) for item in items], None
    try:
        return attach_claims(items, client), None
    except Exception:
        return [dict(item) for item in items], "抽取失败"


def _candidates(anomaly, items, client):
    universe = _tickers(anomaly)
    if anomaly.get("universe") == "wide":
        return [], None
    retrieved = {item["info_id"] for item in items}
    if not items:
        return validate_candidates([], set(), universe), None
    if client is None:
        return validate_candidates([], retrieved, universe), "模型调用失败"
    try:
        return propose_candidates(anomaly, items, [], client, universe), None
    except Exception:
        return validate_candidates([], retrieved, universe), "模型调用失败"


def _apply_score(candidates, components):
    if not candidates or components is None:
        return candidates
    scored = evidence_score(components)
    updated = []
    for row in candidates:
        if not row.get("scored"):
            updated.append(row)
            continue
        copied = dict(row)
        copied["evidence"] = scored
        copied["score"] = scored["total"]
        copied["confidence"] = scored["confidence"]
        copied["fundamental"] = None
        updated.append(copied)
    return updated


def _lifecycle(candidates, when):
    evidence_ids = []
    for row in candidates:
        if row.get("scored") and row.get("score") is not None and row["score"] >= 0.5:
            evidence_ids.extend(row.get("info_ids") or [])
    state, history = transition(None, "已发现", [], when=when, trigger="异常", evidence_ids=[])
    if evidence_ids:
        state, history = transition(
            state,
            "假设中",
            history,
            when=when,
            trigger="证据分达到假设",
            evidence_ids=evidence_ids,
        )
    return state, history


def _report(anomaly, candidates, items, status):
    current = {key: value for key, value in anomaly.items() if key != "status"}
    if status:
        current["status"] = status
    sources = [{"info_id": item["info_id"], "role": item.get("role")} for item in items]
    return explanation_report(current, None, candidates, sources, embeddings=anomaly.get("embeddings"))


def _bundle(anomaly, items, candidates, report, state, history):
    mode = retrieval_mode(anomaly.get("embeddings") or [])
    bundle = {
        "anomaly_id": anomaly["anomaly_id"],
        "universe": anomaly.get("universe"),
        "retrievals": [
            {
                "info_id": item["info_id"],
                "role": item.get("role"),
                "retrieval_mode": mode,
                "published_at": item.get("published_at"),
                "source_level": item.get("source_level"),
                "relevance": item.get("relevance"),
            }
            for item in items
        ],
        "claims": _claim_rows(items),
        "report": report,
    }
    if anomaly.get("universe") == "wide":
        bundle.pop("claims")
        return bundle
    bundle["candidates"] = candidates
    codes = [row for row in report.get("ticker_status") or [] if row.get("n_code")]
    if codes:
        bundle["ticker_status"] = codes
    if state == "假设中":
        bundle["linkage"] = {"event_id": f"evt-{anomaly['anomaly_id']}", "lifecycle": state, "history": history}
        if anomaly.get("trade_date"):
            bundle["tracks"] = [{"trade_date": anomaly["trade_date"], "emotion": "初现", "fundamental": "待验证"}]
    return bundle


def _claim_rows(items):
    rows = []
    for item in items:
        for index, claim in enumerate(item.get("claims") or []):
            if not isinstance(claim, dict):
                continue
            row = {
                "claim_id": claim.get("claim_id") or f"{item['info_id']}:{index}",
                "info_id": item["info_id"],
            }
            row.update({key: claim.get(key) for key in _CLAIM_FIELDS})
            rows.append(row)
    return rows


def _tickers(anomaly):
    names = set()
    for member in anomaly.get("members") or []:
        if isinstance(member, dict) and member.get("ticker"):
            names.add(member["ticker"])
        elif isinstance(member, str):
            names.add(member)
    return names
