"""Barometer: fear (pressure) and greed (overheat) composites 0–100.

Exact port of the prototype docs/phase2/demo/barometer/comp.py:
each indicator scales linearly normal→extreme to 0–100; a dimension is the
mean of its indicators (missing excluded + listed); the composite is the
mean of dimensions. No triggers, no step rules.
"""
import numpy as np
import pandas as pd

SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
AI_CHAIN = ["NVDA", "AMD", "AVGO", "MRVL", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MU",
            "SNDK", "WDC", "DELL", "SMCI", "ANET", "CIEN", "COHR", "VRT", "GEV", "CEG",
            "INTC", "ARM", "QCOM"]
LEVERED = {"TQQQ": (3, "QQQ"), "UPRO": (3, "SPY"), "QLD": (2, "QQQ"), "SSO": (2, "SPY"),
           "USD": (2, "SMH"), "SQQQ": (-3, "QQQ"), "SPXU": (-3, "SPY"),
           "QID": (-2, "QQQ"), "SDS": (-2, "SPY")}
SPDR_FLOW = ["SPY", "XLK", "XLY", "XLF", "XLE", "XLI", "XLV", "XLP", "XLU", "XLB", "XLRE", "XLC"]

FEAR_LEVELS = [0, 7, 15, 30, 45, 100]
GREED_LEVELS = [0, 15, 30, 45, 60, 100]
STAGES = ["绝望", "悲观", "谨慎", "理性", "乐观", "兴奋", "狂热"]


def sc(x, lo, hi):
    return ((x - lo) / (hi - lo) * 100).clip(0, 100)


def rsi(p, n=14):
    d = p.diff()
    return 100 - 100 / (1 + d.clip(lower=0).rolling(n).mean() / (-d.clip(upper=0)).rolling(n).mean())


def _mean(*xs):
    return pd.concat(xs, axis=1).mean(axis=1)


def _worst(a, b):
    return pd.concat([a, b], axis=1).max(axis=1)


def _pct_rank(s, window=1260, minp=504):
    return s.rolling(window, min_periods=minp).apply(
        lambda x: (x[:-1] < x[-1]).mean() * 100 if not np.isnan(x[-1]) else np.nan, raw=True)


def indicators(px, flows):
    """px: {ticker: close Series}; flows: {name: Series} (PIT-aligned to idx).

    Returns (M, missing) — M is the indicator frame, missing lists px symbols
    the day has no value for after ffill(limit=3) on the SPY calendar.
    """
    S, Q, V, V3, SMH = px["SPY"], px["QQQ"], px["VIX"], px["VIX3M"], px["SMH"]
    sect = [t for t in SECTORS if t in px]
    ai = [t for t in AI_CHAIN if t in px]
    ma = lambda p, n: p.rolling(n).mean()
    M = {}
    for n, p in [("QQQ", Q), ("SPY", S)]:
        r = p.pct_change()
        M[n + "_1d"] = r * 100
        M[n + "_sig"] = r / r.rolling(60).std().shift(1)
        M[n + "_dd63"] = (p / p.rolling(63).max() - 1) * 100
        M[n + "_5d"] = p.pct_change(5) * 100
        M[n + "_20d"] = p.pct_change(20) * 100
        for w in (20, 50, 100, 200):
            M[f"{n}距{w}日线"] = (p / ma(p, w) - 1) * 100
        M[n + "距半年低点"] = (p / p.rolling(126).min() - 1) * 100
        M[n + "_RSI"] = rsi(p)
        M[n] = p
        M[n + "_dd250"] = (p / p.rolling(250).max() - 1) * 100
    M["VIX"] = V
    M["VIX_5d"] = V.pct_change(5) * 100
    M["VIX/VIX3M"] = V / V3
    M["MOVE"] = px["MOVE"]
    M["10Y"] = px["TNX"]
    M["10Y_10dbp"] = (px["TNX"] - px["TNX"].shift(10)) * 100
    M["HYG-IEF_10d"] = (px["HYG"].pct_change(10) - px["IEF"].pct_change(10)) * 100
    sp = px[sect]
    nn = sp.notna().sum(axis=1)
    M["行业破50日线"] = (sp < ma(sp, 50)).sum(axis=1) / nn * 100
    M["行业5日下跌占比"] = ((sp.pct_change() < 0).sum(axis=1) / nn * 100).rolling(5).mean()
    na = px[ai].notna().sum(axis=1)
    M["AI站上50日线"] = (px[ai] > ma(px[ai], 50)).sum(axis=1) / na * 100
    M["AI20日涨超25%占比"] = (px[ai].pct_change(20) > 0.25).sum(axis=1) / na * 100
    M["AI120日涨超50%占比"] = (px[ai].pct_change(120) > 0.5).sum(axis=1) / na * 100
    M["AI20日涨超25%"] = (px[ai].pct_change(20) > 0.25).sum(axis=1)
    M["AI家数"] = na
    M["MTUM/SPY5d"] = (px["MTUM"] / S).pct_change(5) * 100
    M["TQQQ5d"] = px["TQQQ"].pct_change(5) * 100
    M["TQQQ60d"] = px["TQQQ"].pct_change(60) * 100
    M["SOXL60d"] = px["SOXL"].pct_change(60) * 100
    M["SOXL20d"] = px["SOXL"].pct_change(20) * 100
    M["TLT10d"] = px["TLT"].pct_change(10) * 100
    M["SPY10d"] = S.pct_change(10) * 100
    M["日元5d"] = -px["JPY=X"].pct_change(5) * 100
    M["黄金5d"] = px["GLD"].pct_change(5) * 100
    M["比特币5d"] = px["BTC-USD"].pct_change(5) * 100
    M["SMH20d"] = SMH.pct_change(20) * 100
    M["SMH_RSI"] = rsi(SMH)
    for w in (20, 50, 200):
        M[f"SMH距{w}日线"] = (SMH / ma(SMH, w) - 1) * 100
    M["SMH相对QQQ20d"] = M["SMH20d"] - M["QQQ_20d"]
    up = (Q.pct_change() > 0).astype(float)
    M["QQQ15日上涨天数"] = up.rolling(15).sum()
    for k, v in flows.items():
        if not k.startswith("_"):
            M[k] = v
    M = pd.DataFrame(M)
    if "资管净多%" in M:
        M["资管净多分位"] = _pct_rank(M["资管净多%"])
    ai_cols = [t for t in ai if t in px]
    if ai_cols:
        ew = (1 + px[ai_cols].pct_change(fill_method=None).mean(axis=1)).cumprod()
        M["AI超额120日"] = (ew.pct_change(120) - S.pct_change(120)) * 100
    return M


