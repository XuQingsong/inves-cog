"""Explanation report. A closed lifecycle still names the reason and the open unknowns."""

from inves_cog.perception.attribution.candidates import market_consensus, market_fingerprint
from inves_cog.perception.attribution.codes import ticker_codes
from inves_cog.perception.attribution.dims import (
    falsified_rumor,
    primary_signal,
    rumor_split,
    sentiment_amplification,
    source_check,
    weakest_link,
)
from inves_cog.perception.attribution.evidence import later_report
from inves_cog.perception.attribution.impact import anomaly_status
from inves_cog.perception.attribution.labels import (
    consensus_dispersion,
    consensus_lookback,
    revision_breadth,
    surprise_history,
)
from inves_cog.perception.attribution.lifecycle import relation_step, weak_signal
from inves_cog.perception.attribution.magnitude import channel_lines, ntm_move
from inves_cog.perception.attribution.propose import research_order, review_queue
from inves_cog.perception.attribution.retrieve import (
    discard_review,
    explore_quota,
    retrieval_gap,
    text_retention,
)
from inves_cog.perception.attribution.second_hit import denial_response
from inves_cog.perception.attribution.tracks import local_support, retrace_windows, track_reading
from inves_cog.perception.attribution.unexplained import coverage_check

_OPERATING = {"供给", "需求", "竞争", "客户融资"}
CONSTRAINT_ITEMS = ("新增供给占需求增量", "投产与良率", "产品代际", "需求吸收", "订单相对可交付", "价格传导")
_OBSERVED = {"观察到", "有支持", "已确立"}
_FUNDAMENTAL = {"待验证", "局部支持", "支持", "冲突", "失效"}


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


def impact_scope(candidates, relations=(), *, direction=None):
    """Exposure is a relation label. A price member without one stays 纯共振."""
    by_ticker = {}
    for rel in relations:
        by_ticker.setdefault(rel.get("ticker"), []).append(rel)
    rows = []
    seen = set()
    for row in _scored(candidates):
        mechanism = row.get("mechanism")
        for affected in row.get("affected") or []:
            ticker = affected.get("ticker")
            key = (ticker, mechanism)
            if not ticker or key in seen:
                continue
            seen.add(key)
            links = by_ticker.get(ticker) or []
            exposure, reason = _exposure(mechanism, links)
            rows.append(
                {
                    "ticker": ticker,
                    "direction": affected.get("direction") or direction,
                    "mechanism": mechanism,
                    "exposure": exposure,
                    "reason": reason,
                    "exit_reason": next((rel.get("exit_reason") for rel in links if rel.get("exit_reason")), None),
                }
            )
    return rows


def tracking_list(mechanisms, known=(), *, deadline_on=None):
    """A supply or demand checklist is a task list. Having a task is not evidence."""
    if not {"供给", "需求"} & set(mechanisms):
        return []
    known_items = set(known)
    return [
        {
            "item": name,
            "question": name,
            "metric": name,
            "source": None,
            "window": None,
            "deadline": deadline_on,
            "status": "有数据" if name in known_items else "未知",
            "is_evidence": False,
        }
        for name in CONSTRAINT_ITEMS
    ]


def constraint_conclusion(items, *, impact=None):
    """One of the four constraint labels. The label does not prove operating impact."""
    if not items:
        return None
    if any(_cited_conflict(row) for row in items):
        label = "关键约束冲突"
    elif any(_usable_status(row) != "结论" for row in items):
        label = "约束不清但有上下界"
    elif impact == "有限":
        label = "可计算且冲击有限"
    elif impact == "实质":
        label = "可计算且冲击实质"
    else:
        label = "约束不清但有上下界"
    return {
        "label": label,
        "has_bounds": any(bool(row.get("bounds")) for row in items),
        "operating_impact_proven": False,
        "closes_case": False,
    }


def split_conclusions(candidates, fundamental=None):
    """Market confidence and fundamental standing stay in separate fields."""
    return {
        "market_confidence": _market_confidence(candidates),
        "fundamental_standing": _fundamental_standing(candidates, fundamental),
    }


