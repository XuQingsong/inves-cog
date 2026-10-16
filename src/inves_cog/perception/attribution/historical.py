"""Historical-case candidates. A missing recording is not a successful call."""

import hashlib
from pathlib import Path

from inves_cog.llm.client import canonical_payload
from inves_cog.perception.attribution.cases import openai_cover, openai_labels
from inves_cog.perception.attribution.manual import historical_case
from inves_cog.perception.attribution.propose import candidate_payload, propose_candidates


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
        "closes_case": not missing,
        "missing": missing,
        "candidates": candidates,
        "sources": [item["info_id"] for item in items],
    }


def recording_path(task, payload, root):
    digest = hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
    return Path(root) / task / f"{digest}.json"


def candidate_capture(anomaly, leads, read_on, root):
    items = retrieval_items(leads, anomaly["trade_date"], read_on)
    payload = candidate_payload(anomaly, items, [])
    return recording_path("anomaly_candidates", payload, root)


def _cited(candidates):
    return [info_id for row in candidates if row.get("scored") for info_id in row.get("info_ids") or []]


def _missing(anomaly, leads, items, candidates):
    kind = anomaly.get("case_kind")
    cited = _cited(candidates)
    if kind == "r1_release":
        return _r1_missing(anomaly, cited)
    if kind == "openai_arr":
        return _openai_missing(items, cited)
    if kind == "muse_rank":
        return _muse_missing(anomaly, leads, cited)
    if kind == "toshiba":
        return _toshiba_missing(items, cited)
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


def _r1_missing(anomaly, cited):
    missing = []
    if not cited:
        missing.append("候选未引用发布材料")
    baskets = " ".join(anomaly.get("baskets") or [])
    if "加速" not in baskets:
        missing.append("受影响篮子未含 AI 加速芯片")
    return missing


def _openai_missing(items, cited):
    by_id = {item["info_id"]: item for item in items}
    ranked = [{"labels": openai_labels(by_id[info_id]["headline"])} for info_id in cited if info_id in by_id]
    if openai_cover(ranked):
        return []
    return ["前 4 名未含至少 3 类"]


def _toshiba_missing(items, cited):
    by_id = {item["info_id"]: item for item in items}
    for info_id in cited:
        headline = (by_id.get(info_id) or {}).get("headline", "").lower()
        if "toshiba" in headline and "disk" in headline:
            return []
    return ["日经扩产原文未冻结"]


def _muse_missing(anomaly, leads, cited):
    missing = []
    if not cited:
        missing.append("候选未引用登顶材料")
    members = {member["ticker"] for member in anomaly.get("members") or []}
    baskets = " ".join(anomaly.get("baskets") or [])
    if "META" not in members and "CPU" not in baskets:
        missing.append("受影响范围未含 CPU 或 META")
    proven = any(lead.get("before_open") is True and lead.get("published_precision") == "minute" for lead in leads)
    if not proven:
        missing.append("不能证明早于开盘")
    return missing
