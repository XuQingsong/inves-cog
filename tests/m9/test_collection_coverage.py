import pytest

from inves_cog.dataguard.coverage import (
    audit,
    health_rows,
    program_tasks,
    registered_tasks,
    streaks,
)


@pytest.mark.phase1_blocking
def test_every_registered_task_whitelisted_and_expected():
    """CI 守门：任何 pipeline 注册任务必须 (a) 在 supervisor 程序清单里，
    (b) 在 data_expectations.yaml 有对应期望项（或标记 disabled）。
    新任务漏进白名单或缺期望项 -> 本测试失败。"""
    from pathlib import Path

    from inves_cog.dataguard.reader import load

    root = Path(__file__).resolve().parents[2]
    _, items = load(root / "config/data_expectations.yaml")
    progs = program_tasks()
    tasks = registered_tasks()
    disabled = {}
    for i in items:
        d = getattr(i, "disabled", None)
        if d:
            for t in d.get("tasks") or []:
                disabled[t] = d.get("reason", "")
    whitelisted = {t for ts in progs.values() for t in ts}
    exp = set()
    for i in items:
        for t in (getattr(i, "filter", None) or {}).get("task_name", []) or []:
            exp.add(t)
    missing_wl = [t for t in tasks if t not in whitelisted and t not in disabled]
    missing_exp = [t for t in tasks if t not in exp and t not in disabled]
    assert missing_wl == [], f"未进白名单: {missing_wl}"
    assert missing_exp == [], f"缺期望项: {missing_exp}"


@pytest.mark.phase1_blocking
def test_audit_flags_unwhitelisted_and_no_expectation():
    out = audit(
        ["ghost_task"],
        {"scheduler": ["bars_full"]},
        [{"filter": {"task_name": ["bars_full"]}}],
        {},
    )
    kinds = {(f.task, f.kind) for f in out}
    assert ("ghost_task", "uncovered") in kinds


@pytest.mark.phase1_blocking
def test_streaks_and_health_degraded_disabled():
    rows = [
        {"task_name": "t1", "status": "degraded", "started_at": 3},
        {"task_name": "t1", "status": "degraded", "started_at": 2},
        {"task_name": "t2", "status": "ok", "started_at": 3},
    ]
    sm = streaks(rows)
    assert sm["t1"]["degraded"] == 2 and sm["t2"]["last_status"] == "ok"
    health = health_rows(["t1", "t2", "t3"], sm, {"t3": "已停用：测试"}, [])
    by = {r["task_name"]: r for r in health}
    assert by["t1"]["state"] == "降级"
    assert by["t3"]["state"] == "已停用"
    assert by["t2"]["state"] == "正常"


@pytest.mark.phase1_blocking
def test_health_flags_consec_failures():
    sm = {"t9": {"fail": 3, "degraded": 0, "last_ok": None, "last_run": 1, "last_status": "failed"}}
    health = health_rows(["t9"], sm, {}, [])
    assert health[0]["state"] == "失败" and health[0]["fail_streak"] == 3
