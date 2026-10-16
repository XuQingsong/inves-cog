"""Historical-case candidates. A missing recording is not a successful call."""

import hashlib
from pathlib import Path

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.cases import muse_chart, openai_cover, openai_labels, r1_or_store
from inves_cog.perception.attribution.manual import historical_case, open_relation
from inves_cog.perception.attribution.propose import candidate_payload, propose_candidates
from inves_cog.perception.attribution.report import type_candidates


def retrieval_items(leads, anomaly_on, read_on):
    items = []
    for lead in leads:
        decision = historical_case(lead, anomaly_on, read_on)
        if not decision["usable"]:
            continue
        item = {
            "info_id": lead["id"],
            "published_at": lead["published_on"],
            "headline": lead.get("excerpt") or "",
            "summary": lead.get("excerpt") or "",
            "role": decision["role"],
        }
        if lead.get("source_level") is not None:
            item["source_level"] = lead["source_level"]
        if lead.get("source_root"):
            item["source_root"] = lead["source_root"]
        items.append(item)
    return items


def historical_report(anomaly, leads, read_on, client):
    items = retrieval_items(leads, anomaly["trade_date"], read_on)
    members = {member["ticker"] for member in anomaly.get("members") or [] if member.get("ticker")}
    candidates = propose_candidates(anomaly, items, [], client, members)
    missing = _missing(anomaly, leads, items, candidates)
    return {
        "anomaly_id": anomaly["anomaly_id"],
        "evidence_mode": "后补录历史案例",
        "collected_then": False,
        "vectors_then": False,
        "closes_ac_m8_06": False,
        "closes_case": False,
        "missing": missing,
        "candidates": candidates,
        "sources": [item["info_id"] for item in items],
        "type_candidates": type_candidates(candidates, anomaly.get("type_candidates_prelim") or ()),
        "valuation": "不变 / 待基本面轨道",
        "trading": None,
    }


def recording_path(task, payload, root):
    digest = hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
    return Path(root) / task / f"{digest}.json"


def candidate_capture(anomaly, leads, read_on, root):
    items = retrieval_items(leads, anomaly["trade_date"], read_on)
    payload = candidate_payload(anomaly, items, [])
    return recording_path("anomaly_candidates", payload, root)


def _ranked(candidates, limit):
    return [row for row in candidates if row.get("scored")][:limit]


def _missing(anomaly, leads, items, candidates):
    kind = anomaly.get("case_kind")
    if kind == "r1_release":
        return _r1_missing(anomaly, items, candidates)
    if kind == "openai_arr":
        return _openai_missing(items, candidates)
    if kind == "muse_rank":
        return _muse_missing(anomaly, items, candidates)
    if kind == "toshiba":
        return _toshiba_missing(items, candidates)
    return ["案例种类未知"]


def headline_lead(row):
    return {
        "id": row["info_id"],
        "kind": row["kind"],
        "case_id": row["case_id"],
        "published_on": row["published_at"][:10],
        "published_precision": "minute",
        "excerpt": row["headline"],
        "source_level": row["source_level"],
    }


def _headline(items, info_id):
    by_id = {item["info_id"]: item for item in items}
    return by_id.get(info_id) or {}


def _r1_source(items, info_id):
    return r1_or_store(_headline(items, info_id).get("headline") or "")


def _r1_linked(anomaly, candidate):
    baskets = " ".join(anomaly.get("baskets") or [])
    members = {member["ticker"] for member in anomaly.get("members") or [] if member.get("ticker")}
    affected = {row.get("ticker") for row in candidate.get("affected") or [] if row.get("ticker")}
    return "加速" in baskets and bool(members & affected)


def _r1_missing(anomaly, items, candidates):
    missing = []
    linked = False
    cited = False
    for row in _ranked(candidates, 3):
        if not any(_r1_source(items, info_id) for info_id in row.get("info_ids") or []):
            continue
        cited = True
        linked = linked or _r1_linked(anomaly, row)
    if not cited:
        missing.append("候选未引用发布材料")
    if not linked:
        missing.append("候选未连接加速芯片范围")
    return missing


def _factor_labels(item):
    labels = set(openai_labels(item.get("headline") or ""))
    background = item.get("role") == "背景" and item.get("source_root") in {"reuters", "ft"}
    if "arr_background" in labels and not background:
        labels.discard("arr_background")
    return labels


def _openai_missing(items, candidates):
    ranked = []
    for row in _ranked(candidates, 4):
        labels = set()
        for info_id in row.get("info_ids") or []:
            labels |= _factor_labels(_headline(items, info_id))
        ranked.append({"labels": labels})
    if openai_cover(ranked):
        return []
    return ["前 4 名未含至少 3 类"]


def _toshiba_disk(items, info_id):
    headline = (_headline(items, info_id).get("headline") or "").lower()
    return "toshiba" in headline and "disk" in headline


def _toshiba_missing(items, candidates):
    ranked = _ranked(candidates, 3)
    cited = [info_id for row in ranked for info_id in row.get("info_ids") or []]
    supply = any(
        row.get("mechanism") == "供给" and any(_toshiba_disk(items, info_id) for info_id in row.get("info_ids") or [])
        for row in ranked
    )
    if supply:
        return []
    if any(_toshiba_disk(items, info_id) for info_id in cited):
        return ["机制不是供给"]
    return ["日经扩产原文未冻结"]


def _muse_charts(items, candidates):
    found = []
    for row in _ranked(candidates, 3):
        for info_id in row.get("info_ids") or []:
            item = _headline(items, info_id)
            if muse_chart(item.get("headline") or ""):
                found.append(item)
    return found


def _muse_missing(anomaly, items, candidates):
    missing = []
    charts = _muse_charts(items, candidates)
    if not charts:
        missing.append("候选未引用登顶材料")
    members = {member["ticker"] for member in anomaly.get("members") or []}
    baskets = " ".join(anomaly.get("baskets") or [])
    if "META" not in members and "CPU" not in baskets:
        missing.append("受影响范围未含 CPU 或 META")
    if charts:
        relations = {open_relation(item.get("published_at"), anomaly["trade_date"]) for item in charts}
        if "早于开盘" not in relations:
            missing.append("晚于开盘" if relations == {"晚于开盘"} else "不能证明早于开盘")
    return missing
