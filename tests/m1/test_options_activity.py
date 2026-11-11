import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from inves_cog.perception.options_activity import options_activity

DAY = date(2026, 11, 9)


class Conn:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def execute(self, sql, params=()):
        assert "flows.option_volume_occ" in sql
        ticker, day = params[0], params[1]
        return _Result([r for r in self._rows if r["underlying"] == ticker and r["date"] < day])


class _Result(list):
    def fetchall(self):
        return list(self)

    def fetchone(self):
        return self[0] if self else None


def _occ(day, cp, account, qty, ticker="T"):
    return {"date": day, "underlying": ticker, "cp": cp, "account_type": account, "quantity": qty}


def _baseline(end, days, calls=1000, puts=1000):
    """`days` sessions strictly before `end - 1`（留 DAY-1 给 day0），alternating
    put volume so the baseline put/call ratio has nonzero variance."""
    rows = []
    last = end - timedelta(days=1)
    for i in range(days, 0, -1):
        day = last - timedelta(days=i)
        p = puts - 100 if (days - i) % 2 == 0 else puts + 100
        rows += [_occ(day, "C", "C", calls), _occ(day, "P", "C", p)]
    return rows


@pytest.mark.phase1_blocking
def test_missing_when_no_occ_rows():
    out = options_activity(Conn(), "T", DAY, params={})
    assert out["missing"] == "无 OCC 期权成交记录"
    assert out["label"] == "暂缺"


@pytest.mark.phase1_blocking
def test_same_day_rows_excluded_t_plus_one():
    rows = _baseline(DAY, 11)
    rows += [
        _occ(DAY - timedelta(days=1), "C", "C", 2000),
        _occ(DAY - timedelta(days=1), "P", "C", 2000),
        # 当日行：T 日成交次日才发布，不得进入
        _occ(DAY, "C", "C", 999_999),
        _occ(DAY, "P", "M", 999_999),
    ]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["data_date"] == (DAY - timedelta(days=1)).isoformat()
    assert out["call_volume"] == 2000
    assert out["total_volume"] == 4000


@pytest.mark.phase1_blocking
def test_thin_volume_not_judged():
    rows = _baseline(DAY, 11)
    rows += [_occ(DAY - timedelta(days=1), "C", "C", 300), _occ(DAY - timedelta(days=1), "P", "C", 200)]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["label"] == "成交过少，不判"
    assert out["total_volume"] == 500


@pytest.mark.phase1_blocking
def test_short_history_not_judged():
    rows = _baseline(DAY, 5)
    rows += [_occ(DAY - timedelta(days=1), "C", "C", 3500), _occ(DAY - timedelta(days=1), "P", "C", 500)]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["label"] == "历史不足"
    assert out["baseline_days"] == 5


@pytest.mark.phase1_blocking
def test_call_surge_label():
    rows = _baseline(DAY, 11)
    rows += [_occ(DAY - timedelta(days=1), "C", "C", 3500), _occ(DAY - timedelta(days=1), "P", "C", 500)]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["call_multiple"] == pytest.approx(3.5)
    assert out["pc_z"] <= -2
    assert out["label"] == "看涨放量"


@pytest.mark.phase1_blocking
def test_put_surge_label():
    rows = _baseline(DAY, 11)
    rows += [_occ(DAY - timedelta(days=1), "C", "C", 500), _occ(DAY - timedelta(days=1), "P", "C", 3500)]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["put_multiple"] == pytest.approx(3.53, abs=0.01)
    assert out["pc_z"] >= 2
    assert out["label"] == "看跌放量"


@pytest.mark.phase1_blocking
def test_volume_surge_alone_is_not_flagged():
    # 看涨看跌同比放大，P/C 不变 → 不算放量
    rows = _baseline(DAY, 11)
    rows += [_occ(DAY - timedelta(days=1), "C", "C", 4000), _occ(DAY - timedelta(days=1), "P", "C", 4000)]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["call_multiple"] == pytest.approx(4.0)
    assert out["label"] == "正常"


@pytest.mark.phase1_blocking
def test_account_split_and_thresholds_from_params():
    rows = _baseline(DAY, 11)
    rows += [
        _occ(DAY - timedelta(days=1), "C", "C", 2800),
        _occ(DAY - timedelta(days=1), "C", "M", 500),
        _occ(DAY - timedelta(days=1), "C", "F", 100),
        _occ(DAY - timedelta(days=1), "P", "C", 500),
    ]
    out = options_activity(Conn(rows), "T", DAY, params={})
    assert out["customer_share"] == pytest.approx(0.846, abs=0.01)
    assert out["mm_share"] == pytest.approx(0.128, abs=0.01)
    assert out["firm_share"] == pytest.approx(0.026, abs=0.01)
    # 阈值全部来自参数：把放量倍数抬到 4 后，同样的数据不再判看涨放量
    strict = options_activity(Conn(rows), "T", DAY, params={"options_spike_multiple": 4.0})
    assert strict["label"] != "看涨放量"
    assert out["label"] == "看涨放量"


@pytest.mark.phase1_blocking
def test_rule_a_does_not_read_options_activity():
    offenders = []
    for directory in ("src/inves_cog/trading", "src/inves_cog/valuation", "src/inves_cog/valuation_v1"):
        root = Path(directory)
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                if any("options_activity" in n for n in names):
                    offenders.append(str(path))
    assert not offenders, f"rule A imports options_activity: {offenders}"
