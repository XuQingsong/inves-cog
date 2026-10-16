"""Candidate proposals. A wide anomaly is stored without asking the model."""

from inves_cog.perception.attribution.candidates import validate_candidates

MECHANISMS = {"供给", "需求", "竞争", "客户融资", "估值倍数"}
_ANOMALY_KEYS = ("anomaly_id", "trade_date", "session", "baskets", "members", "direction", "universe")


def candidate_payload(anomaly, items, neighbors):
    return {
        "anomaly": {key: anomaly[key] for key in _ANOMALY_KEYS if key in anomaly},
        "items": [_item_view(item) for item in items[:40]],
        "neighbors": neighbors,
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


def propose_candidates(anomaly, items, neighbors, client, universe):
    if anomaly.get("universe") == "wide":
        return []
    if not items:
        return validate_candidates([], set(), universe)
    result = client.call("anomaly_candidates", candidate_payload(anomaly, items, neighbors))
    raw = [row for row in result.get("candidates") or [] if row.get("mechanism") in MECHANISMS][:5]
    return validate_candidates(raw, {item["info_id"] for item in items}, universe)
