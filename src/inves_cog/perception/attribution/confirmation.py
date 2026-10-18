"""Source-bound FR-M8-14 checks. A market response is not operating proof."""

import math
from datetime import datetime

from inves_cog.perception.attribution.candidates import independent_of_price, market_confirmed
from inves_cog.perception.attribution.evidence import alternative_exclusion


def confirmation_reading(candidate, anomaly, items, members):
    """Use this candidate's citations and complete mapped scope, never model flags.

    Callers supply members resolved against the actual anomaly. Missing scope,
    source metadata or own-event checks stay unknown. No new anomaly threshold
    is inferred from a stock's residual.
    """
    ids = list(candidate.get("info_ids") or [])
    cited = [row for row in items if row.get("info_id") in ids]
    complete = bool(ids) and set(ids) == {row.get("info_id") for row in cited}
    timed = [row for row in cited if row.get("claims")]
    stamps = [_stamp(row.get("published_at")) for row in timed]
    earliest = min(stamps).isoformat() if stamps and all(stamps) and complete else None
    names = [row.get("ticker") or row.get("entity_id") for row in members]
    observed = [row.get("resid") for row in members]
    response = (
        True
        if anomaly.get("anomaly_id")
        and anomaly.get("universe") == "pool"
        and anomaly.get("session") in {"close", "post"}
        and members
        and all(_number(value) for value in observed)
        else None
    )
    # Current review paraphrases and price rows cannot create independent roots.
    original = [
        row
        for row in cited
        if row.get("evidence_role") not in {"current_context", "research_gap"}
        and row.get("kind") not in {"price", "social"}
    ]
    independent_rows = []
    for row in original:
        level = row.get("source_level")
        independent_rows.append(
            {
                "source_root": _name(row.get("source_root")),
                "kind": row.get("kind"),
                "source_level": level if type(level) is int and level in {1, 2, 3, 4} else None,
                "heat_spike": row.get("heat_spike") is True,
                "entity": _name(row.get("entity")),
                "monitor": _name(row.get("monitor")),
            }
        )
    independent = True if complete and independent_of_price(independent_rows) else None
    alternative = alternative_exclusion(members)
    reading = {
        "claim_time": True if earliest is not None else None,
        "response": response,
        "independent": independent,
        "alternative": alternative,
    }
    return {
        "origin": "candidate_citations_and_m7_members",
        "mechanism": candidate.get("mechanism"),
        "info_ids": ids,
        "scope": names,
        "reading": reading,
        "confirmed": market_confirmed(**reading),
        "checks": {
            "claim_time": {
                "value": reading["claim_time"],
                "earliest_published_at": earliest,
                "source_ids": [row["info_id"] for row in timed],
                "missing": [] if earliest else ["说法缺精确出版时间、完整引用或有效说法；日期区间不造分钟"],
            },
            "response": {
                "value": response,
                "anomaly_id": anomaly.get("anomaly_id"),
                "scope": names,
                "residuals": observed,
                "missing": [] if response else ["候选范围未完整映射到池内M7异常的已观测成员"],
                "note": "沿用M7异常对象，不声称每只成员单独越过异常门槛或证明因果",
            },
            "independent": {
                "value": independent,
                "source_ids": [row["info_id"] for row in original],
                "source_roots": sorted({row["source_root"] for row in independent_rows if row["source_root"]}),
                "missing": [] if independent else ["引用未提供两独立来源根、已监控热度突增或1–3级点评"],
                "note": "只用来源元数据；不使用模型自评、当前转述或价格作为独立证据",
            },
            "alternative": {
                "value": alternative,
                "scope": names,
                "member_checks": [
                    {key: row.get(key) for key in ("ticker", "earnings_reaction", "guidance_8k", "rating_change")}
                    for row in members
                ],
                "missing": [] if alternative is not None else ["缺候选完整范围或逐成员财报/8-K/评级核查"],
            },
        },
        "semantic_quality_proven": False,
        "operating_impact_proven": False,
    }


def _stamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if isinstance(value, datetime) and value.tzinfo is not None else None


def _number(value):
    return type(value) in {int, float} and math.isfinite(value)


def _name(value):
    return value.strip() if isinstance(value, str) and value.strip() else None