DIM_INPUTS = {
    "fear": {
        "下跌冲击": ["QQQ_sig", "SPY_sig", "QQQ_5d", "SPY_5d", "QQQ_dd63", "SPY_dd63"],
        "恐慌情绪": ["VIX", "VIX/VIX3M", "VIX_5d"],
        "债市信用": ["MOVE", "10Y_10dbp", "HYG-IEF_10d"],
        "超卖扩散": ["行业破50日线", "行业5日下跌占比", "QQQ_RSI"],
        "去杠杆": ["MTUM/SPY5d", "TQQQ5d", "SPY10d", "TLT10d", "QQQ_5d", "黄金5d", "比特币5d", "日元5d"],
        "资金与杠杆": ["杠杆ETF调仓亿", "SPDR资金5日%", "杠杆基金4周变化", "SOFR-IORB基点", "净流动性4周%", "个股看跌看涨5日"],
    },
    "greed": {
        "超买": ["QQQ_RSI", "SMH_RSI", "QQQ距20日线", "SMH距20日线"],
        "连续上涨": ["QQQ_20d", "SMH20d", "QQQ15日上涨天数"],
        "多头与杠杆": ["TQQQ60d", "SOXL60d", "VIX", "杠杆ETF净申购20日%", "融资余额同比%", "资管净多分位", "个股看跌看涨5日"],
        "获利盘": ["QQQ距200日线", "SMH距200日线", "AI120日涨超50%占比"],
        "情绪普涨": ["AI站上50日线", "AI20日涨超25%占比", "SMH相对QQQ20d"],
    },
}


