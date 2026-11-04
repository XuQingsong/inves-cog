"""P2-V1 case8: Rule A vs Rule A + overval_veto on the 59-stock universe,
2024-01-02 -> 2026-10-30. Per-ticker trade lists for the 8 named tickers,
veto events, P&L, buy-and-hold comparison, portfolio summary."""

import csv
import json
import os
import sys
from datetime import date

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from inves_cog.backtest.overval import load_quintiles, quintile_at
from inves_cog.backtest.runner import prepare_inputs, run_backtest

OUT = os.path.expanduser("~/inves-cog-bt/valuation")
os.makedirs(OUT, exist_ok=True)
PANEL = os.path.join(OUT, "panel_sp500.csv")
CASE8 = ["INTC", "NVDA", "GOOGL", "MU", "SNDK", "AMD", "TSLA", "MSFT"]
START, END = date(2024, 1, 2), date(2026, 10, 30)

conn = psycopg.connect(os.environ["INVES_COG_DATABASE_URL"], row_factory=dict_row, autocommit=True)
fin = (
    set(json.load(open("/tmp/sp500_sector.json"))["financials"]) if os.path.exists("/tmp/sp500_sector.json") else set()
)
spec0 = {"universe": "config", "start": START, "end": END, "mode": "paper", "extractor": "fixed"}
prepared = prepare_inputs(conn, spec0)
print("prepared", flush=True)

runs = {}
for label, flags in [("base", {}), ("veto", {"overval_veto": True})]:
    r = run_backtest(
        None,
        {**spec0, "label": f"case8-{label}", "flags": flags, "overval_panel": PANEL, "overval_financials": sorted(fin)},
        write=False,
        prepared=prepared,
    )
    runs[label] = r
    m = r["metrics"]
    print(f"{label}: ret {m['return_pct']:.1f}% dd {m['max_drawdown_pct']:.1f}% trades {m['trades']}", flush=True)

qmap, qdays = load_quintiles(PANEL, financials=fin)
prices = prepared["prices"]


def bh(t):
    rows = {d: r for d, r in prices.get(t, {}).items() if START <= d <= END}
    days = sorted(rows)
    if not days:
        return None
    p0 = rows[days[0]]["close"] * (rows[days[0]].get("adj_factor") or 1)
    p1 = rows[days[-1]]["close"] * (rows[days[-1]].get("adj_factor") or 1)
    return {"first_day": str(days[0]), "ret": round(100 * (p1 / p0 - 1), 1)}


# P&L per ticker: realized = sells - cost-basis of sold shares (avg cost), unrealized = held*(last-cost) vs last px
def ticker_pnl(trades, t, last_px):
    tts = sorted(
        (x for x in trades if x["ticker"] == t and x.get("fill_price")), key=lambda x: str(x.get("trade_date"))
    )
    cost, shares, realized = 0.0, 0.0, 0.0
    peak_cap = 0.0
    cap_in = 0.0
    for tr in tts:
        qty = tr.get("qty") or 0
        px = tr["fill_price"]
        if tr["side"] == "buy":
            cost += qty * px
            shares += qty
            cap_in += qty * px
            peak_cap = max(peak_cap, cap_in)
        else:
            if shares > 0:
                realized += qty * (px - cost / shares)
                cost -= qty * (cost / shares)
                shares -= qty
            cap_in = cost
    unreal = shares * (last_px - (cost / shares if shares else 0)) if shares else 0.0
    return {
        "realized": round(realized),
        "unrealized": round(unreal),
        "shares_held": shares,
        "peak_capital": round(peak_cap),
        "pnl_pct_peak": round(100 * (realized + unreal) / peak_cap, 1) if peak_cap else None,
    }


def last_px(t):
    rows = prices.get(t, {})
    days = [d for d in rows if d <= END]
    d = max(days)
    return rows[d]["close"] * (rows[d].get("adj_factor") or 1) if days else None


rows_out, summary = [], {}
for label in ("base", "veto"):
    trades = runs[label]["trades"]
    vetoes = [v for v in runs[label].get("veto_events", [])]
    for tr in trades:
        if tr["ticker"] in CASE8:
            rows_out.append(
                {
                    "run": label,
                    "ticker": tr["ticker"],
                    "trade_date": tr.get("trade_date"),
                    "action": tr.get("action"),
                    "label": tr.get("label"),
                    "side": tr["side"],
                    "qty": tr.get("qty"),
                    "fill_price": tr.get("fill_price"),
                    "notional": tr.get("notional"),
                    "reason": tr.get("reason_zh"),
                    "quintile": quintile_at(qmap, qdays, tr["ticker"], tr.get("trade_date")),
                }
            )
    for v in vetoes:
        if v["ticker"] in CASE8:
            rows_out.append(
                {
                    "run": label,
                    "ticker": v["ticker"],
                    "trade_date": v["date"],
                    "action": "VETO",
                    "label": "overval_veto",
                    "qty": "",
                    "fill_price": v["price"],
                    "notional": "",
                    "reason": "m8 top-quintile",
                    "quintile": v["quintile"],
                    "m8": v.get("m8"),
                }
            )
    summary[label] = {
        "return_pct": runs[label]["metrics"]["return_pct"],
        "max_dd": runs[label]["metrics"]["max_drawdown_pct"],
        "trades": runs[label]["metrics"]["trades"],
        "flags": runs[label]["metrics"].get("flags_counts", {}),
    }
per_t = {}
for t in CASE8:
    per_t[t] = {}
    for label in ("base", "veto"):
        px = last_px(t)
        p = ticker_pnl(runs[label]["trades"], t, px)
        p["buy_hold"] = bh(t)
        per_t[t][label] = p

keys = [
    "run",
    "ticker",
    "trade_date",
    "action",
    "label",
    "side",
    "qty",
    "fill_price",
    "notional",
    "reason",
    "quintile",
    "m8",
]
with open(f"{OUT}/case8_trades.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows_out:
        w.writerow({k: r.get(k) for k in keys})
with open(f"{OUT}/case8_summary.json", "w") as f:
    json.dump({"runs": summary, "per_ticker": per_t}, f, indent=1, default=str)
print("wrote", f"{OUT}/case8_trades.csv", f"{OUT}/case8_summary.json", flush=True)
