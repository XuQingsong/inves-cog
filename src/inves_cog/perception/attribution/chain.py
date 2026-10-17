"""Run one attribution pass. A failed anomaly does not stop the next one.

The model may propose a mechanism. Scores, lifecycle, and the report come
from the rules. This module does not open a database URL and does not deploy
the morning schedule.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import regular_bounds
from inves_cog.perception.attribution.candidates import market_confirmed, validate_candidates
from inves_cog.perception.attribution.claims import attach_claims
from inves_cog.perception.attribution.evidence import (
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
from inves_cog.perception.attribution.propose import propose_candidates
from inves_cog.perception.attribution.replay import replay_mode
from inves_cog.perception.attribution.report import explanation_report
from inves_cog.perception.attribution.retrieve import retrieval_entities, retrieval_mode, shortlist
from inves_cog.perception.attribution.second_hit import second_hit_conclusion
from inves_cog.perception.attribution.tracks import apply_deadline, capital_state

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
        return len(holder["rows"])

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
    """A close or post M7 object starts at the exchange close. Other sessions stay untouched."""
    if anomaly.get("started_at") is not None or anomaly.get("session") not in {"close", "post"}:
        return anomaly
    trade_date = anomaly.get("trade_date")
    if trade_date is None:
        return anomaly
    bounds = regular_bounds(_calendar_day(trade_date))
    if bounds is None:
        return anomaly
    prepared = dict(anomaly)
    prepared["started_at"] = bounds[1]
    return prepared


def _one(anomaly, items, *, as_of, client, store, components, stage):
    if anomaly.get("started_at") is None or "universe" not in anomaly:
        raise ValueError("异常缺少起点或范围")
    visible = _retrieved(anomaly, items, as_of)
    claimed, claim_note = _claims(visible, client, anomaly.get("universe"))
    candidates, model_note = _candidates(anomaly, claimed, client)
    candidates = _apply_score(candidates, anomaly, claimed, components)
    when = as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)
    prior = _prior(anomaly, store)
    state, history, deadline = _lifecycle(candidates, when, prior, anomaly, stage, as_of)
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
    )
    report["lifecycle"] = state
    report["history"] = history
    proven = bool(deadline and deadline.get("operating_impact_proven"))
    report["operating_impact_proven"] = proven
    hits, conclusion = _second_hits(anomaly)
    tracks = _track_rows(anomaly, state)
    saved = False
    if store is not None:
        store.save(_bundle(anomaly, claimed, candidates, report, state, history, impact, hits, tracks, deadline))
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
        "operating_impact_proven": proven,
        "second_hit": conclusion,
        "tracks": tracks,
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


def _basket_rows(anomaly):
    rows = anomaly.get("basket_members")
    if rows is None:
        rows = anomaly.get("baskets") or []
    return [row for row in rows if isinstance(row, dict)]


def _prior(anomaly, store):
    if store is not None:
        loaded = store.prior(f"evt-{anomaly['anomaly_id']}")
        if loaded is not None:
            return loaded
    carried = anomaly.get("prior_event")
    if isinstance(carried, dict) and carried.get("lifecycle"):
        return carried
    return None


def _lifecycle(candidates, when, prior, anomaly, stage, as_of):
    evidence_ids = []
    for row in candidates:
        if row.get("scored") and row.get("score") is not None and row["score"] >= 0.5:
            evidence_ids.extend(row.get("info_ids") or [])
    state = None if prior is None else prior.get("lifecycle")
    history = [] if prior is None else list(prior.get("history") or [])
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
    if stage != "attribution_candidates" and state == "假设中" and _market_ready(anomaly):
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
    records = anomaly.get("operating_records")
    if stage == "attribution_labels" and state == "基本面核查中" and records is not None:
        verdict = operating_verdict(records, as_of=as_of, expected_direction=anomaly.get("direction"))
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


def _second_hits(anomaly):
    events = anomaly.get("later_events") or []
    if not events:
        return [], None
    start = anomaly.get("started_at")
    conclusion = second_hit_conclusion(events, start)
    rows = []
    for event in events:
        published = event.get("published_at")
        if start is not None and (published is None or published <= start):
            continue
        rows.append(
            {
                "info_id": event["info_id"],
                "published_at": published,
                "source_root": event.get("source_root"),
                "outcome": event.get("outcome"),
                "expected_z": event.get("expected_z"),
                "control_z": event.get("control_z"),
            }
        )
    return rows, conclusion


def _track_rows(anomaly, state):
    sessions = anomaly.get("sessions") or []
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
    return [{"trade_date": anomaly["trade_date"], "emotion": emotion, "fundamental": "待验证"}]


def _report(anomaly, candidates, items, status, impact, channels, deadline):
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
