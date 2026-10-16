"""Later information on the same narrative. One source root counts once, and only on the market layer."""


def classify_response(expected_z, control_z, *, direction):
    """A hit matches the expected direction. The control basket must stay inside 1 sigma."""
    if direction not in {"up", "down"}:
        raise ValueError("方向只接受 up 或 down")
    aligned = expected_z >= 1 if direction == "up" else expected_z <= -1
    opposed = expected_z <= -1 if direction == "up" else expected_z >= 1
    if aligned and abs(control_z) < 1:
        return "命中"
    if opposed:
        return "反证"
    return "无响应"


def prediction_fingerprint(candidate):
    """A medium or high market score records the fingerprint. It stays on the market layer."""
    if candidate.get("scored") is False or not _at_least_medium(candidate):
        return None
    return {
        "entities": _chain_entities(candidate),
        "baskets": _expected_baskets(candidate),
        "control_baskets": list(candidate.get("control_baskets") or []),
        "layer": "市场",
    }


def later_matches_fingerprint(fingerprint, item, anomaly_start):
    """A later page counts only when it shares an entity and was published after the start."""
    published = None if item is None else item.get("published_at")
    if not fingerprint or published is None or published <= anomaly_start:
        return False
    linked = set(fingerprint.get("entities") or [])
    return bool(linked & set(item.get("entities") or []))


def _at_least_medium(candidate):
    confidence = candidate.get("confidence")
    if confidence in {"高", "中"}:
        return True
    if confidence == "低":
        return False
    score = candidate.get("score")
    return score is not None and score >= 0.5


def _chain_entities(candidate):
    found = []
    for row in candidate.get("chain") or []:
        entity = row.get("entity_id")
        if entity and entity not in found:
            found.append(entity)
    return found


def _expected_baskets(candidate):
    found = []
    for row in candidate.get("affected") or []:
        basket = row.get("basket_id")
        if not basket:
            continue
        item = {"basket_id": basket, "direction": row.get("direction")}
        if item not in found:
            found.append(item)
    return found


def _seen_before_response(event):
    """A page pulled from the later price move counts only if it was already on file."""
    if not event.get("from_price_anomaly"):
        return True
    seen = event.get("first_seen_at")
    response_at = event.get("response_at")
    if seen is None or response_at is None:
        return False
    return seen < response_at


def later_event(published_at, anomaly_start, *, source_root, outcome=None):
    """A later page is only eligible. Without a measured response it stays untested."""
    if published_at <= anomaly_start:
        return {"eligible": False, "conclusion": "未检验"}
    if outcome is None:
        return {"eligible": True, "conclusion": "未检验"}
    event = {"source_root": source_root, "published_at": published_at, "outcome": outcome}
    return {"eligible": True, "conclusion": second_hit_conclusion([event], anomaly_start)}


def second_hit_conclusion(events, anomaly_start=None):
    seen = set()
    outcomes = []
    for event in events:
        published = event.get("published_at")
        if anomaly_start is not None and (published is None or published <= anomaly_start):
            continue
        if not _seen_before_response(event):
            continue
        root = event["source_root"]
        if root in seen:
            continue
        seen.add(root)
        outcomes.append(event["outcome"])
    if not outcomes:
        return "未检验"
    quiet = 0
    for outcome in outcomes:
        quiet = quiet + 1 if outcome == "无响应" else 0
        if quiet >= 2:
            return "否定"
    if outcomes.count("反证") >= 1:
        return "否定"
    if outcomes.count("命中") >= 1:
        return "确认"
    return "未检验"
