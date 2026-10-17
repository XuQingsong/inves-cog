"""An unexplained anomaly is rechecked once per session for five sessions, then it stops."""

from inves_cog.perception.attribution.impact import anomaly_status, require_anomaly_status
from inves_cog.perception.attribution.propose import propose_candidates


def statuses_without_news(cases, client):
    rows = []
    for case in cases:
        if case.get("fixture") != "synthetic" or case.get("news"):
            raise ValueError("空新闻路径只接受标明 synthetic 的空输入")
        candidates = propose_candidates(case, [], [], client, set(case.get("members") or []))
        scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
        rows.append(
            {
                "anomaly_id": case["anomaly_id"],
                "status": anomaly_status(case.get("universe"), scores),
                "fixture": "synthetic",
            }
        )
    require_anomaly_status(rows)
    return rows


def classify_unexplained(scores):
    if any(score >= 0.5 for score in scores):
        return None
    return "已发现·原因未明"


def recheck_flags(session_count):
    return [index < 5 for index in range(session_count)]


def attention_line(held, max_abs_z):
    if held and max_abs_z >= 4:
        return "请人工查看"
    return None


def coverage_check(days):
    """Three strictly rising unexplained ratios raise the alarm. One step up does not."""
    if days is None:
        return None
    rows = [_coverage_day(day) for day in days]
    ratios = [row["unexplained_ratio"] for row in rows]
    if len(ratios) < 3 or any(value is None for value in ratios):
        alarm = None
    else:
        alarm = all(ratios[index] > ratios[index - 1] for index in range(1, len(ratios)))
    return {
        "days": rows,
        "alarm": alarm,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


def _coverage_day(day):
    total = day.get("total")
    found = day.get("with_candidate")
    unexplained = day.get("unexplained")
    ratio = None
    if _count(total) and _count(found) and _count(unexplained) and found <= total and unexplained <= total and total:
        ratio = unexplained / total
    return {
        "total": total,
        "with_candidate": found,
        "unexplained": unexplained,
        "unexplained_ratio": ratio,
    }


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