def dimensions(M):
    """Fear/greed dimension frames — exact comp.py formulas."""
    F = {}
    F["下跌冲击"] = _mean(
        _worst(sc(-M.QQQ_sig, 1, 5), sc(-M.SPY_sig, 1, 5)),
        _worst(sc(-M.QQQ_5d, 1, 10), sc(-M.SPY_5d, 1, 8)),
        _worst(sc(-M.QQQ_dd63, 3, 20), sc(-M.SPY_dd63, 3, 15)))
    F["恐慌情绪"] = _mean(sc(M.VIX, 15, 45), sc(M["VIX/VIX3M"], 0.85, 1.15), sc(M.VIX_5d, 0, 80))
    F["债市信用"] = _mean(sc(M.MOVE, 80, 160), sc(M["10Y_10dbp"].abs(), 10, 60), sc(-M["HYG-IEF_10d"], 0, 6))
    F["超卖扩散"] = _mean(sc(M["行业破50日线"], 30, 100), sc(M["行业5日下跌占比"], 50, 85), sc(50 - M.QQQ_RSI, 5, 30))
    sb = pd.concat([-M.SPY10d, -M.TLT10d], axis=1).min(axis=1)
    co = pd.concat([-M.QQQ_5d / 5, -M["黄金5d"] / 3, -M["比特币5d"] / 12], axis=1).min(axis=1)
    F["去杠杆"] = _mean(sc(-M["MTUM/SPY5d"], 0, 6), sc(-M.TQQQ5d, 0, 30), sc(sb, 0, 5), sc(co, 0, 1.5), sc(M["日元5d"], 0, 6))
    F["资金与杠杆"] = _mean(
        sc(-M["杠杆ETF调仓亿"], 10, 120), sc(-M["SPDR资金5日%"], 0, 2.5),
        sc(-M["杠杆基金4周变化"], 0, 10), sc(M["SOFR-IORB基点"], 0, 15),
        sc(-M["净流动性4周%"], 0, 5), sc(M["个股看跌看涨5日"], 0.6, 0.95))
    G = {}
    G["超买"] = _mean(sc(M.QQQ_RSI, 55, 85), sc(M.SMH_RSI, 55, 88), sc(M["QQQ距20日线"], 0, 8), sc(M["SMH距20日线"], 0, 18))
    G["连续上涨"] = _mean(sc(M.QQQ_20d, 2, 12), sc(M.SMH20d, 5, 35), sc(M["QQQ15日上涨天数"], 8, 13))
    G["多头与杠杆"] = _mean(
        sc(M.TQQQ60d, 10, 90), sc(M.SOXL60d, 20, 250), sc(-M.VIX, -18, -11),
        sc(M["杠杆ETF净申购20日%"], 0, 25), sc(M["融资余额同比%"], 10, 40),
        sc(M["资管净多分位"], 60, 100), sc(-M["个股看跌看涨5日"], -0.6, -0.42))
    G["获利盘"] = _mean(sc(M["QQQ距200日线"], 5, 25), sc(M["SMH距200日线"], 10, 70), sc(M["AI120日涨超50%占比"], 0, 60))
    G["情绪普涨"] = _mean(sc(M["AI站上50日线"], 60, 100), sc(M["AI20日涨超25%占比"], 0, 50), sc(M["SMH相对QQQ20d"], 0, 20))
    return pd.DataFrame(F), pd.DataFrame(G)


def nature(gi, sh, ac):
    if ac >= 45 and sh >= 40:
        return "堆积型过热：超买叠加多头、杠杆与获利盘堆积，遇利空易集中兑现"
    if ac >= 45:
        return "堆积未释放：短期已降温，但获利盘与杠杆仍在高位"
    if gi >= 25 and sh >= ac + 25 and ac < 25:
        return "超卖反弹型：短期急涨，但多头与获利盘并未堆积"
    return ""


def stage(f_level, g_level):
    fi, gi = min(int(f_level), 4), min(int(g_level), 4)
    if fi >= 2 and fi >= gi:
        return -(fi - 1)
    if gi >= 2:
        return gi - 1
    return 0


def compute_day(M, F, G, day):
    """One day's full record (prototype row shape)."""
    FI, GI = F.mean(axis=1), G.mean(axis=1)
    fl = float(np.interp(FI.fillna(0)[day], FEAR_LEVELS, [0, 1, 2, 3, 4, 5]))
    gl = float(np.interp(GI.fillna(0)[day], GREED_LEVELS, [0, 1, 2, 3, 4, 5]))
    SH = G[["超买", "连续上涨", "情绪普涨"]].mean(axis=1)
    AC = G[["多头与杠杆", "获利盘"]].mean(axis=1)
    reb = _mean(sc(FI.rolling(20).max(), 20, 60),
                sc(M["QQQ距半年低点"].where(M.QQQ_dd250 < -8), 3, 15), 100 - G["获利盘"])
    missing = [
        ind for side in DIM_INPUTS.values() for inds in side.values() for ind in inds
        if ind in M.columns and (day not in M.index or pd.isna(M.loc[day, ind]))
    ]
    inputs = {k: (None if pd.isna(M.loc[day, k]) else round(float(M.loc[day, k]), 4))
              for k in M.columns if day in M.index}
    return {
        "date": day, "fear": round(float(FI[day]), 1), "greed": round(float(GI[day]), 1),
        "rebound": round(float(reb[day]), 1),
        "missing": sorted(set(missing)), "inputs": inputs,
        "fear_level": round(fl, 2), "greed_level": round(gl, 2),
        "stage": stage(fl, gl),
        "pendulum": round(float(np.clip(max(gl - 1, 0) - max(fl - 1, 0), -3.4, 3.4)), 2),
        "short_heat": round(float(SH[day]), 1), "accumulation": round(float(AC[day]), 1),
        "nature": nature(GI[day], SH[day], AC[day]),
        "dims": {"fear": {k: (None if pd.isna(F.loc[day, k]) else round(float(F.loc[day, k]))) for k in F},
                 "greed": {k: (None if pd.isna(G.loc[day, k]) else round(float(G.loc[day, k]))) for k in G}},
    }
