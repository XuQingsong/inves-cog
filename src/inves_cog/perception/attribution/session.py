"""One report shell per M7 anomaly when nothing was visible yet.

This does not judge section 7.1. News that was already visible belongs on
the retrieval path, not in this empty shell.
"""

from inves_cog.perception.attribution.impact import anomaly_status, require_anomaly_status
from inves_cog.perception.attribution.propose import propose_candidates
from inves_cog.perception.attribution.replay import then_visible


def reports_without_visible_news(anomalies, items, as_of, client):
    if then_visible(items, as_of):
        raise ValueError("当时可见的新闻不走这条空报告")
    rows = []
    for anomaly in anomalies:
        if "anomaly_id" not in anomaly or "universe" not in anomaly:
            raise ValueError("异常对象缺少编号或范围")
        members = {member["ticker"] for member in anomaly.get("members") or [] if member.get("ticker")}
        candidates = propose_candidates(anomaly, [], [], client, members)
        scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
        rows.append(
            {
                "anomaly_id": anomaly["anomaly_id"],
                "universe": anomaly["universe"],
                "trade_date": anomaly.get("trade_date"),
                "status": anomaly_status(anomaly["universe"], scores),
                "candidates": candidates,
                "sources": [],
                "visible_news": 0,
                "case_clause_met": False,
            }
        )
    require_anomaly_status(rows)
    return rows