def explanation_report(
    anomaly,
    decomposition,
    candidates,
    sources,
    deadline=None,
    relations=(),
    known_constraints=(),
    deadline_on=None,
    *,
    supplement=None,
    narrative_shock=False,
    fundamental_unchanged=False,
    embeddings=None,
    magnitude=None,
    statements=(),
    as_of=None,
    heat=None,
    clues=None,
    queue=None,
    rumor=None,
    verifiers=(),
    chain=None,
    timing=None,
    audit=None,
    denial=None,
    tracks_view=None,
    fingerprint=None,
    explore=None,
    discarded=None,
    falsified=None,
    relation=None,
    primary=None,
    research=None,
    consensus=None,
    coverage=None,
    windows=None,
    ntm=None,
    archive=None,
    lookback=None,
    breadth=None,
    dispersion=None,
    surprises=None,
):
    scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
    mechanisms = [row.get("mechanism") for row in _scored(candidates)]
    tracking = tracking_list(mechanisms, known_constraints, deadline_on=deadline_on)
    note = supplement.get("note") if supplement else None
    conclusions = split_conclusions(candidates, _stated_fundamental(deadline, statements, as_of))
    report = {
        "anomaly_id": anomaly["anomaly_id"],
        "status": anomaly.get("status") or anomaly_status(anomaly.get("universe"), scores),
        "impact": decomposition,
        "candidates": candidates,
        "valuation": "不变 / 待基本面轨道",
        "trading": None,
        "sources": sources,
        "unknowns": [],
        "scope": impact_scope(candidates, relations, direction=anomaly.get("direction")),
        "tracking": tracking,
        "constraint_conclusion": constraint_conclusion(tracking),
        "supplement": note,
        "market_confidence": conclusions["market_confidence"],
        "fundamental_standing": conclusions["fundamental_standing"],
        "retrieval_gap": retrieval_gap(embeddings),
        "magnitude_channels": None if magnitude is None else channel_lines(magnitude),
        "sentiment_amplification": sentiment_amplification(heat, conclusions["fundamental_standing"]),
        "weak_signal": None if clues is None else weak_signal(clues),
        "review_queue": None if queue is None else review_queue(queue),
        "rumor_split": None if rumor is None else rumor_split(rumor, verifiers),
        "weakest_link": weakest_link(chain),
        "later_report": later_report(timing),
        "source_check": source_check(audit),
        "denial_response": denial_response(denial),
        "track_reading": track_reading(tracks_view),
        "market_fingerprint": market_fingerprint(fingerprint),
        "explore_quota": explore_quota(explore),
        "discard_review": discard_review(discarded),
        "falsified_rumor": falsified_rumor(falsified),
        "relation_step": relation_step(relation),
        "primary_signal": primary_signal(primary),
        "research_order": research_order(research),
        "market_consensus": market_consensus(consensus),
        "coverage_check": coverage_check(coverage),
        "retrace_windows": retrace_windows(windows),
        "ntm_move": ntm_move(ntm),
        "text_retention": text_retention(archive),
        "consensus_lookback": consensus_lookback(lookback),
        "revision_breadth": revision_breadth(breadth),
        "consensus_dispersion": consensus_dispersion(dispersion),
        "surprise_history": surprise_history(surprises),
        "ticker_status": ticker_codes(
            anomaly,
            candidates,
            narrative_shock=narrative_shock,
            fundamental_unchanged=fundamental_unchanged,
        ),
        "type_candidates": type_candidates(
            candidates,
            anomaly.get("type_candidates_prelim") or (),
            operating_impact_proven=bool(deadline and deadline.get("operating_impact_proven")),
        ),
    }
    if deadline is not None:
        report["lifecycle"] = deadline["lifecycle"]
        report["deadline_outcome"] = deadline["deadline_outcome"]
        report["closing_reason"] = deadline["closing_reason"]
        report["unknowns"] = list(deadline.get("unknowns") or [])
        report["operating_impact_proven"] = deadline["operating_impact_proven"]
    if note and note not in report["unknowns"]:
        report["unknowns"].append(note)
    return report


def _market_confidence(candidates):
    scores = [row["score"] for row in candidates if row.get("scored") and row.get("score") is not None]
    if not scores:
        return "低"
    best = max(scores)
    if best >= 0.70:
        return "高"
    if best >= 0.50:
        return "中"
    return "低"


def _fundamental_standing(candidates, fundamental):
    operating = [row for row in _scored(candidates) if row.get("mechanism") in _OPERATING]
    if not operating:
        return None
    if fundamental in _FUNDAMENTAL:
        return fundamental
    return "待验证"


def _stated_fundamental(deadline, statements, as_of):
    if deadline:
        stated = deadline.get("fundamental")
        if stated in _FUNDAMENTAL:
            return stated
    if statements and local_support(statements, as_of) == "局部支持":
        return "局部支持"
    return None


def _scored(candidates):
    allowed = _OPERATING | {"估值倍数"}
    return [row for row in candidates if _counts(row) and row.get("mechanism") in allowed]


def _counts(row):
    return row.get("scored") and row.get("score") is not None and row["score"] >= 0.5


def _cited(row):
    return bool(row.get("source")) and row.get("source_level") in (1, 2, 3)


def _usable_status(row):
    if row.get("status") == "结论" and _cited(row):
        return "结论"
    if row.get("status") == "结论":
        return "有数据"
    return row.get("status")


def _cited_conflict(row):
    return bool(row.get("conflict")) and _cited(row)


def _exposure(mechanism, relations):
    if mechanism == "估值倍数":
        return "概念关联", "估值倍数停在市场层"
    active = [rel for rel in relations if not rel.get("exit_reason")]
    observed = [rel for rel in active if rel.get("exposure") in {"直接", "间接"} and rel.get("status") in _OBSERVED]
    if any(rel.get("exposure") == "直接" for rel in observed):
        return "直接", "状态至少观察到"
    if observed:
        return "间接", "状态至少观察到"
    if relations:
        return "概念关联", "候选关系不是经营暴露"
    return "纯共振", "没有观察到的关系"
