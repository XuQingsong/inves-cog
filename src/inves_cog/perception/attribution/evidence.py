"""Six-part evidence score. Missing parts drop out and the remaining weights are rescaled."""

from datetime import datetime

from inves_cog.perception.attribution.rules import m8_rules


def evidence_score(components, rules=None):
    weights = (rules or m8_rules())["evidence_weights"]
    components = components or {}
    available = {name: components[name] for name in weights if components.get(name) is not None}
    weight = sum(weights[name] for name in available)
    if weight == 0:
        return {"total": None, "confidence": None, "enters_hypothesis": False}
    total = round(sum(weights[name] * available[name] for name in available) / weight, 6)
    if total >= 0.70:
        confidence = "高"
    elif total >= 0.50:
        confidence = "中"
    else:
        confidence = "低"
    return {"total": total, "confidence": confidence, "enters_hypothesis": total >= 0.5}


_MAGNITUDE = {"相容": 1.0, "部分相容": 0.6, "不相容": 0.2}


def magnitude_component(verdict):
    """An untested channel stays missing. An incompatible verdict is not an emotion label."""
    return _MAGNITUDE.get(verdict)


def time_alignment(published, session_start, session_end):
    if published < session_start:
        return 1.0
    if published <= session_end:
        return 0.7
    return 0.0


def bounded_time_alignment(items, session_start, session_end=None):
    """Score the earliest cited publication only when all possible times agree.

    An interval remains an interval. Unknown publication time can make the
    earliest time uncertain; a known pre-start publication already proves that
    the earliest one precedes the start. This says nothing about first_seen.
    """
    start = _publication_stamp(session_start)
    end = _publication_stamp(session_end)
    if start is None or not items:
        return None
    bounds = [_publication_bounds(item) for item in items]
    known = [bound for bound in bounds if bound is not None]
    if not known:
        return None
    try:
        upper = min(bound[1] for bound in known)
        if upper < start:
            return 1.0
        if len(known) != len(bounds) or end is None or end < start:
            return None
        lower = min(bound[0] for bound in known)
        scores = {time_alignment(stamp, start, end) for stamp in (lower, upper)}
    except TypeError:  # Mixed naive/aware times are not a usable comparison.
        return None
    return scores.pop() if len(scores) == 1 else None


def _publication_stamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value)
        except ValueError:
            return None
        return stamp if stamp.tzinfo is not None else None
    return None


def _publication_bounds(item):
    exact = _publication_stamp(item.get("published_at"))
    if exact is not None:
        return exact, exact
    interval = item.get("published_interval")
    if not isinstance(interval, dict):
        return None
    lower = _publication_stamp(interval.get("earliest_utc"))
    upper = _publication_stamp(interval.get("latest_utc"))
    try:
        if lower is not None and upper is not None and lower <= upper:
            return lower, upper
    except TypeError:
        pass
    return None


def later_report(timing):
    """A report after the start can explain later spread. It cannot explain the drop already underway."""
    if timing is None:
        return None
    published = timing.get("published_at")
    start = timing.get("anomaly_start")
    if published is None or start is None:
        return None
    late = published > start
    return {
        "explains_prior_drop": False if late else None,
        "explains_later_spread": True if late else None,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


_EXPOSURE_SCORE = {"直接": 3, "间接": 2, "概念关联": 1}
_OBSERVED = {"观察到", "有支持", "已确立"}


def basket_specificity(expected, control):
    """How far the expected basket moved past the control, scaled by 3. No control basket is missing."""
    if not expected or not control:
        return None
    gap = _mean_abs(expected) - _mean_abs(control)
    return min(1.0, max(0.0, gap / 3))


def narrative_support(items, event_entities, affected):
    """Independent co-mention roots. Missing tags or roots are not a checked absence."""
    event = set(event_entities)
    names = set(affected)
    if not event or not names:
        return None
    roots = set()
    uncertain_roots = set()
    unknown_root = False
    for item in items:
        tags = [item.get(key) for key in ("entities", "tickers") if item.get(key) is not None]
        known_tags = bool(tags) and all(
            isinstance(value, list) and all(isinstance(name, str) for name in value) for value in tags
        )
        root = item.get("source_root")
        root = root if isinstance(root, str) and root.strip() else None
        if not known_tags:
            if root:
                uncertain_roots.add(root)
            else:
                unknown_root = True
            continue
        mentioned = {name for value in tags for name in value}
        if mentioned & event and mentioned & names:
            if root:
                roots.add(root)
            else:
                unknown_root = True
    if len(roots) >= 5:
        return 1.0
    if unknown_root or uncertain_roots - roots:
        return None
    return len(roots) / 5


_OWN_FLAGS = ("earnings_reaction", "guidance_8k", "rating_change")


def alternative_exclusion(members):
    """One minus the share with their own earnings, 8-K, or rating change. An unknown member stays missing."""
    if not members:
        return None
    flagged = []
    for member in members:
        own = _own_news(member)
        if own is None:
            return None
        flagged.append(own)
    return round(1 - sum(flagged) / len(flagged), 6)


def _mean_abs(values):
    return sum(abs(value) for value in values) / len(values)


def _own_news(member):
    """True is an own event. All three explicit false means none. Anything else is unknown."""
    if not isinstance(member, dict):
        return None
    flags = [member.get(name) for name in _OWN_FLAGS]
    if any(flag is True for flag in flags):
        return True
    if all(flag is False for flag in flags):
        return False
    return None


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
