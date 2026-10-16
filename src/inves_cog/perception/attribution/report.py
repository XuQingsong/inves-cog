"""Explanation report. A closed lifecycle still names the reason and the open unknowns."""

from inves_cog.perception.attribution.impact import anomaly_status

_OPERATING = {"供给", "需求", "竞争", "客户融资"}


def type_candidates(candidates, prelim=(), *, operating_impact_proven=False):
    """Add a type only when a scored candidate supports it. A case name does not."""
    found = [name for name in prelim if name not in ("事件冲击", "叙事冲击", "原因未明")]
    scored = [row for row in candidates if row.get("scored") and row.get("score") is not None and row["score"] >= 0.5]
    if not scored:
        found.append("原因未明")
    for row in scored:
        if row.get("mechanism") == "估值倍数":
            found.append("叙事冲击")
        if row.get("mechanism") in _OPERATING and operating_impact_proven:
            found.append("事件冲击")
    result = []
    for name in found:
        if name not in result:
            result.append(name)
    return result


def explanation_report(anomaly, decomposition, candidates, sources, deadline=None):
    scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
    report = {
        "anomaly_id": anomaly["anomaly_id"],
        "status": anomaly.get("status") or anomaly_status(anomaly.get("universe"), scores),
        "impact": decomposition,
        "candidates": candidates,
        "valuation": "不变 / 待基本面轨道",
        "trading": None,
        "sources": sources,
        "unknowns": [],
        "type_candidates": type_candidates(
            candidates,
            anomaly.get("type_candidates_prelim") or (),
            operating_impact_proven=bool(deadline and deadline.get("operating_impact_proven")),
        ),
    }
    if deadline is None:
        return report
    report["lifecycle"] = deadline["lifecycle"]
    report["deadline_outcome"] = deadline["deadline_outcome"]
    report["closing_reason"] = deadline["closing_reason"]
    report["unknowns"] = list(deadline.get("unknowns") or [])
    report["operating_impact_proven"] = deadline["operating_impact_proven"]
    return report
