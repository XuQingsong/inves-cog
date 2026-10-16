"""Explanation report. A closed lifecycle still names the reason and the open unknowns."""

from inves_cog.perception.attribution.impact import anomaly_status


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
    }
    if deadline is None:
        return report
    report["lifecycle"] = deadline["lifecycle"]
    report["deadline_outcome"] = deadline["deadline_outcome"]
    report["closing_reason"] = deadline["closing_reason"]
    report["unknowns"] = list(deadline.get("unknowns") or [])
    report["operating_impact_proven"] = deadline["operating_impact_proven"]
    return report
