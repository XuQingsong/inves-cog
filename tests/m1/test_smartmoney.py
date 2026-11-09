import ast
from datetime import date
from pathlib import Path

import pytest

from inves_cog.perception.smartmoney import money_flow


class FakeConn:
    """form4 rows carry a trailing filed_at used to simulate the SQL cutoff."""

    def __init__(self, form4=(), short_vol=(), bars=(), si=(), shares=None):
        self._form4 = list(form4)
        self._map = {
            "flows.short_volume": list(short_vol),
            "bars_daily": list(bars),
            "ingest.short_interest": list(si),
            "fin_state": list(shares or []),
        }

    def execute(self, sql, params=()):
        if "form4_events" in sql:
            as_of = params[1]
            return _Result([r[:8] for r in self._form4 if r[8] <= as_of])
        for key, rows in self._map.items():
            if key in sql:
                return _Result(rows)
        raise AssertionError(f"unexpected query: {sql[:80]}")


class _Result(list):
    def fetchall(self):
        return list(self)

    def fetchone(self):
        return self[0] if self else None


def _f4(name, title, director, plan, code, shares, price, amount, filed):
    return (name, title, director, plan, code, shares, price, amount, filed)


DAY = date(2026, 11, 9)


@pytest.mark.phase1_blocking
def test_ps_only_and_excluded_count():
    conn = FakeConn(
        form4=[
            _f4("A Doe", "CFO", False, False, "S", 10, 100.0, 1000.0, DAY),
            _f4("A Doe", "CFO", False, False, "P", 5, 50.0, 250.0, DAY),
            _f4("A Doe", "CFO", False, None, "G", 999, 0.0, None, DAY),
            _f4("B Roe", None, True, None, "A", 1, 1.0, None, DAY),
        ]
    )
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["excluded_count"] == 2  # G + A counted as excluded, not as amounts
    assert ins["totals"]["buys"]["usd"] == 250.0
    assert ins["totals"]["unplanned"]["usd"] == 1000.0


@pytest.mark.phase1_blocking
def test_unknown_plan_not_counted_as_unplanned():
    conn = FakeConn(form4=[_f4("A Doe", "CFO", False, None, "S", 10, 1.0, 20_000_000.0, DAY)])
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["totals"]["unknown_plan"]["usd"] == 20_000_000.0
    assert ins["totals"]["unplanned"]["usd"] == 0.0
    assert ins["label"] == "中性"  # NULL plan must not trigger 偏空


@pytest.mark.phase1_blocking
def test_label_thresholds():
    bullish = FakeConn(form4=[_f4("A", "t", False, None, "P", 1, 1.0, 1_500_000.0, DAY)])
    assert money_flow(bullish, "T", DAY, params={})["insiders"]["label"] == "偏多"
    bearish = FakeConn(form4=[_f4("A", "t", False, False, "S", 1, 1.0, 15_000_000.0, DAY)])
    assert money_flow(bearish, "T", DAY, params={})["insiders"]["label"] == "偏空"
    below = FakeConn(form4=[_f4("A", "t", False, False, "S", 1, 1.0, 9_000_000.0, DAY)])
    assert money_flow(below, "T", DAY, params={})["insiders"]["label"] == "中性"


@pytest.mark.phase1_blocking
def test_pit_cutoff_excludes_later_filings():
    conn = FakeConn(
        form4=[
            _f4("Old", "t", False, False, "S", 1, 1.0, 1000.0, date(2026, 10, 1)),
            _f4("New", "t", False, False, "S", 1, 1.0, 20_000_000.0, date(2026, 11, 10)),
        ]
    )
    ins = money_flow(conn, "T", DAY, params={})["insiders"]
    assert ins["totals"]["unplanned"]["usd"] == 1000.0  # 11-10 filing is after as_of
    assert ins["label"] == "中性"


@pytest.mark.phase1_blocking
def test_missing_blocks_say_why():
    out = money_flow(FakeConn(), "T", DAY, params={})
    assert out["insiders"]["missing"]
    assert out["offexchange"]["missing"] == "该股不在 FINRA 返回中"
    assert out["short"]["missing"] == "无 FINRA 持仓记录"


@pytest.mark.phase1_blocking
def test_short_visibility_uses_publish_date():
    si = [(date(2026, 10, 15), date(2026, 11, 30), 100.0, 2.0)]
    out = money_flow(FakeConn(si=si), "T", date(2026, 10, 28), params={})
    assert out["short"]["missing"] == "无 FINRA 持仓记录"
    out2 = money_flow(FakeConn(si=si), "T", date(2026, 12, 1), params={})
    assert out2["short"]["missing"] is None
    assert out2["short"]["latest"]["publish_inferred"] is False
    si_null = [(date(2026, 10, 15), None, 100.0, 2.0)]
    out3 = money_flow(FakeConn(si=si_null), "T", date(2026, 12, 1), params={})
    assert out3["short"]["latest"]["publish_inferred"] is True


@pytest.mark.phase1_blocking
def test_rule_a_does_not_import_smartmoney():
    offenders = []
    for path in Path("src/inves_cog/trading").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any("smartmoney" in n for n in names):
                offenders.append(str(path))
    assert not offenders, f"trading imports smartmoney: {offenders}"
