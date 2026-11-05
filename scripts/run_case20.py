"""P2-V1 case20: Rule A vs Rule A + overval_veto, universe = 59 + KO/MCD/LULU,
2024-01-02 -> 2026-10-30. 20-ticker trade list, veto events, P&L, B&H,
and dominant entry-block reason for never-bought tickers."""

import csv
import json
import os
import sys
from datetime import date

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from inves_cog.backtest.loader import BacktestLoader
from inves_cog.backtest.overval import load_quintiles, quintile_at
from inves_cog.backtest.runner import prepare_inputs, run_backtest
from inves_cog.trading.execution.state import PARAMS
from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY, EXCLUDED

OUT = os.path.expanduser("~/inves-cog-bt/valuation")
os.makedirs(OUT, exist_ok=True)
PANEL = os.path.join(OUT, "panel_sp500.csv")
CASE20 = [
    "INTC",
    "NVDA",
    "GOOGL",
    "MU",
    "SNDK",
    "AMD",
    "TSLA",
    "MSFT",
    "UNH",
    "KO",
    "MA",
    "V",
    "NFLX",
    "META",
    "AAPL",
    "TSM",
    "AMAT",
    "MCD",
    "AMZN",
    "LULU",
]
START, END = date(2024, 1, 2), date(2026, 10, 30)

conn = psycopg.connect(os.environ["INVES_COG_DATABASE_URL"], row_factory=dict_row, autocommit=True)
universe = BacktestLoader.universe("config", PARAMS["replay_tickers"]) + ["KO", "MCD", "LULU"]
fin = (
    set(json.load(open("/tmp/sp500_sector.json"))["financials"]) if os.path.exists("/tmp/sp500_sector.json") else set()
)
spec0 = {"universe": universe, "start": START, "end": END, "mode": "paper", "extractor": "fixed"}
prepared = prepare_inputs(conn, spec0)
print("prepared", len(universe), flush=True)

runs = {}
for label, flags in [("base", {}), ("veto", {"overval_veto": True})]:
    r = run_backtest(
        None,
        {
            **spec0,
            "label": f"case20-{label}",
            "flags": flags,
            "overval_panel": PANEL,
            "overval_financials": sorted(fin),
        },
        write=False,
        prepared=prepared,
    )
    runs[label] = r
    m = r["metrics"]
    print(f"{label}: ret {m['return_pct']:.1f}% dd {m['max_drawdown_pct']:.1f}% trades {m['trades']}", flush=True)

qmap, qdays = load_quintiles(PANEL, financials=fin)
prices = prepared["prices"]
signals = prepared["signals"]


def adj_px(t, d):
    r = prices.get(t, {}).get(d)
    return r["close"] * (r.get("adj_factor") or 1) if r else None


def last_adj(t):
    days = [d for d in prices.get(t, {}) if d <= END]
    return adj_px(t, max(days)) if days else None


def bh(t):
    rows = {d: r for d, r in prices.get(t, {}).items() if START <= d <= END}
    days = sorted(rows)
    if not days:
        return None
    return round(100 * (adj_px(t, days[-1]) / adj_px(t, days[0]) - 1), 1)


def ticker_pnl(trades, t, px):
    tts = sorted(
        (x for x in trades if x["ticker"] == t and x.get("fill_price")), key=lambda x: str(x.get("trade_date"))
    )
    cost = shares = realized = peak = 0.0
    for tr in tts:
        qty, px_ = tr.get("qty") or 0, tr["fill_price"]
        if tr["side"] == "buy":
            cost += qty * px_
            shares += qty
            peak = max(peak, cost)
        else:
            if shares > 0:
                realized += qty * (px_ - cost / shares)
                cost -= qty * (cost / shares)
                shares -= qty
    unreal = shares * (px - cost / shares) if shares and px else 0.0
    return {
        "realized": round(realized),
        "unrealized": round(unreal),
        "shares_held": shares,
        "peak_capital": round(peak),
        "pnl_pct_peak": round(100 * (realized + unreal) / peak, 1) if peak else None,
    }


def block_reasons(t):
    """Dominant failing gate per signal day for a never-bought ticker."""
    counts = {}
    for day, rows in signals.get(t, {}).items():
        sc = rows[0] if isinstance(rows, list) else rows
        if not (START <= day <= END):
            continue
        if sc.get("entry_pass"):
            continue
        books, tier, lines = sc.get("books") or {}, sc.get("tier"), set(sc.get("red_lines") or [])
        if tier not in ENTRY:
            key = "no-tier"
        elif sc.get("null_reason") == "insufficient_history":
            key = "insufficient_history"
        elif not all(books.get(k) is not None and books[k] >= b for k, b in zip(BOOK_KEYS, ENTRY[tier], strict=True)):
            key = "book:" + next(
                k for k, b in zip(BOOK_KEYS, ENTRY[tier], strict=True) if books.get(k) is None or books[k] < b
            )
        elif sc.get("m32_ok") is False:
            key = "m32-guard"
        elif EXCLUDED & lines:
            key = "red_line:" + sorted(EXCLUDED & lines)[0]
        else:
            key = "other"
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get) if counts else None, counts


rows_out, summary, per_t = [], {}, {}
for label in ("base", "veto"):
    trades = runs[label]["trades"]
    vetoes = [v for v in runs[label].get("veto_events", [])]
    for tr in trades:
        if tr["ticker"] in CASE20:
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
        if v["ticker"] in CASE20:
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
for t in CASE20:
    per_t[t] = {}
    for label in ("base", "veto"):
        p = ticker_pnl(runs[label]["trades"], t, last_adj(t))
        vts = [v for v in runs[label].get("veto_events", []) if v["ticker"] == t]
        p["veto_count"] = len(vts)
        p["veto_first"] = str(min(v["date"] for v in vts)) if vts else None
        p["veto_last"] = str(max(v["date"] for v in vts)) if vts else None
        p["veto_px_range"] = (
            (round(min(v["price"] for v in vts), 2), round(max(v["price"] for v in vts), 2)) if vts else None
        )
        p["buy_hold"] = bh(t)
        if not any(tr["ticker"] == t and tr["side"] == "buy" for tr in runs[label]["trades"]):
            dom, counts = block_reasons(t)
            p["never_bought_reason"] = dom
            p["block_counts"] = counts
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
with open(f"{OUT}/case20_trades.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in sorted(rows_out, key=lambda r: (r["ticker"], str(r["trade_date"]))):
        w.writerow({k: r.get(k) for k in keys})
with open(f"{OUT}/case20_summary.json", "w") as f:
    json.dump({"runs": summary, "per_ticker": per_t}, f, indent=1, default=str)
print("wrote", f"{OUT}/case20_trades.csv", f"{OUT}/case20_summary.json", flush=True)
