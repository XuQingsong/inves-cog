from unittest.mock import MagicMock

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


@pytest.mark.phase1_blocking
def test_writes_to_inherits_expectation_table():
    """writes_to {tasks:[...]} on a table-level expectation inherits its
    table + date_column for the empty-run check."""
    from types import SimpleNamespace

    items = [
        SimpleNamespace(
            writes_to={"tasks": ["fred"]},
            table="ingest.macro_observations",
            date_column="observation_date",
        )
    ]
    from inves_cog.dataguard.coverage import config_task_tables

    assert config_task_tables(items)["fred"] == {
        "table": "ingest.macro_observations",
        "date_column": "observation_date",
    }


@pytest.mark.phase1_blocking
def test_missing_ratio_tolerance_constant():
    """Collectors export the 1% missing tolerance used by degraded."""
    from inves_cog.ingest.intraday import MISSING_TOLERANCE, YAHOO_TICKERS

    assert MISSING_TOLERANCE == 0.01
    assert "^TNX" not in YAHOO_TICKERS and "^FVX" not in YAHOO_TICKERS


@pytest.mark.phase1_blocking
def test_per_ticker_gap_names_ticker():
    from inves_cog.dataguard.coverage import per_ticker_gaps

    reader = MagicMock()
    reader.execute.return_value.fetchall.return_value = [{"ticker": "ACME", "latest": "2026-11-05"}]
    out = per_ticker_gaps(reader, MagicMock())
    assert out and "个股报价缺失：ACME" in out[0].task and "停牌" in out[0].detail


@pytest.mark.phase1_blocking
def test_disabled_expectation_skipped_in_scan_and_evaluate():
    """disabled expectations produce no findings via scan or evaluate."""
    from inves_cog.dataguard.service import scan
    from inves_cog.dataguard.core import evaluate
    from types import SimpleNamespace
    import inspect

    item = SimpleNamespace(disabled={"tasks": ["x"], "reason": "已停用"})
    assert evaluate(item, None, [], None) == []
    src = inspect.getsource(scan)
    assert "disabled" in src


@pytest.mark.phase1_blocking
def test_degraded_threshold_allows_single_ticker():
    """1 of 76 missing is not degraded; >1% AND >1 absolute is."""
    from inves_cog.ingest.intraday import _degraded

    assert _degraded(1, 76) is False  # XLC-only miss -> ok
    assert _degraded(2, 76) is True  # >1% of 76
    assert _degraded(1, 40) is False  # max(1, floor) gate
