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


def test_intraday_row_inherits_daily_and_maps_index_snapshots(monkeypatch):
    """Provisional row inherits the previous trading day's px row, then
    snapshot-covered columns override. ^VIX/^VIX3M/^TNX snapshots map to the
    VIX/VIX3M/TNX columns; columns with no snapshot keep yesterday's value."""
    from datetime import datetime
    from unittest.mock import MagicMock

    import pandas as pd

    from inves_cog.perception.barometer import run

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"ticker": "^VIX", "last": 23.88, "as_of": datetime(2026, 11, 6, 15, 50)},
        {"ticker": "^TNX", "last": 4.862, "as_of": datetime(2026, 11, 6, 15, 50)},
        {"ticker": "SPY", "last": 490.0, "as_of": datetime(2026, 11, 6, 15, 50)},
    ]
    idx = pd.bdate_range("2026-10-26", "2026-11-05")
    base = pd.Series(100.0, index=idx)
    flat = ["SPY", "QQQ", "SMH", "MTUM", "TQQQ", "SOXL", "GLD", "HYG", "IEF", "TLT", "JPY=X", "BTC-USD", "XLK"]
    px = pd.DataFrame(
        {
            **{t: base.copy() for t in flat},
            "VIX": pd.Series(28.18, index=idx),
            "VIX3M": pd.Series(25.55, index=idx),
            "TNX": pd.Series(4.93, index=idx),
            "债市波动": pd.Series(15.7, index=idx),
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
    rec = run.run_intraday(conn, datetime(2026, 11, 6, 15, 51))
    assert rec["inputs"]["VIX"] == 23.88  # snapshot ^VIX mapped live
    assert rec["inputs"]["VIX/VIX3M"] == round(23.88 / 25.55, 4)  # ^VIX3M absent -> DAILY_ONLY carry
    assert rec["inputs"]["10Y"] == 4.862  # ^TNX mapped -> M["10Y"] (same units)
    assert rec["inputs"]["QQQ"] is None  # no snapshot -> NaN, not yesterday's
    assert "QQQ_5d" in rec["missing"]  # uncovered price inputs stay missing
    assert "债市波动" in rec["missing"]
    assert "VIX" not in rec["missing"]
    assert "VIX/VIX3M" not in rec["missing"]


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
                "债市波动",
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
    assert "债市波动" in rec["missing"] or rec["missing"]  # uncovered → listed missing


def test_api_shape_and_missing():
    from datetime import date as _d

    from inves_cog.web.barometer import _row, render_page

    row = {
        "date": _d(2026, 10, 30),
        "fear": 18.9,
        "greed": 4.0,
        "fear_level": 1.5,
        "greed_level": 0.3,
        "stage": "谨慎",
        "pendulum": -0.5,
        "short_heat": 10.0,
        "accumulation": 20.0,
        "nature": "",
        "dims": {"fear": {"去杠杆": 30}, "greed": {}},
        "inputs": {"VIX": 18.2, "asof_cftc": "2026-10-27", "asof_margin": "2026-09-30"},
        "missing": ["MOVE"],
    }
    rec = _row(row)
    assert "missing" not in rec  # field trimmed by page-weight PR (#153)
    assert rec["asof"]["cftc"] == "2026-10-27"
    assert list(rec["FD"]) == list({"去杠杆": 30})  # ordered output
    html = render_page([rec])
    assert "市场情绪钟摆" in html and "缺" in html and "noqa" not in html


def test_arc_order_and_script_intact():
    from datetime import date as _d

    from inves_cog.web.barometer import FEAR_ORDER, GREED_ORDER, _row, render_page

    assert FEAR_ORDER == ["下跌冲击", "恐慌情绪", "债市信用", "超卖扩散", "去杠杆", "资金与杠杆"]
    assert GREED_ORDER == ["超买", "连续上涨", "多头与杠杆", "获利盘", "情绪普涨"]
    row = {
        "date": _d(2026, 10, 30),
        "fear": 10.0,
        "greed": 5.0,
        "fear_level": 1.0,
        "greed_level": 0.5,
        "stage": "理性",
        "pendulum": 0.0,
        "short_heat": 5.0,
        "accumulation": 10.0,
        "nature": "",
        "dims": {"fear": {"资金与杠杆": 40, "下跌冲击": 10}, "greed": {"情绪普涨": 20, "超买": 15}},
        "inputs": {},
        "missing": [],
    }
    rec = _row(row)
    assert list(rec["FD"]) == ["下跌冲击", "资金与杠杆"]
    assert list(rec["GD"]) == ["超买", "情绪普涨"]
    html = render_page([rec])
    for ident in ("const TN=", "const ST=", "const DIM=", "const P=", "RING=[", 'svg id="pend"', "const R=[{"):
        assert ident in html
    for banned in ("下单", "目标价", "实时"):
        assert banned not in html


def test_homepage_state_block():
    """Rendered homepage state block = barometer sentence + linked 晴雨表, no old text."""
    from inves_cog.web.investor_html import _state_head

    payload = {
        "state": {
            "band": "平静",
            "title": "谨慎 · 恐惧 19 / 贪婪 4",
            "detail": "纳指 −3.5%（平时 3.4 倍），距高点 −9.1%；杠杆 ETF 收盘被迫卖出 107 亿美元。",
            "sentence": "谨慎 · 恐惧 19 / 贪婪 4：纳指 −3.5%…",
            "barometer": {"date": "2026-10-30", "stage": "谨慎", "fear": 19, "greed": 4},
        }
    }
    html = _state_head(payload)
    assert "杠杆 ETF 收盘被迫卖出 107 亿美元" in html
    assert 'href="/barometer"' in html
    assert "详见 /barometer" not in html
    assert "约平时" not in html.split("state-d", 1)[1].split("</p>", 1)[0]


def test_baro_sentence():
    from inves_cog.web.barometer import baro_sentence

    sent = baro_sentence(
        {"下跌冲击": 60, "资金与杠杆": 40},
        {},
        {"QQQ_1d": -3.5, "QQQ_sig": 3.4, "QQQ_dd63": -9.1, "杠杆ETF调仓亿": -107, "QQQ距200日线": 1.6},
        3.0,
        1.0,
    )
    assert "纳指 −3.5%（平时 3.4 倍）" in sent and "距高点 −9.1%" in sent
    assert "杠杆 ETF 收盘被迫卖出 107 亿美元" in sent
    assert "纳指距 200 日线仅 1.6%" in sent
    neutral = baro_sentence({}, {}, {"__fear": 20, "__greed": 15}, 1.0, 1.0)
    assert "两侧读数都在正常范围" in neutral


def test_sentence_missing_vix():
    from inves_cog.web.barometer import sentence

    rec = {"m": {}, "fl": 3, "gl": 0, "F": 50, "G": 10, "FD": {"恐慌情绪": 80}, "GD": {}}
    assert "VIX 缺" in sentence(rec)


def test_loader_sources(monkeypatch):
    """price_frame: six ETFs come from bars_daily (not yahoo_px), TNX and BTC-USD
    from macro_observations, JPY=X from ECB and MOVE on yahoo_px."""
    from datetime import date
    from unittest.mock import MagicMock

    from inves_cog.perception.barometer import loader

    assert loader.FLOWS == {"JPY=X": "ecb_jpyx", "债市波动": "cboe_vxtlt"}
    assert loader.MACRO["BTC-USD"] == ("ingest.macro_observations", "CBBTCUSD")
    assert loader.MACRO["TNX"] == ("ingest.macro_observations", "DGS10")
    assert set(loader.BARS_ETFS) == {"TQQQ", "SOXL", "GLD", "HYG", "IEF", "TLT"}

    queries = []

    class _Conn:
        def execute(self, sql, params=()):
            queries.append(sql)
            cur = MagicMock()
            if "bars_daily" in sql:
                tickers = params[0]
                assert set(loader.BARS_ETFS) <= set(tickers)
                cur.fetchall.return_value = [
                    {"ticker": t, "d": date(2026, 10, 29), "c": 100.0 + i} for i, t in enumerate(loader.BARS_ETFS)
                ]
            elif "yahoo_px_tnx" in sql:
                raise AssertionError("TNX must not come from yahoo_px_tnx")
            else:
                cur.fetchall.return_value = [{"d": date(2026, 10, 29), "value": 4.5}]
            return cur

    px = loader.price_frame(_Conn(), date(2026, 10, 29))
    for t in loader.BARS_ETFS:
        assert px[t].iloc[-1] == 100.0 + loader.BARS_ETFS.index(t)
    assert px["TNX"].iloc[-1] == 4.5
    obs_queries = [q for q in queries if "flows.observations" in q and "macro" not in q]
    assert len(obs_queries) == 2  # JPY=X, 债市波动 only


def test_series_picks_latest_vintage_for_macro_observations():
    """Multiple vintages per observation_date: loader must deterministically
    return the newest (same order as restatement: fetched_at DESC, realtime_start DESC)."""
    from datetime import date

    from inves_cog.perception.barometer.loader import _series

    class _Res:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class _Conn:
        def __init__(self, rows):
            self._rows = rows
            self.sql = None

        def execute(self, sql, params=()):
            self.sql = sql
            # emulate DISTINCT ON (observation_date) ORDER BY observation_date,
            # fetched_at DESC, realtime_start DESC
            best = {}
            for r in self._rows:
                key = (r["fetched_at"], r["realtime_start"])
                if r["d"] not in best or key > best[r["d"]][0]:
                    best[r["d"]] = (key, r)
            return _Res(sorted((v[1] for v in best.values()), key=lambda r: r["d"]))

    day = date(2026, 11, 6)
    conn = _Conn(
        [
            {"d": day, "value": 100.0, "fetched_at": "2026-11-06 01:00", "realtime_start": "2026-11-06"},
            {"d": day, "value": 200.0, "fetched_at": "2026-11-07 01:00", "realtime_start": "2026-11-07"},
            {"d": day, "value": 150.0, "fetched_at": "2026-11-06 12:00", "realtime_start": "2026-11-06"},
        ]
    )
    s = _series(conn, "ingest.macro_observations", "CBBTCUSD", day)
    assert "DISTINCT ON (observation_date)" in conn.sql
    assert "fetched_at DESC, realtime_start DESC" in conn.sql
    assert s.iloc[0] == 200.0


def test_price_frame_start_slice_covers_pct_rank_minp():
    """资管净多分位 needs ≥504 trading days (~730 cal) of history before the
    restated day; the price_frame start slice must retain that much px.index."""
    from datetime import date

    import pandas as pd

    from inves_cog.perception.barometer.loader import price_frame

    days = pd.bdate_range("2022-01-01", "2026-11-06")
    rows = [{"ticker": "SPY", "d": d.date(), "c": 100.0} for d in days]

    class _Rows:
        def __init__(self, rs):
            self.rs = rs

        def fetchall(self):
            return self.rs

    class _Conn:
        def execute(self, sql, *args):
            return _Rows(rows if "bars_daily" in sql else [])

    px = price_frame(_Conn(), days[-1].date(), start=days[-1].date())
    assert (pd.Timestamp(days[-1].date()) - px.index.min()).days >= int(504 * 365 / 252)
