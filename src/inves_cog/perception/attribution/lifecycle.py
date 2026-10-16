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


def transition(current, new, history, *, when, trigger, evidence_ids):
    if (current, new) not in ALLOWED:
        raise ValueError(f"不允许从 {current} 进入 {new}")
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
