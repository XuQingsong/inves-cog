"""Run one attribution pass. A failed anomaly does not stop the next one.

The model may propose a mechanism. Scores, lifecycle, and the report come
from the rules. This module does not open a database URL and does not deploy
the morning schedule.
"""

import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import exchange, regular_bounds, trading_day
from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.candidates import market_confirmed, validate_candidates
from inves_cog.perception.attribution.claims import attach_claims, claim_payload, read_claims
from inves_cog.perception.attribution.evidence import (
    alternative_exclusion,
    basket_specificity,
    evidence_score,
    exposure_gradient,
    magnitude_component,
    narrative_support,
    time_alignment,
)
from inves_cog.perception.attribution.impact import decompose
from inves_cog.perception.attribution.lifecycle import transition
from inves_cog.perception.attribution.magnitude import implied_magnitude
from inves_cog.perception.attribution.operating import operating_verdict
from inves_cog.perception.attribution.propose import candidate_payload, propose_candidates
from inves_cog.perception.attribution.replay import replay_mode
from inves_cog.perception.attribution.report import explanation_report
from inves_cog.perception.attribution.retrieve import retrieval_entities, retrieval_mode, shortlist
from inves_cog.perception.attribution.second_hit import (
    classify_response,
    later_matches_fingerprint,
    prediction_fingerprint,
    second_hit_conclusion,
)
from inves_cog.perception.attribution.tracks import apply_deadline, capital_state, deadline_reached, earliest_deadline

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_NEW_YORK = ZoneInfo("America/New_York")
_SLOTS = (
    ("attribution_candidates", time(9, 15)),
    ("attribution_tracks", time(9, 30)),
    ("attribution_labels", time(12, 30)),
)
_CLAIM_FIELDS = ("subject", "variable", "mechanism", "direction", "quantity", "horizon", "certainty", "source_level")
_EVIDENCE = ("time", "gradient", "specificity", "narrative", "magnitude", "alternatives")
_FUNDAMENTAL = {"供给", "需求", "竞争", "客户融资"}
_STAGE_NAMES = {name for name, _slot in _SLOTS}


