import psycopg, json, os, sys, csv, statistics
from psycopg.rows import dict_row
from datetime import date, timedelta

sys.path.insert(0, "src")
from inves_cog.valuation.panel import build_panel, fridays, CYCLICAL, FINANCIAL, FWD_WEEKS
from inves_cog.ingest.fundamentals.repository import state_from_row

conn = psycopg.connect("postgresql://xuqingsong@localhost:5432/inves_cog_bt", row_factory=dict_row, autocommit=True)
tl = json.load(open("/tmp/sp500_timeline.json"))
current = {k: date.fromisoformat(v) for k, v in tl["current"].items()}
exits = {k: date.fromisoformat(v) for k, v in tl["exits"].items()}
members = sorted(set(current) | set(exits))
# prices
rows = conn.execute(
    "SELECT ticker, trade_date, close, adj_factor FROM ingest.bars_daily ORDER BY trade_date"
).fetchall()
prices = {}
removed = json.load(open("/tmp/removed_names.json"))
trunc_decisions = {}
for r in rows:
    t, d = r["ticker"], r["trade_date"]
    if t in exits and d > exits[t]:
        trunc_decisions.setdefault(
            t,
            (
                removed.get(t, [{}])[-1].get("reason", "?")
                if isinstance(removed.get(t), list) and removed.get(t)
                else "exited"
            ),
        )
        continue
    prices.setdefault(t, {})[d] = r
# states per member from local fin_state
states_map = {}
for t in members:
    cur = conn.execute(
        "SELECT * FROM fundamentals.fin_state WHERE ticker=%s AND extractor='fixed' ORDER BY filed", (t,)
    )
    states_map[t] = [state_from_row(r) for r in cur.fetchall()]
panel = build_panel(
    conn,
    members,
    {t: {d: {"close": r["close"]} for d, r in rows.items()} for t, rows in prices.items()},
    states_map,
    prices.get("SPY", {}),
)


def is_member(t, d):
    if t in current and current[t] <= d:
        return True
    if t in exits and d < exits[t]:
        return True
    return False


panel = [r for r in panel if is_member(r["ticker"], r["date"])]
OUT = os.path.expanduser("~/inves-cog-bt/valuation")
os.makedirs(OUT, exist_ok=True)
import bisect

spy_adj = {d: r["close"] * (r["adj_factor"] or 1) for d, r in prices.get("SPY", {}).items()}
spy_days = sorted(spy_adj)
adjc = {}


def near(days, tgt, tol=4):
    i = bisect.bisect_right(days, tgt + timedelta(days=tol)) - 1
    return days[i] if i >= 0 and days[i] >= tgt - timedelta(days=tol) else None


def last_le(days, d):
    i = bisect.bisect_right(days, d) - 1
    return days[i] if i >= 0 else None


for r in panel:
    t, d0 = r["ticker"], r["date"]
    if t not in adjc:
        a = {d: r2["close"] * (r2["adj_factor"] or 1) for d, r2 in prices.get(t, {}).items()}
        adjc[t] = (a, sorted(a))
    adj, days = adjc[t]
    if not days:
        continue
    dp = last_le(days, d0)
    ds = last_le(spy_days, d0)
    if not dp or not ds:
        continue
    p0, s0 = adj[dp], spy_adj[ds]
    for w in FWD_WEEKS:
        tgt = d0 + timedelta(weeks=w)
        c = near(days, tgt)
        sd = near(spy_days, tgt)
        if not c and t in exits and days and tgt > max(days):
            c = max(days)  # acquired/delisted: terminal value = last trading price
        r[f"fwd{w}"] = round(100 * ((adj[c] / p0 - 1) - (spy_adj[sd] / s0 - 1)), 2) if c and sd and s0 else None
keys = sorted({k for r in panel for k in r})
with open(f"{OUT}/panel_sp500.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in panel:
        w.writerow({k: r.get(k) for k in keys})
# coverage gate
gate = {}
for year in range(2018, 2027):
    yr_rows = [r for r in panel if r["date"].year == year]
    members_y = {
        t
        for t in members
        if (t in current and current[t] <= date(year, 12, 31)) or (t in exits and exits[t] > date(year, 1, 1))
    }
    with_px = {r["ticker"] for r in yr_rows if r.get("close")}
    with_e = {r["ticker"] for r in yr_rows if r.get("e_next") and r["e_next"] > 0}
    leavers_y = {s for s, e in exits.items() if e.year == year}
    leaver_e = leavers_y & with_e
    gate[year] = {
        "members": len(members_y),
        "with_px": len(with_px),
        "with_e": len(with_e),
        "pct": round(100 * len(with_e) / max(1, len(members_y)), 1),
        "leavers": len(leavers_y),
        "leaver_e": len(leaver_e),
        "leaver_pct": round(100 * len(leaver_e) / max(1, len(leavers_y)), 1) if leavers_y else None,
    }
# sanity: 10 random incl 3 leavers + MA
import random

random.seed(7)
leavers_rows = [r for r in panel if r["ticker"] in exits]
sample = (
    random.sample(leavers_rows, min(3, len(leavers_rows)))
    + random.sample([r for r in panel if r["ticker"] not in exits], 6)
    + [r for r in panel if r["ticker"] == "MA"][-1:]
)
gate["sanity"] = [{k: r.get(k) for k in ("ticker", "date", "close", "ev", "m8")} for r in sample]
gate["truncations"] = {t: r for t, r in sorted(trunc_decisions.items())}
json.dump(gate, open(f"{OUT}/coverage.json", "w"), indent=1, default=str)
for y, g in gate.items():
    if y == "sanity":
        continue
    print(y, g)
print("sanity:", gate["sanity"])
print("truncated leavers:", len(trunc_decisions))
