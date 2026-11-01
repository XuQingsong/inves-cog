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