def attribute_all(anomalies, items, *, as_of, client, store=None, components_by_id=None, stage=None):
    """Retrieve, score, report, and save each anomaly. One failure stays on that row."""
    usable = [item for item in items if item.get("published_at") is not None]
    scores = components_by_id or {}
    rows = []
    for anomaly in anomalies:
        prepared = adapt_m7(anomaly)
        try:
            rows.append(
                _one(
                    prepared,
                    usable,
                    as_of=as_of,
                    client=client,
                    store=store,
                    components=scores.get(prepared.get("anomaly_id")),
                    stage=stage,
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
    """Replay each as-of with anomalies that already occurred and items visible then."""
    played = []
    for as_of in days:
        due = [anomaly for anomaly in anomalies if _occurred(anomaly, as_of)]
        mode = replay_mode(items, as_of)
        batch = attribute_all(
            due,
            items,
            as_of=as_of,
            client=client,
            store=store,
            components_by_id=components_by_id,
        )
        played.append({"as_of": as_of, "replay": mode, "anomalies": batch})
    return played


def _occurred(anomaly, as_of):
    started = anomaly.get("started_at")
    if started is not None:
        return started <= as_of
    trade_date = anomaly.get("trade_date")
    if trade_date is None:
        return True
    return _calendar_day(trade_date) <= _calendar_day(as_of)


def _calendar_day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


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


def execute_stage(task_name, anomalies, items, *, as_of, client, store=None, components_by_id=None):
    """Run one of the three attribution jobs. This does not deploy a schedule."""
    if task_name not in _STAGE_NAMES:
        raise ValueError("未知任务")
    return attribute_all(
        anomalies,
        items,
        as_of=as_of,
        client=client,
        store=store,
        components_by_id=components_by_id,
        stage=task_name,
    )


def run_scheduled(
    when,
    *,
    anomalies=None,
    items=None,
    client=None,
    store=None,
    connection=None,
    clock=None,
    trade_date=None,
    params_version=None,
):
    """Run the job for this minute. Nothing is deployed, and no caller operation is substituted."""
    slot = job_slot(when)
    if slot is None:
        return None
    if anomalies is None:
        return {**slot, "recorded": False, "ran": False}
    if connection is None:
        rows = execute_stage(
            slot["task_name"],
            anomalies,
            items or [],
            as_of=when,
            client=client,
            store=store,
        )
        return {**slot, "recorded": False, "ran": True, "count": len(rows), "rows": rows}
    from inves_cog.perception.anomaly.service import run_recorded

    holder = {}

    def operation():
        holder["rows"] = execute_stage(
            slot["task_name"],
            anomalies,
            items or [],
            as_of=when,
            client=client,
            store=store,
        )
        rows = holder["rows"]
        if store is None:
            return len(rows)
        saved = [row for row in rows if row.get("saved")]
        if rows and not saved:
            detail = "；".join(row.get("degraded") or row.get("status") or "未保存" for row in rows)
            raise RuntimeError(detail or "未保存")
        return len(saved)

    row_id = run_recorded(
        connection,
        clock=clock,
        task_name=slot["task_name"],
        trade_date=trade_date,
        params_version=params_version,
        operation=operation,
    )
    rows = holder.get("rows") or []
    return {**slot, "recorded": True, "ran": True, "count": len(rows), "rows": rows, "job_id": row_id}


def adapt_m7(anomaly):
    """Close starts at the exchange open. Post starts at the exchange close."""
    session = anomaly.get("session")
    if anomaly.get("started_at") is not None or session not in {"close", "post"}:
        return anomaly
    trade_date = anomaly.get("trade_date")
    if trade_date is None:
        return anomaly
    bounds = regular_bounds(_calendar_day(trade_date))
    if bounds is None:
        return anomaly
    prepared = dict(anomaly)
    prepared["started_at"] = bounds[0] if session == "close" else bounds[1]
    return prepared


def _one(anomaly, items, *, as_of, client, store, components, stage):
    if anomaly.get("started_at") is None or "universe" not in anomaly:
        raise ValueError("异常缺少起点或范围")
    previous, rejected = _stored_report(anomaly, store, as_of) if stage is not None else (None, False)
    prior = None if rejected else _prior(anomaly, store)
    if prior is None and previous is not None and anomaly.get("universe") != "wide":
        prior = _report_prior(previous)
    if stage == "attribution_labels":
        return _labels(anomaly, previous, prior, as_of, store)
    visible = _retrieved(anomaly, items, as_of)
    reused = False
    if stage in {"attribution_candidates", "attribution_tracks"} and anomaly.get("universe") != "wide":
        claimed, candidates, claim_note, model_note, reused = _resume_analysis(anomaly, visible, previous, as_of)
        if not reused and stage == "attribution_candidates":
            claimed, claim_note = _claims(visible, client, anomaly.get("universe"))
            candidates, model_note = _candidates(anomaly, claimed, client)
    else:
        claimed, claim_note = _claims(visible, client, anomaly.get("universe"))
        candidates, model_note = _candidates(anomaly, claimed, client)
    candidates = _apply_score(candidates, anomaly, claimed, components)
    when = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
    due_on = earliest_deadline(
        anomaly.get("started_at") or anomaly.get("trade_date"),
        deadline_on=anomaly.get("deadline_on"),
        earnings_sessions=anomaly.get("earnings_sessions"),
        mechanism_sessions=anomaly.get("mechanism_sessions"),
    )
    state, history, deadline = _lifecycle(candidates, when, prior, anomaly, stage, as_of, due_on)
    impact = _impact(anomaly)
    channels = _channels(anomaly)
    report = _report(
        anomaly,
        candidates,
        claimed,
        "待分析" if model_note else None,
        impact,
        channels,
        deadline,
        deadline_on=due_on.isoformat() if due_on is not None else None,
    )
    report["lifecycle"] = state
    report["history"] = history
    if due_on is not None:
        report["deadline_on"] = due_on.isoformat()
    proven = bool(deadline and deadline.get("operating_impact_proven"))
    report["operating_impact_proven"] = proven
    if stage == "attribution_candidates" and anomaly.get("universe") != "wide":
        snapshot = (
            deepcopy(previous["stage_analysis"])
            if reused
            else _analysis_snapshot(anomaly, visible, claimed, candidates, as_of, claim_note, model_note)
        )
        if snapshot is not None:
            snapshot["candidate_rows_hash"] = _hash_input({"candidates": candidates})
            report["stage_analysis"] = snapshot
        report["analysis_reused"] = reused
    elif stage == "attribution_tracks" and anomaly.get("universe") != "wide":
        report["analysis_reused"] = reused
        report["analysis_as_of"] = (previous or {}).get("stage_analysis", {}).get("as_of")
        if reused:
            report["stage_analysis"] = deepcopy(previous["stage_analysis"])
            report["stage_analysis"]["candidate_rows_hash"] = _hash_input({"candidates": candidates})
        elif previous is not None:
            report["previous_candidates"] = deepcopy(previous.get("candidates") or [])
    hits, conclusion = _second_hits(anomaly, candidates, as_of)
    tracks = _track_rows(anomaly, state, stage, as_of)
    notes = [note for note in (claim_note, model_note) if note]
    if reused and notes:
        notes = ["沿用此前分析降级：" + "；".join(notes)]
    if stage is not None and notes:
        report["analysis_note"] = "；".join(notes)
    saved = False
    if store is not None:
        store.save(_bundle(anomaly, claimed, candidates, report, state, history, impact, hits, tracks, deadline))
        saved = True
    return {
        "anomaly_id": anomaly.get("anomaly_id"),
        "status": report["status"],
        "report": report,
        "lifecycle": state,
        "history": history,
        "degraded": "；".join(notes) if notes else None,
        "saved": saved,
        "operating_impact_proven": proven,
        "second_hit": conclusion,
        "tracks": tracks,
    }


def _stamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if isinstance(value, datetime) and value.tzinfo is not None else None


def _hash_input(value):
    def encode(part):
        if isinstance(part, (date, datetime)):
            return part.isoformat()
        raise TypeError("分析输入不能序列化")

    ready = json.loads(json.dumps(value, default=encode, ensure_ascii=False, allow_nan=False))
    return sha256(canonical_payload(ready).encode()).hexdigest()


def _analysis_binding(anomaly, visible):
    scope = candidate_payload(anomaly, [], [])["anomaly"]
    return {"anomaly": scope, "started_at": anomaly["started_at"], "visible": visible}


def _stored_report(anomaly, store, as_of):
    reader = getattr(store, "report", None)
    report = reader(anomaly["anomaly_id"]) if reader is not None else None
    if not isinstance(report, dict):
        return None, False
    if report.get("anomaly_id") not in {None, anomaly["anomaly_id"]}:
        return None, True
    snapshot = report.get("stage_analysis")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if snapshot and (
        snapshot.get("anomaly_id") != anomaly["anomaly_id"] or snapshot.get("universe") != anomaly["universe"]
    ):
        return None, True
    if snapshot.get("scope_hash") is not None and snapshot["scope_hash"] != _hash_input(_analysis_binding(anomaly, [])):
        return None, True
    created = _stamp(snapshot.get("as_of") or report.get("analysis_as_of"))
    now = _stamp(as_of)
    if snapshot and created is None or created is not None and (now is None or created > now):
        return None, True
    return deepcopy(report), False


def _report_prior(report):
    formed = report.get("deadline_outcome") is not None or report.get("closing_reason") is not None
    return {
        "lifecycle": report.get("lifecycle"),
        "history": list(report.get("history") or []),
        "deadline_outcome": report.get("deadline_outcome"),
        "closing_reason": report.get("closing_reason"),
        "unknowns": list(report.get("unknowns") or []),
        "fundamental": report.get("fundamental_standing") if formed else None,
        "operating_impact_proven": report.get("operating_impact_proven") if formed else None,
    }


def _analysis_snapshot(anomaly, visible, claimed, candidates, as_of, claim_note, model_note):
    now = _stamp(as_of)
    if now is None:
        return None
    try:
        return {
            "version": 1,
            "anomaly_id": anomaly["anomaly_id"],
            "universe": anomaly["universe"],
            "analysis_day": now.astimezone(_SHANGHAI).date().isoformat(),
            "as_of": now.isoformat(),
            "scope_hash": _hash_input(_analysis_binding(anomaly, [])),
            "input_hash": _hash_input(_analysis_binding(anomaly, visible)),
            "claim_payload_hash": _hash_input(claim_payload(visible)),
            "candidate_payload_hash": _hash_input(candidate_payload(anomaly, claimed, [])),
            "candidate_rows_hash": _hash_input({"candidates": candidates}),
            "claims": [{"info_id": item["info_id"], "claims": deepcopy(item.get("claims") or [])} for item in claimed],
            "claim_note": claim_note,
            "model_note": model_note,
        }
    except (TypeError, ValueError):
        return None


def _resume_analysis(anomaly, visible, previous, as_of):
    pending = (
        [dict(item) for item in visible],
        validate_candidates([], set(), _tickers(anomaly)),
        None,
        "候选待更新：无合格本日分析",
        False,
    )
    snapshot = (previous or {}).get("stage_analysis")
    now = _stamp(as_of)
    if not isinstance(snapshot, dict) or now is None:
        return pending
    created = _stamp(snapshot.get("as_of"))
    if (
        snapshot.get("version") != 1
        or snapshot.get("anomaly_id") != anomaly["anomaly_id"]
        or snapshot.get("universe") != anomaly["universe"]
    ):
        return pending
    if created is None or created > now or snapshot.get("analysis_day") != now.astimezone(_SHANGHAI).date().isoformat():
        return pending
    try:
        if snapshot.get("input_hash") != _hash_input(_analysis_binding(anomaly, visible)) or snapshot.get(
            "claim_payload_hash"
        ) != _hash_input(claim_payload(visible)):
            return pending
        by_id = read_claims({"items": snapshot.get("claims")})
        if set(by_id) != {item["info_id"] for item in visible}:
            return pending
        claimed = [{**item, "claims": by_id[item["info_id"]]} for item in visible]
        if snapshot.get("candidate_payload_hash") != _hash_input(candidate_payload(anomaly, claimed, [])):
            return pending
        rows = previous.get("candidates") or []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return pending
        if snapshot.get("candidate_rows_hash") != _hash_input({"candidates": rows}):
            return pending
        candidates = validate_candidates([row for row in rows if row.get("scored")], set(by_id), _tickers(anomaly))
        return claimed, candidates, snapshot.get("claim_note"), snapshot.get("model_note"), True
    except (TypeError, ValueError, KeyError):
        return pending


def _labels(anomaly, previous, prior, as_of, store):
    report = _report(anomaly, [], [], None, None, None, _carried_deadline(prior))
    if previous is not None:
        report.update(deepcopy(previous))
    if anomaly["universe"] == "wide":
        prior = None
        report.update({"status": "已记录", "candidates": [], "scope": [], "ticker_status": []})
    state = (prior or {}).get("lifecycle", report.get("lifecycle"))
    history = list((prior or {}).get("history", report.get("history")) or [])
    report["lifecycle"] = state
    report["history"] = history
    if prior is not None and (prior.get("deadline_outcome") is not None or prior.get("closing_reason") is not None):
        for key in ("deadline_outcome", "closing_reason", "unknowns", "operating_impact_proven"):
            report[key] = deepcopy(prior.get(key))
        report["fundamental_standing"] = prior.get("fundamental")
    report["labelled_as_of"] = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
    snapshot = report.get("stage_analysis")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    report["analysis_as_of"] = snapshot.get("as_of") or report.get("analysis_as_of")
    note = None
    if previous is None:
        note = "缺少此前分析报告，未形成新候选或结论"
    elif report["analysis_as_of"] is None:
        note = "旧报告缺少分析时点，仅继承已持久事实"
    elif report.get("analysis_note"):
        note = report["analysis_note"]
        if not note.startswith("沿用此前分析说明："):
            note = "沿用此前分析说明：" + note
    if note:
        report["analysis_note"] = note
    if store is not None:
        bundle = {"anomaly_id": anomaly["anomaly_id"], "universe": anomaly["universe"], "report": report}
        codes = [row for row in report.get("ticker_status") or [] if row.get("n_code")]
        if codes and anomaly["universe"] != "wide":
            bundle["ticker_status"] = codes
        store.save(bundle)
    return {
        "anomaly_id": anomaly["anomaly_id"],
        "status": report["status"],
        "report": report,
        "lifecycle": state,
        "history": history,
        "degraded": note,
        "saved": store is not None,
        "operating_impact_proven": report.get("operating_impact_proven", False),
        "second_hit": None,
        "tracks": [],
    }


def _claims(items, client, universe):
    if universe == "wide" or not items or client is None:
        return [dict(item) for item in items], None
    try:
        return attach_claims(items, client), None
    except ValueError as exc:
        if str(exc) == "结构不合格":
            return [dict(item) for item in items], "结构不合格"
        raise
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
    except ValueError as exc:
        if str(exc) == "结构不合格":
            return validate_candidates([], retrieved, universe), "结构不合格"
        raise
    except Exception:
        return validate_candidates([], retrieved, universe), "模型调用失败"


def _retrieved(anomaly, items, as_of):
    """Entity, graph, and approved-vector union, then the top 40 already in the window."""
    members = _member_names(anomaly)
    found = retrieval_entities(
        members,
        _basket_rows(anomaly),
        anomaly.get("edges") or [],
        anomaly.get("monitored") or [],
    )
    return shortlist(items, found["entities"], anomaly["started_at"], as_of)


def _apply_score(candidates, anomaly, items, overrides):
    updated = []
    for row in candidates:
        if not row.get("scored"):
            updated.append(row)
            continue
        components = _components(row, anomaly, items)
        components.update(_override(overrides, row.get("mechanism")))
        scored = evidence_score(components)
        copied = dict(row)
        copied["evidence"] = scored
        copied["score"] = scored["total"]
        copied["confidence"] = scored["confidence"]
        copied["fundamental"] = None
        updated.append(copied)
    return updated


def _components(candidate, anomaly, items):
    """Six evidence parts for this candidate. A part with no input stays missing."""
    components = {}
    cited = [item for item in items if item.get("info_id") in set(candidate.get("info_ids") or [])]
    published = _earliest(cited)
    start = anomaly.get("started_at")
    end = anomaly.get("ended_at")
    if published is not None and start is not None and (published < start or end is not None):
        components["time"] = time_alignment(published, start, end if end is not None else start)
    direction = candidate.get("direction") or anomaly.get("direction")
    members = anomaly.get("members") or []
    relations = anomaly.get("relations") or []
    if direction and members and relations:
        components["gradient"] = exposure_gradient(members, relations, direction=direction)
    expected, control = _residuals(candidate, anomaly)
    if expected and control:
        components["specificity"] = basket_specificity(expected, control)
    affected = [
        row.get("ticker") for row in candidate.get("affected") or [] if isinstance(row, dict) and row.get("ticker")
    ]
    events = [
        row.get("entity_id") for row in candidate.get("chain") or [] if isinstance(row, dict) and row.get("entity_id")
    ]
    if cited and affected and events:
        components["narrative"] = narrative_support(cited, events, affected)
    verdict = (anomaly.get("magnitude_by_mechanism") or {}).get(candidate.get("mechanism"))
    if verdict is not None:
        components["magnitude"] = magnitude_component(verdict)
    exclusion = alternative_exclusion(_alternative_members(candidate, anomaly))
    if exclusion is not None:
        components["alternatives"] = exclusion
    return components


def _override(overrides, mechanism):
    if not isinstance(overrides, dict):
        return {}
    nested = overrides.get(mechanism)
    if not isinstance(nested, dict):
        return {}
    return {key: value for key, value in nested.items() if key in _EVIDENCE}


def _residuals(candidate, anomaly):
    table = anomaly.get("basket_residuals") or {}
    expected = []
    for row in candidate.get("affected") or []:
        if not isinstance(row, dict):
            continue
        expected.extend(table.get(row.get("basket_id")) or [])
    control = []
    for basket in candidate.get("control_baskets") or []:
        control.extend(table.get(basket) or [])
    return expected, control


def _earliest(items):
    stamps = [item.get("published_at") for item in items if item.get("published_at") is not None]
    if not stamps:
        return None
    return min(stamps)


def _member_names(anomaly):
    names = []
    for member in anomaly.get("members") or []:
        if isinstance(member, dict):
            name = member.get("ticker") or member.get("entity_id")
        else:
            name = member
        if name and name not in names:
            names.append(name)
    return names


def _alternative_members(candidate, anomaly):
    """Anomaly members named by this candidate. An unmapped range stays missing."""
    by_name = {}
    for member in anomaly.get("members") or []:
        if not isinstance(member, dict):
            continue
        name = member.get("ticker") or member.get("entity_id")
        if name and name not in by_name:
            by_name[name] = member
    names = []
    for row in candidate.get("affected") or []:
        if not isinstance(row, dict):
            continue
        ticker = row.get("ticker")
        if ticker:
            if ticker not in by_name:
                return []
            names.append(ticker)
            continue
        basket = row.get("basket_id")
        if isinstance(basket, str) and basket:
            mapped = _basket_anomaly_members(anomaly, basket, by_name)
            if mapped is None:
                if not ticker:
                    return []
            else:
                names.extend(mapped)
    chosen = []
    for name in names:
        if name not in by_name:
            return []
        if name not in chosen:
            chosen.append(name)
    return [by_name[name] for name in chosen]


def _basket_anomaly_members(anomaly, basket_id, by_name):
    listed = []
    found = False
    for basket in _basket_rows(anomaly):
        if basket.get("basket_id") != basket_id:
            continue
        found = True
        for name in basket.get("members") or []:
            if isinstance(name, str):
                listed.append(name)
    for member in anomaly.get("members") or []:
        if isinstance(member, dict) and member.get("basket_id") == basket_id:
            found = True
            name = member.get("ticker") or member.get("entity_id")
            if isinstance(name, str):
                listed.append(name)
    if not found:
        return None
    chosen = []
    for name in listed:
        if name in by_name and name not in chosen:
            chosen.append(name)
    return chosen


def _basket_rows(anomaly):
    rows = anomaly.get("basket_members")
    if rows is None:
        rows = anomaly.get("baskets") or []
    return [row for row in rows if isinstance(row, dict)]


def _carried_deadline(prior):
    """A labels pass keeps a conclusion that was already formed. It does not form a new one."""
    if not isinstance(prior, dict):
        return None
    if all(prior.get(key) is None for key in ("deadline_outcome", "closing_reason", "fundamental")):
        return None
    return {
        "lifecycle": prior.get("lifecycle"),
        "deadline_outcome": prior.get("deadline_outcome"),
        "closing_reason": prior.get("closing_reason"),
        "fundamental": prior.get("fundamental"),
        "unknowns": list(prior.get("unknowns") or []),
        "operating_impact_proven": bool(prior.get("operating_impact_proven")),
    }


def _prior(anomaly, store):
    if store is not None:
        loaded = store.prior(f"evt-{anomaly['anomaly_id']}")
        if loaded is not None:
            return loaded
    carried = anomaly.get("prior_event")
    if isinstance(carried, dict) and carried.get("lifecycle"):
        return carried
    return None


def _lifecycle(candidates, when, prior, anomaly, stage, as_of, due_on):
    evidence_ids = []
    for row in candidates:
        if row.get("scored") and row.get("score") is not None and row["score"] >= 0.5:
            evidence_ids.extend(row.get("info_ids") or [])
    state = None if prior is None else prior.get("lifecycle")
    history = [] if prior is None else list(prior.get("history") or [])
    if stage == "attribution_labels":
        return state, history, _carried_deadline(prior)
    if state is None:
        state, history = transition(None, "已发现", history, when=when, trigger="异常", evidence_ids=[])
    if state == "已发现" and evidence_ids:
        state, history = transition(
            state,
            "假设中",
            history,
            when=when,
            trigger="证据分达到假设",
            evidence_ids=evidence_ids,
        )
    if stage in {None, "attribution_tracks"} and state == "假设中" and _market_ready(anomaly):
        state, history = transition(
            state,
            "市场确认",
            history,
            when=when,
            trigger="四项同时成立",
            evidence_ids=evidence_ids,
        )
        mechanism = _lead_mechanism(candidates)
        if mechanism in _FUNDAMENTAL:
            state, history = transition(
                state,
                "基本面核查中",
                history,
                when=when,
                trigger="进入基本面核查",
                evidence_ids=evidence_ids,
                mechanism=mechanism,
            )
    deadline = None
    missing_records = anomaly.get("operating_records") is None
    records = [] if missing_records else anomaly["operating_records"]
    if stage == "attribution_tracks" and state == "基本面核查中" and deadline_reached(due_on, as_of):
        unknowns = ("经营记录缺失",) if missing_records else ()
        verdict = operating_verdict(
            records,
            as_of=as_of,
            expected_direction=anomaly.get("direction"),
            unknowns=unknowns,
        )
        if verdict.confirmed():
            deadline = apply_deadline(verdict)
            state, history = transition(
                state,
                deadline["lifecycle"],
                history,
                when=when,
                trigger=deadline["closing_reason"],
                evidence_ids=evidence_ids,
            )
    return state, history, deadline


def _market_ready(anomaly):
    reading = anomaly.get("market_confirmation")
    if not isinstance(reading, dict):
        return False
    return market_confirmed(
        claim_time=reading.get("claim_time"),
        response=reading.get("response"),
        independent=reading.get("independent"),
        alternative=reading.get("alternative"),
    )


def _lead_mechanism(candidates):
    scored = [row for row in candidates if row.get("scored") and row.get("score") is not None]
    if not scored:
        return None
    return max(scored, key=lambda row: row["score"]).get("mechanism")


def _impact(anomaly):
    raw = anomaly.get("impact_inputs")
    if not isinstance(raw, dict):
        return None
    parts = decompose(
        raw["total"],
        raw.get("sum_delta_e"),
        raw.get("pe"),
        raw.get("market_cap"),
        raw.get("verdict"),
        raw.get("true_features"),
        raw.get("available_features"),
    )
    return {"total_residual": raw["total"], **parts}


def _channels(anomaly):
    payload = anomaly.get("magnitude_payload")
    if not isinstance(payload, dict):
        return None
    return implied_magnitude(payload)


def _second_hits(anomaly, candidates, as_of):
    events = anomaly.get("later_events") or []
    if not events:
        return [], None
    start = anomaly.get("started_at")
    fingerprints = []
    for candidate in candidates:
        fingerprint = prediction_fingerprint(candidate)
        if fingerprint:
            fingerprints.append((candidate, fingerprint))
    measured = []
    rows = []
    for event in events:
        outcome = _measured_hit(event, fingerprints, anomaly, start, as_of)
        if outcome is None:
            continue
        measured.append({**event, "outcome": outcome})
        rows.append(
            {
                "info_id": event["info_id"],
                "published_at": event.get("published_at"),
                "source_root": event.get("source_root"),
                "outcome": outcome,
                "expected_z": event.get("expected_z"),
                "control_z": event.get("control_z"),
            }
        )
    if not measured:
        return [], "未检验"
    return rows, second_hit_conclusion(measured, start)


def _measured_hit(event, fingerprints, anomaly, start, as_of):
    """A later page counts only when it was visible and matches the frozen fingerprint."""
    if not _later_visible(event, as_of):
        return None
    for candidate, fingerprint in fingerprints:
        if not later_matches_fingerprint(fingerprint, event, start):
            continue
        if event.get("mechanism") != candidate.get("mechanism"):
            continue
        direction = _expected_direction(candidate, fingerprint, anomaly, event)
        if direction is None or event.get("direction") not in {None, direction}:
            continue
        expected = {row.get("basket_id") for row in fingerprint.get("baskets") or []}
        if expected and event.get("basket_id") not in expected:
            continue
        controls = set(fingerprint.get("control_baskets") or [])
        named = event.get("control_basket")
        if controls and named not in controls:
            continue
        expected_z = event.get("expected_z")
        control_z = event.get("control_z")
        if expected_z is None or control_z is None:
            continue
        return classify_response(expected_z, control_z, direction=direction)
    return None


def _later_visible(event, as_of):
    published = event.get("published_at")
    seen = event.get("first_seen_at")
    if published is None or seen is None or as_of is None:
        return False
    return max(published, seen) <= as_of


def _expected_direction(candidate, fingerprint, anomaly, event):
    baskets = [row for row in fingerprint.get("baskets") or [] if isinstance(row, dict)]
    named = event.get("basket_id")
    if named:
        matched = [
            row.get("direction")
            for row in baskets
            if row.get("basket_id") == named and row.get("direction") in {"up", "down"}
        ]
        if len(set(matched)) == 1:
            return matched[0]
        return None
    directions = [row.get("direction") for row in baskets if row.get("direction") in {"up", "down"}]
    if len(set(directions)) == 1:
        return directions[0]
    if len(directions) > 1:
        return None
    for row in candidate.get("affected") or []:
        if isinstance(row, dict) and row.get("direction") in {"up", "down"}:
            return row["direction"]
    direction = anomaly.get("direction")
    return direction if direction in {"up", "down"} else None


def _completed_session(as_of):
    """The NYSE session that has already closed. A Beijing date is not that session."""
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        return None
    day = as_of.astimezone(_NEW_YORK).date()
    bounds = regular_bounds(day)
    if bounds is not None and as_of >= bounds[1]:
        return day
    cal = exchange(day.year)
    if trading_day(day):
        label = cal.previous_session(str(day))
    else:
        label = cal.date_to_session(str(day), direction="previous")
    return label.date()


def _track_rows(anomaly, state, stage=None, as_of=None):
    sessions = anomaly.get("sessions") or []
    if stage == "attribution_labels" and not sessions:
        return []
    if sessions:
        rows = []
        for row in sessions:
            rows.append(
                {
                    "trade_date": row["trade_date"],
                    "emotion": row.get("emotion") or "延续",
                    "capital": capital_state(row["sessions_elapsed"], row["cumulative"], row["first"]),
                    "fundamental": row.get("fundamental") or "待验证",
                }
            )
        return rows
    if state in {None, "已发现"} or not anomaly.get("trade_date"):
        return []
    emotion = "初现" if state == "假设中" else "延续"
    trade_date = anomaly["trade_date"]
    if stage == "attribution_tracks":
        session_day = _completed_session(as_of)
        if session_day is None or session_day < _calendar_day(trade_date):
            return []
        trade_date = session_day.isoformat()
    return [{"trade_date": trade_date, "emotion": emotion, "fundamental": "待验证"}]


def _report(anomaly, candidates, items, status, impact, channels, deadline, *, deadline_on=None):
    current = {key: value for key, value in anomaly.items() if key != "status"}
    if status:
        current["status"] = status
    sources = [{"info_id": item["info_id"], "role": item.get("role")} for item in items]
    return explanation_report(
        current,
        impact,
        candidates,
        sources,
        deadline,
        relations=anomaly.get("relations") or (),
        deadline_on=deadline_on,
        embeddings=anomaly.get("embeddings"),
        magnitude=channels,
        tracks_view=anomaly.get("tracks_view"),
    )


def _bundle(anomaly, items, candidates, report, state, history, impact, hits, tracks, deadline):
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
    if state not in {None, "已发现"}:
        linkage = {"event_id": f"evt-{anomaly['anomaly_id']}", "lifecycle": state, "history": history}
        if deadline is not None:
            linkage["deadline_outcome"] = deadline["deadline_outcome"]
            linkage["closing_reason"] = deadline["closing_reason"]
            linkage["unknowns"] = list(deadline.get("unknowns") or [])
        bundle["linkage"] = linkage
        if tracks:
            bundle["tracks"] = tracks
        if hits:
            bundle["second_hits"] = hits
        if impact is not None:
            bundle["impact"] = impact
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
