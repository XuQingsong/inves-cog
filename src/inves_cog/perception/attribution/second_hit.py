"""Later information on the same narrative. One source root counts once, and only on the market layer."""


def classify_response(expected_z, control_z):
    if expected_z >= 1 and abs(control_z) < 1:
        return "命中"
    if expected_z <= -1:
        return "反证"
    return "无响应"


def second_hit_conclusion(events):
    seen = set()
    outcomes = []
    for event in events:
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
