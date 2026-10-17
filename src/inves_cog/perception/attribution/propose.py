"""Candidate proposals. A wide anomaly is stored without asking the model."""

from inves_cog.perception.attribution.candidates import validate_candidates

MECHANISMS = {"供给", "需求", "竞争", "客户融资", "估值倍数"}
_ANOMALY_KEYS = ("anomaly_id", "trade_date", "session", "baskets", "members", "direction", "universe")
_FORBIDDEN = ("score", "confidence", "fundamental", "evidence", "operating_impact_proven", "enters_hypothesis")


def candidate_output():
    """Return schema carried in the payload. The model does not decide scores or conclusions."""
    return {
        "candidates": {
            "max": 5,
            "mechanism": sorted(MECHANISMS),
            "chain": [{"entity_id": "string", "new": "boolean"}],
            "affected": [{"basket_id": "string", "ticker": "string", "direction": ["up", "down"]}],
            "control_baskets": ["string"],
            "info_ids": ["string"],
            "direction": ["up", "down"],
            "forbidden": list(_FORBIDDEN),
        }
    }


def candidate_payload(anomaly, items, neighbors):
    return {
        "anomaly": {key: anomaly[key] for key in _ANOMALY_KEYS if key in anomaly},
        "items": [_item_view(item) for item in items[:40]],
        "neighbors": neighbors,
        "output": candidate_output(),
    }


def _item_view(item):
    published = item.get("published_at")
    if hasattr(published, "isoformat"):
        published = published.isoformat()
    return {
        "info_id": item["info_id"],
        "published_at": published,
        "source_level": item.get("source_level"),
        "headline": item.get("headline"),
        "summary": item.get("summary"),
        "role": item.get("role"),
        "claims": item.get("claims") or [],
    }


_NOT_OPERATING = {"price", "social_heat", "second_hit", "consensus", "flow"}
_REASONS = (
    "持仓的经营证伪或风险越限",
    "直接量化的经营变化",
    "异常中的新解释",
    "可能改变产业关系的新机制",
    "普通重复背景",
)


def review_queue(items):
    """Order the review budget. Authenticity does not set the rank, and a level-1 source is still checked."""
    if items is None:
        return None
    ordered = []
    for index, row in enumerate(items):
        rank, reason = _review_rank(row)
        ordered.append(
            (
                rank,
                index,
                {
                    "info_id": row.get("info_id"),
                    "rank": rank,
                    "reason": reason,
                    "must_verify": row.get("source_level") == 1,
                },
            )
        )
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _review_rank(row):
    held = row.get("held") is True
    if held and (row.get("falsified") is True or row.get("risk_breach") is True):
        return 1, _REASONS[0]
    if row.get("quantity") is not None and row.get("kind") not in _NOT_OPERATING:
        return 2, _REASONS[1]
    if row.get("anomaly_id") and row.get("reprint") is not True:
        return 3, _REASONS[2]
    new_edge = row.get("new_mechanism") is True or (
        row.get("mechanism") in MECHANISMS and row.get("relation_status") == "候选"
    )
    if new_edge and row.get("reprint") is not True:
        return 4, _REASONS[3]
    return 5, _REASONS[4]


def research_order(items):
    """Four research tiers. A candidate is not recent unless it is already marked recent."""
    if items is None:
        return None
    ordered = []
    for index, row in enumerate(items):
        rank, reason = _research_rank(row)
        ordered.append(
            (
                rank,
                index,
                {
                    "info_id": row.get("info_id"),
                    "rank": rank,
                    "reason": reason,
                    "operating_evidence": False,
                    "fundamental_standing": None,
                },
            )
        )
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _research_rank(row):
    if row.get("held") is True and row.get("risk") is True:
        return 1, "持仓风险"
    if row.get("candidate") is True and row.get("recent") is True:
        return 2, "近期候选"
    if row.get("driver_link") is True:
        return 3, "可改变驱动因子的关键环节"
    if row.get("unknown_anomaly") is True:
        return 4, "重大未知异常"
    return 5, None


def propose_candidates(anomaly, items, neighbors, client, universe):
    if anomaly.get("universe") == "wide":
        return []
    if not items:
        return validate_candidates([], set(), universe)
    result = client.call("anomaly_candidates", candidate_payload(anomaly, items, neighbors))
    raw = read_candidates(result)
    return validate_candidates(raw, {item["info_id"] for item in items}, universe)


def read_candidates(result):
    """Keep structurally valid candidates. A bad envelope is an explicit degrade."""
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        raise ValueError("结构不合格")
    rows = []
    for row in result["candidates"]:
        parsed = _candidate_row(row)
        if parsed is not None:
            rows.append(parsed)
    return rows[:5]


def _candidate_row(row):
    if not isinstance(row, dict) or row.get("mechanism") not in MECHANISMS:
        return None
    info_ids = row.get("info_ids")
    if not isinstance(info_ids, list) or any(not isinstance(item, str) or not item for item in info_ids):
        return None
    if "chain" in row and not isinstance(row.get("chain"), list):
        return None
    if "affected" in row and not isinstance(row.get("affected"), list):
        return None
    if "control_baskets" in row and not isinstance(row.get("control_baskets"), list):
        return None
    parsed = {
        "mechanism": row["mechanism"],
        "info_ids": list(info_ids),
        "chain": _chain(row.get("chain") or []),
        "affected": _affected_rows(row.get("affected") or []),
        "control_baskets": [item for item in (row.get("control_baskets") or []) if isinstance(item, str)],
    }
    if row.get("direction") in {"up", "down"}:
        parsed["direction"] = row["direction"]
    return parsed


def _chain(rows):
    kept = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("entity_id"), str):
            continue
        item = {"entity_id": row["entity_id"]}
        if isinstance(row.get("new"), bool):
            item["new"] = row["new"]
        kept.append(item)
    return kept


def _affected_rows(rows):
    kept = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("ticker"), str):
            continue
        item = {"ticker": row["ticker"]}
        if isinstance(row.get("basket_id"), str):
            item["basket_id"] = row["basket_id"]
        if row.get("direction") in {"up", "down"}:
            item["direction"] = row["direction"]
        kept.append(item)
    return kept
