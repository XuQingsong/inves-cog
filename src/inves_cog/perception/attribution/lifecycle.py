"""Linkage lifecycle. Market confirmation cannot skip the hypothesis stage."""

from inves_cog.perception.attribution.operating import operating_verdict

ALLOWED = {
    (None, "已发现"),
    ("已发现", "假设中"),
    ("假设中", "市场确认"),
    ("假设中", "已衰减·无影响"),
    ("市场确认", "基本面核查中"),
    ("基本面核查中", "已验证·有影响"),
    ("基本面核查中", "已衰减·无影响"),
    ("基本面核查中", "已证伪"),
    ("已衰减·无影响", "假设中"),
    ("已证伪", "假设中"),
}
_FUNDAMENTAL = {"供给", "需求", "竞争", "客户融资"}
_WINDOW = 30
_ROOTS = 3
_STAGES = 2
_LADDER = {"候选", "观察到", "有支持", "已确立"}
_MARKET_LINKS = {"市场共振", "市场叙事"}
_PRICE = {"price", "price_resonance"}


def transition(current, new, history, *, when, trigger, evidence_ids, mechanism=None):
    if (current, new) not in ALLOWED:
        raise ValueError(f"不允许从 {current} 进入 {new}")
    if new == "基本面核查中" and mechanism not in _FUNDAMENTAL:
        raise ValueError("估值倍数停在市场层")
    history = list(history)
    history.append(
        {
            "at": when,
            "old": current,
            "new": new,
            "trigger": trigger,
            "evidence_ids": list(evidence_ids),
        }
    )
    return new, history


def relation_step(edge):
    """A new edge stays a candidate. Price cannot establish it, and resonance is not transmission."""
    if edge is None:
        return None
    status = edge.get("status")
    link = edge.get("link_type")
    proposed_status = edge.get("proposed_status")
    proposed_link = edge.get("proposed_link")
    is_new = edge.get("is_new") is True
    price_block = proposed_status == "已确立" and status != "已确立" and _price_only(edge)
    market_block = proposed_link == "经营传导" and link in _MARKET_LINKS
    if not is_new and not price_block and not market_block:
        return None
    blocked = []
    if is_new:
        status_out = "候选"
        if proposed_status not in (None, "候选"):
            blocked.append("新边")
    elif price_block:
        status_out = status if status in _LADDER else None
        blocked.append("价格共振")
    else:
        status_out = status if status in _LADDER else None
    if market_block and _operating_support(edge):
        link_out = "经营传导"
    elif market_block:
        link_out = link
        blocked.append("市场层")
    else:
        link_out = link
    return {
        "status": status_out,
        "link_type": link_out,
        "blocked": blocked,
        "fundamental_standing": None,
        "operating_impact_proven": False,
    }


def _price_only(edge):
    rows = edge.get("evidence") or []
    if not rows:
        return edge.get("price_resonance") is True
    return all(row.get("kind") in _PRICE or row.get("price_resonance") is True for row in rows)


def _operating_support(edge):
    records = edge.get("evidence") or []
    as_of = edge.get("as_of")
    direction = edge.get("expected_direction")
    if not records or as_of is None or direction not in {"up", "down"}:
        return False
    verdict = operating_verdict(records, as_of=as_of, expected_direction=direction)
    return verdict.outcome == "支持"


def weak_signal(clues):
    """Three roots and two stages inside 30 sessions raise research priority only."""
    if clues is None:
        return None
    grouped, incomplete = _group_clues(clues)
    tasks = []
    unknown = False
    for variable, rows in grouped.items():
        task = _variable_task(variable, rows)
        if task is None:
            unknown = True
        elif task:
            tasks.append(task)
    if tasks:
        priority = True
    elif unknown or incomplete:
        priority = None
    else:
        priority = False
    return {
        "research_priority": priority,
        "lifecycle": "已发现" if priority else None,
        "authenticity": None,
        "fundamental_standing": None,
        "overlay": False,
        "tasks": tasks,
    }


def _group_clues(clues):
    grouped = {}
    incomplete = False
    for row in clues:
        variable = row.get("variable")
        if not variable or row.get("sessions_ago") is None:
            incomplete = True
            continue
        grouped.setdefault(variable, []).append(row)
    return grouped, incomplete


def _variable_task(variable, rows):
    inside = [row for row in rows if 0 <= row["sessions_ago"] <= _WINDOW]
    if not inside:
        return False
    if any(row.get("contradiction") is True for row in inside):
        return False
    if any(not row.get("source_root") or not row.get("stage") for row in inside):
        return None
    roots = {row["source_root"] for row in inside}
    stages = {row["stage"] for row in inside}
    if len(roots) < _ROOTS or len(stages) < _STAGES:
        return False
    return {
        "variable": variable,
        "reason": "弱信号补证",
        "is_evidence": False,
        "roots": len(roots),
        "stages": len(stages),
    }
