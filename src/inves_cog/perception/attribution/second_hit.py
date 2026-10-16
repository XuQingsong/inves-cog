"""Later information on the same narrative. One source root counts once, and only on the market layer."""


def classify_response(expected_z, control_z):
    if expected_z >= 1 and abs(control_z) < 1:
        return "命中"
    if expected_z <= -1:
        return "反证"
    return "无响应"


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
