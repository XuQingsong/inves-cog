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


_EXPOSURE_SCORE = {"直接": 3, "间接": 2, "概念关联": 1}
_OBSERVED = {"观察到", "有支持", "已确立"}


def basket_specificity(expected, control):
    """How far the expected basket moved past the control, scaled by 3. No control basket is missing."""
    if not expected or not control:
        return None
    gap = _mean_abs(expected) - _mean_abs(control)
    return min(1.0, max(0.0, gap / 3))


def narrative_support(items, event_entities, affected):
    """Share of independent roots that name both the event and an affected entity, capped at 1."""
    event = set(event_entities)
    names = set(affected)
    roots = set()
    for item in items:
        mentioned = set(item.get("entities") or []) | set(item.get("tickers") or [])
        root = item.get("source_root")
        if root and mentioned & event and mentioned & names:
            roots.add(root)
    return min(len(roots) / 5, 1.0)


def alternative_exclusion(members):
    """One minus the share of members with their own earnings, 8-K guidance, or rating change."""
    if not members:
        return None
    flagged = sum(1 for member in members if _own_news(member))
    return round(1 - flagged / len(members), 6)


def _mean_abs(values):
    return sum(abs(value) for value in values) / len(values)


def _own_news(member):
    return bool(member.get("earnings_reaction") or member.get("guidance_8k") or member.get("rating_change"))


def exposure_gradient(members, relations, *, direction):
    """Spearman of observed exposure and the move in the expected direction. Below three names is missing."""
    if direction not in {"up", "down"}:
        return None
    sign = 1.0 if direction == "up" else -1.0
    scores = _exposure_scores(relations)
    paired = []
    for member in members:
        ticker = member.get("ticker") if isinstance(member, dict) else member
        resid = member.get("resid_z") if isinstance(member, dict) else None
        if not ticker or resid is None:
            continue
        paired.append((scores.get(ticker, 0), sign * resid))
    if len(paired) < 3:
        return None
    rho = _spearman([row[0] for row in paired], [row[1] for row in paired])
    if rho is None:
        return None
    return max(0.0, round(rho, 6))


def _exposure_scores(relations):
    scores = {}
    for rel in relations:
        if rel.get("exit_reason") or rel.get("status") not in _OBSERVED:
            continue
        ticker = rel.get("ticker")
        if not ticker:
            continue
        scores[ticker] = max(scores.get(ticker, 0), _EXPOSURE_SCORE.get(rel.get("exposure"), 0))
    return scores


def _spearman(left, right):
    return _pearson(_ranks(left), _ranks(right))


def _ranks(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        rank = (start + end) / 2 + 1
        for index in range(start, end + 1):
            ranks[order[index]] = rank
        start = end + 1
    return ranks


def _pearson(left, right):
    count = len(left)
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    paired = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right, strict=True))
    spread_left = sum((x - mean_left) ** 2 for x in left) ** 0.5
    spread_right = sum((y - mean_right) ** 2 for y in right) ** 0.5
    if spread_left == 0 or spread_right == 0:
        return None
    return paired / (spread_left * spread_right)
