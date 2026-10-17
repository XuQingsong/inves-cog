"""Capital track and the deadline clock. A reprint does not start the clock again."""

import math


def capital_state(sessions_elapsed, cumulative, first):
    if sessions_elapsed <= 1:
        return "冲击中"
    if first not in (None, 0) and cumulative * first > 0 and abs(cumulative) >= 1.2 * abs(first):
        return "延续"
    ratio = 0.0 if first in (None, 0) else 1 - cumulative / first
    if ratio >= 1.0:
        return "反转"
    if ratio >= 0.5:
        return "已消化"
    return "消化中"


def retrace_windows(reading):
    """Report the 5-day and 20-day retrace. A zero first residual has no percentage."""
    if reading is None:
        return None
    first = reading.get("first")
    return {
        "retrace_5": _window_retrace(reading, "day_5", first),
        "retrace_20": _window_retrace(reading, "day_20", first),
        "capital_state": None,
        "fundamental_standing": None,
        "operating_evidence": False,
        "valuation": None,
    }


def _window_retrace(reading, key, first):
    if key not in reading:
        return None
    cumulative = reading.get(key)
    if not _finite(cumulative) or not _finite(first) or first == 0:
        return None
    return 1 - cumulative / first


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def deadline_offset(earnings_sessions, mechanism_sessions, cap=20):
    candidates = [cap]
    if earnings_sessions is not None:
        candidates.append(earnings_sessions)
    if mechanism_sessions is not None:
        candidates.append(mechanism_sessions)
    return min(candidates)


def close_deadline(verdict, *, renewed=False):
    return apply_deadline(verdict, renewed=renewed)


def _deadline_result(outcome, *, level1_denial, unknowns):
    if outcome == "支持":
        result = {
            "lifecycle": "已验证·有影响",
            "fundamental": "支持",
            "deadline_outcome": "支持",
            "closing_reason": "截止日证据支持",
            "operating_impact_proven": True,
        }
    elif outcome == "反证" and level1_denial:
        result = {
            "lifecycle": "已证伪",
            "fundamental": "冲突",
            "deadline_outcome": "反证",
            "closing_reason": "一级否认或事实矛盾",
            "operating_impact_proven": True,
        }
    elif outcome == "反证":
        result = {
            "lifecycle": "已衰减·无影响",
            "fundamental": "冲突",
            "deadline_outcome": "反证",
            "closing_reason": "截止日证据指向失效",
            "operating_impact_proven": True,
        }
    else:
        result = {
            "lifecycle": "已衰减·无影响",
            "fundamental": "失效",
            "deadline_outcome": "条件风险",
            "closing_reason": "截止日仍未知",
            "operating_impact_proven": False,
        }
    result["unknowns"] = list(unknowns)
    return result


def apply_deadline(verdict, *, level1_denial=False, renewed=False):
    from inves_cog.perception.attribution.operating import Verdict

    if renewed:
        raise ValueError("截止日不能续期")
    if not isinstance(verdict, Verdict) or not verdict.confirmed():
        raise ValueError("截止日结果必须来自经营证据规则")
    return _deadline_result(verdict.outcome, level1_denial=level1_denial, unknowns=verdict.unknowns)


_BLOCKED = {"price", "social_heat", "second_hit", "consensus", "flow"}


def local_support(statements, as_of):
    """One visible level-1 or level-2 quantity. This label is not 支持."""
    if any(_quantitative(row, as_of) for row in statements):
        return "局部支持"
    return "待验证"


def _quantitative(row, as_of):
    if row.get("kind") in _BLOCKED or row.get("source_level") not in (1, 2):
        return False
    if row.get("quantity") is None:
        return False
    published = row.get("published_at")
    if published is None or as_of is None:
        return False
    seen = row.get("first_seen_at") or published
    return max(published, seen) <= as_of


def track_reading(tracks):
    """Two published combinations only. A half retrace is not digested, and valuation stays put."""
    if tracks is None:
        return None
    narrative = tracks.get("narrative")
    fundamental = tracks.get("fundamental")
    if narrative is None or fundamental is None:
        return None
    capital = tracks.get("capital")
    retrace = tracks.get("retrace")
    if narrative == "衰减" and fundamental == "冲突" and capital is None:
        return None
    if narrative == "衰减" and fundamental == "未变" and retrace is None:
        return None
    reading = None
    if narrative == "衰减" and fundamental == "未变" and retrace > 0.5:
        reading = "冲击已消化"
    elif narrative == "衰减" and capital == "延续" and fundamental == "冲突":
        reading = "价格和基本面背离"
    return {
        "reading": reading,
        "research_priority": False,
        "valuation": None,
        "divergence_label": None,
        "fundamental_standing": None,
        "operating_impact_proven": False,
    }


def reactivate(evidence):
    if evidence.get("reprint"):
        raise ValueError("转载不能重新激活")
    original = evidence.get("original") and evidence.get("source_level") in (1, 2)
    if original or evidence.get("new_scope") or evidence.get("near_realization"):
        return "假设中"
    raise ValueError("不能重新激活")
