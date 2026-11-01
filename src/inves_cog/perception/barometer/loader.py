"""Load barometer inputs from prod DB → the px DataFrame + flows series comp.py needs.

bars_daily is canonical where covered (SPY/QQQ/SMH/sectors/AI chain/MTUM);
yahoo_px_* observations fill the rest (TQQQ/SOXL/GLD/HYG/IEF/TLT/JPY=X/BTC/^MOVE).
PIT: every value is the latest with published_at <= asof for flows inputs.
"""
import logging
from datetime import date, timedelta

import pandas as pd

from inves_cog.ingest.market import NY
from inves_cog.perception.barometer.compute import SPDR_FLOW

log = logging.getLogger(__name__)

BARS_TICKERS = ["SPY", "QQQ", "SMH", "MTUM"]
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
AI_CHAIN = ["NVDA", "AMD", "AVGO", "MRVL", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MU",
            "SNDK", "WDC", "DELL", "SMCI", "ANET", "CIEN", "COHR", "VRT", "GEV", "CEG",
            "INTC", "ARM", "QCOM"]
YAHOO = {"TQQQ": "yahoo_px_tqqq", "SOXL": "yahoo_px_soxl", "GLD": "yahoo_px_gld",
         "HYG": "yahoo_px_hyg", "IEF": "yahoo_px_ief", "TLT": "yahoo_px_tlt",
         "JPY=X": "yahoo_px_jpyx", "BTC-USD": "yahoo_px_btcusd", "MOVE": "yahoo_px_move"}
# VIX/VIX3M/10Y live in macro/flows series
MACRO = {"VIX": ("ingest.macro_observations", "VIX_CBOE"),
         "VIX3M": ("ingest.macro_observations", "VIX3M_CBOE"),
         "TNX": ("flows.observations", "yahoo_px_tnx")}


def _series(conn, table, series_id, end):
    date_col = "observation_date" if "macro_observations" in table else "obs_date"
    rows = conn.execute(
        f"SELECT {date_col} AS d, value FROM {table} WHERE series_id=%s AND {date_col} <= %s "
        "ORDER BY 1", (series_id, end)).fetchall()
    return pd.Series({pd.Timestamp(r["d"]): float(r["value"]) for r in rows if r["value"] is not None})


def price_frame(conn, end, start=None):
    """px DataFrame like comp.py: bars_daily tickers + yahoo_px_/macro columns."""
    cols = {}
    tickers = BARS_TICKERS + SECTORS + AI_CHAIN
    rows = conn.execute(
        "SELECT ticker, trade_date AS d, close*adj_factor AS c FROM ingest.bars_daily "
        "WHERE ticker = ANY(%s) AND trade_date <= %s ORDER BY 1,2",
        (tickers, end)).fetchall()
    per = {}
    for r in rows:
        per.setdefault(r["ticker"], []).append((pd.Timestamp(r["d"]), float(r["c"])))
    for t, pairs in per.items():
        cols[t] = pd.Series(dict(pairs))
    for t, sid in YAHOO.items():
        cols[t] = _series(conn, "flows.observations", sid, end)
    for t, (table, sid) in MACRO.items():
        cols[t] = _series(conn, table, sid, end)
    px = pd.DataFrame(cols).sort_index()
    if "SPY" in px:
        idx = px["SPY"].dropna().index
        px = px.reindex(idx).ffill(limit=3)
    if start is not None:
        px = px.loc[px.index >= pd.Timestamp(start) - pd.Timedelta(days=400)]
    return px


