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


def propose_candidates(anomaly, items, neighbors, client, universe):
    if anomaly.get("universe") == "wide":
        return []
    result = client.call("anomaly_candidates", candidate_payload(anomaly, items, neighbors))
    raw = [row for row in result.get("candidates") or [] if row.get("mechanism") in MECHANISMS][:5]
    return validate_candidates(raw, {item["info_id"] for item in items}, universe)
