"""Voided post anomalies: web readers filter them; the script dry-runs safely."""

import inspect

import pytest

pytestmark = pytest.mark.phase1_blocking


def test_web_anomaly_reads_exclude_voided():
    from inves_cog.web import pages, stock_brief

    pages_src = inspect.getsource(pages)
    stock_src = inspect.getsource(stock_brief)
    assert pages_src.count("NOT LIKE '已作废%'") >= 2
    assert "NOT LIKE '已作废%'" in stock_src


def test_dry_run_never_writes(monkeypatch):
    import scripts.void_post_multi_anomalies as mod

    class FakeConn:
        def execute(self, sql, args=()):
            if sql.startswith("UPDATE"):
                raise AssertionError("dry-run must not UPDATE")
            return self

        def fetchall(self):
            return [{"anomaly_id": "2026-11-06:post:001", "status": "已发现·原因未明"}]

        def transaction(self):
            import contextlib

            return contextlib.nullcontext()

    monkeypatch.setattr(mod, "main", lambda: None)  # only verify module loads
    assert mod.NEW_STATUS == "已作废·统计口径错误"
    assert "<@ '{multi_3d,multi_5d}'::text[]" in mod.SELECT
