"""Six-part evidence score. Missing parts drop out and the remaining weights are rescaled."""

from inves_cog.perception.attribution.rules import m8_rules


def evidence_score(components, rules=None):
    weights = (rules or m8_rules())["evidence_weights"]
    available = {name: components[name] for name in weights if components.get(name) is not None}
    weight = sum(weights[name] for name in available)
    total = round(sum(weights[name] * available[name] for name in available) / weight, 6)
    if total >= 0.70:
        confidence = "高"
    elif total >= 0.50:
        confidence = "中"
    else:
        confidence = "低"
    return {"total": total, "confidence": confidence, "enters_hypothesis": total >= 0.5}


def time_alignment(published, session_start, session_end):
    if published < session_start:
        return 1.0
    if published <= session_end:
        return 0.7
    return 0.0
