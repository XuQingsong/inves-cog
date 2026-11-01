import pandas as pd

from inves_cog.perception.barometer.compute import DIM_INPUTS, nature, sc, stage


def test_sc_anchors():
    assert sc(pd.Series([15.0]), 15, 45).iloc[0] == 0
    assert sc(pd.Series([45.0]), 15, 45).iloc[0] == 100
    assert sc(pd.Series([30.0]), 15, 45).iloc[0] == 50
    assert sc(pd.Series([99.0]), 15, 45).iloc[0] == 100
    assert sc(pd.Series([5.0]), 15, 45).iloc[0] == 0


def test_stage_bands():
    assert stage(1.0, 1.0) == 0  # 理性
    assert stage(3.5, 1.0) == -2  # 悲观 (紧张)
    assert stage(4.5, 1.0) == -3  # 绝望 (恐慌)
    assert stage(1.0, 3.5) == 2  # 兴奋 (过热)


def test_nature_labels():
    assert "堆积型" in nature(50, 45, 50)
    assert "堆积未释放" in nature(50, 30, 50)
    assert "超卖反弹" in nature(30, 50, 10)
    assert nature(10, 10, 10) == ""


def test_dimensions_missing_excluded():
    """A dim = mean of present indicators only; NaN indicators drop out."""
    idx = pd.date_range("2026-10-26", periods=5, freq="B")
    import numpy as np

    from inves_cog.perception.barometer.compute import dimensions

    cols = set()
    for side in DIM_INPUTS.values():
        for inds in side.values():
            cols.update(inds)
    M = pd.DataFrame({c: pd.Series(0.0, index=idx) for c in cols})
    M["VIX"] = pd.Series([15.0] * 4 + [np.nan], index=idx)
    F, G = dimensions(M)
    # 恐慌情绪 on the last day: VIX NaN → mean of remaining two indicators only
    assert not pd.isna(F["恐慌情绪"].iloc[-1])
    assert pd.isna(M["VIX"].iloc[-1])


def test_official_gate_bars_missing():
    """No bars for today → no write, pending key set, not marked done."""
    import sys
    from datetime import date, datetime
    from unittest.mock import MagicMock

    sys.path.insert(0, "scripts")
    import schedule_flows

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"c": 0}
    state = {}
    schedule_flows._barometer(conn, date(2026, 11, 2), "17:00", None, datetime(2026, 11, 2, 17, 0), state)
    assert state.get("baro_pending:2026-11-02") is True
    assert "baro:2026-11-02" not in state


def test_intraday_provisional_missing(monkeypatch):
    """Provisional row: snapshot prices only; uncovered inputs → missing, not ffilled."""
    from datetime import datetime
    from unittest.mock import MagicMock

    import pandas as pd
    from inves_cog.perception.barometer import run

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"ticker": "SPY", "last": 700.0, "as_of": datetime(2026, 11, 2, 15, 0)},
        {"ticker": "QQQ", "last": 640.0, "as_of": datetime(2026, 11, 2, 15, 0)},
    ]
    idx = pd.bdate_range("2026-10-26", "2026-10-30")
    px = pd.DataFrame(
        {
            t: pd.Series(100.0, index=idx)
            for t in [
                "SPY",
                "QQQ",
                "SMH",
                "VIX",
                "VIX3M",
                "MTUM",
                "TQQQ",
                "SOXL",
                "GLD",
                "HYG",
                "IEF",
                "TLT",
                "JPY=X",
                "BTC-USD",
                "MOVE",
                "TNX",
            ]
            + ["XLK"]
        }
    )
    monkeypatch.setattr(run, "price_frame", lambda c, e: px.copy())
    monkeypatch.setattr(
        run,
        "flows_inputs",
        lambda c, i, p: {
            k: pd.Series(0.0, index=i)
            for k in [
                "杠杆ETF调仓亿",
                "SPDR资金5日%",
                "杠杆基金4周变化",
                "SOFR-IORB基点",
                "净流动性4周%",
                "个股看跌看涨5日",
                "杠杆ETF净申购20日%",
                "融资余额同比%",
                "资管净多分位",
                "资管净多%",
                "杠杆基金净头寸%",
            ]
        },
    )
    rec = run.run_intraday(conn, datetime(2026, 11, 2, 15, 30))
    assert rec["inputs"]["provisional"] is True
    assert "MOVE" in rec["missing"] or rec["missing"]  # uncovered → listed missing