def flows_inputs(conn, idx, closes):
    """flows.* money/leverage inputs, PIT-aligned to the trading calendar (idx).

    Ported 1:1 from comp.py: onidx aligns each series to trading days by its
    published_at date (data date + publication lag already applied).
    """
    def onidx(s):
        s = s.dropna().sort_index()
        return s.reindex(idx.union(s.index)).ffill().reindex(idx)

    def obs(sid, pit_col="published_at"):
        rows = conn.execute(
            "SELECT obs_date AS d, value, published_at AS p FROM flows.observations "
            "WHERE series_id=%s ORDER BY published_at", (sid,)).fetchall()
        # series keyed by the PUBLICATION date (PIT): value visible from published_at
        return pd.Series({pd.Timestamp(r["p"]).tz_convert(NY).normalize().tz_localize(None): float(r["value"])
                          for r in rows if r["value"] is not None}).groupby(level=0).last()

    out = {}
    # --- levered ETF rebalance + net subscription + SPDR flows (same math as comp.py) ---
    etf = conn.execute(
        "SELECT ticker, date AS d, COALESCE(aum, shares*nav) AS aum, nav FROM flows.etf_daily "
        "WHERE nav IS NOT NULL AND COALESCE(aum, shares*nav) IS NOT NULL ORDER BY 1,2").fetchall()
    E = {}
    for r in etf:
        E.setdefault(r["ticker"], []).append(r)
    def etf_df(t):
        d = pd.DataFrame(E.get(t, [])).set_index("d").sort_index() if E.get(t) else None
        if d is None or d.empty:
            return None
        d.index = pd.to_datetime(d.index)
        return d.drop_duplicates()

    def flow(t):
        d = etf_df(t)
        return (d.aum - d.aum.shift(1) * d.nav / d.nav.shift(1)) if d is not None else pd.Series(dtype=float)

    LEV = {"TQQQ": (3, "QQQ"), "UPRO": (3, "SPY"), "QLD": (2, "QQQ"), "SSO": (2, "SPY"),
           "USD": (2, "SMH"), "SQQQ": (-3, "QQQ"), "SPXU": (-3, "SPY"),
           "QID": (-2, "QQQ"), "SDS": (-2, "SPY")}
    # underlying returns come from the price frame; caller passes closes via M later —
    # here we return the per-ticker series pieces; runner assembles.
    reb = levflow = levaum = None
    for t, (L, u) in LEV.items():
        a = onidx(etf_df(t).aum) if etf_df(t) is not None else pd.Series(dtype=float)
        piece = (a.shift(1) * L * (L - 1) * closes[u].pct_change()).fillna(0)
        reb = piece if reb is None else reb + piece
        if L > 0:
            f = onidx(flow(t)).fillna(0)
            levflow = f if levflow is None else levflow + f
            levaum = a.fillna(0) if levaum is None else levaum + a.fillna(0)
    out["杠杆ETF调仓亿"] = (reb / 1e8) if reb is not None else pd.Series(dtype=float)
    out["杠杆ETF净申购20日%"] = (levflow.rolling(20).sum() / levaum.shift(20) * 100) if levaum is not None else pd.Series(dtype=float)
    spf = [onidx(flow(t)).fillna(0) for t in SPDR_FLOW if etf_df(t) is not None]
    spa = [onidx(etf_df(t).aum).fillna(0) for t in SPDR_FLOW if etf_df(t) is not None]
    if spf:
        out["SPDR资金5日%"] = sum(spf).rolling(5).sum() / sum(spa).shift(5) * 100
    # --- CFTC lev/am net % (pivoted trader_class rows; PIT by release_at) ---
    rows = conn.execute(
        "SELECT market, trader_class, report_date AS d, long, short, open_interest, "
        "release_at AS p FROM flows.cftc_positions ORDER BY release_at").fetchall()
    nets, am = {}, {}
    for r in rows:
        mk = r["market"].split(" - ")[0]
        if not mk.startswith(("NASDAQ-100 Consolidated", "S&P 500 Consolidated")):
            continue
        if r["open_interest"] and r["long"] is not None and r["short"] is not None:
            pct = (r["long"] - r["short"]) / r["open_interest"] * 100
            tgt = nets if r["trader_class"] == "lev_money" else am if r["trader_class"] == "asset_mgr" else None
            if tgt is not None:
                tgt.setdefault(mk, {})[pd.Timestamp(r["p"]).tz_convert(NY).normalize().tz_localize(None)] = pct
    mks = sorted(nets)
    if mks:
        parts_n = [pd.Series(nets[m]) for m in mks if m in nets]
        parts_a = [pd.Series(am[m]) for m in mks if m in am]
        lev = sum(parts_n) / len(parts_n)
        amn = sum(parts_a) / len(parts_a) if parts_a else None
        out["杠杆基金净头寸%"] = onidx(lev)
        out["杠杆基金4周变化"] = onidx(lev - lev.shift(4))
        if amn is not None:
            out["资管净多%"] = onidx(amn)
    # --- FRED / margin / P-C ---
    ior = obs("fred_ioer").combine_first(obs("fred_iorb"))
    sofr = obs("fred_sofr")
    out["SOFR-IORB基点"] = onidx((sofr - ior.reindex(sofr.index).ffill()) * 100)
    wal, tga, rrp = obs("fred_walcl"), obs("fred_wtregen"), obs("fred_rrpontsyd")
    nl = wal - tga.reindex(wal.index).ffill() - rrp.reindex(wal.index).ffill() * 1000
    out["净流动性4周%"] = onidx((nl / nl.shift(4) - 1) * 100)
    mg = obs("finra_margin_debit")
    out["融资余额同比%"] = onidx((mg / mg.shift(12) - 1) * 100)
    out["融资余额亿"] = onidx(mg / 100)
    out["个股看跌看涨5日"] = obs("cboe_pc_equity").reindex(idx).rolling(5, min_periods=3).mean()
    out["2Y_126dbp"] = onidx(_series(conn, "ingest.macro_observations", "DGS2", date(2100, 1, 1)).diff(126) * 100)
    out["席勒PE"] = onidx(obs("shiller_pe"))
    out["_fund_asof"] = {"cftc": pd.Series(
        {pd.Timestamp(r["p"]).tz_convert(NY).normalize().tz_localize(None): r["d"] for r in rows if r["market"].split(" - ")[0].startswith(("NASDAQ-100 Consolidated", "S&P 500 Consolidated"))})}
    return out


