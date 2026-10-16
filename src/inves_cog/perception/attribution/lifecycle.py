"""Linkage lifecycle. Market confirmation cannot skip the hypothesis stage."""

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
