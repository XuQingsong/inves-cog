"""P2-R4 eval — local inves_cog_bt. DSN via env; ≤6 workers; checkpoint-resumable."""

import json
import os
import sys
from datetime import date

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from inves_cog.backtest.evaluate import quarter_starts, signal_level_eval
from inves_cog.backtest.runner import prepare_inputs, run_backtest

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/inves-cog-bt/p2r4")
os.makedirs(OUT, exist_ok=True)
DONE = set()
if os.path.exists(f"{OUT}/results.jsonl"):
    DONE = {json.loads(line)["label"] for line in open(f"{OUT}/results.jsonl")}


def save(label, obj):
    with open(f"{OUT}/results.jsonl", "a") as f:
        f.write(json.dumps({"label": label, **obj}, default=str) + "\n")


conn = psycopg.connect(os.environ["INVES_COG_DATABASE_URL"], row_factory=dict_row, autocommit=True)
END = date(2026, 10, 30)
V19 = {"tier_lock": True, "pullback_entry": True, "cooldown_recover": True, "chase_block": True}
V19R = {"rule_tiers": True, "pullback_entry": True, "cooldown_recover": True, "gap_judgment": True}
variants = {
    "pullback": {"pullback_entry": True},
    "cooldown": {"cooldown_recover": True},
    "chase8": {"chase_block": True},
    "chase15": {"chase_block": True, "chase_threshold": 0.15},
    "v19": V19,
    "rule_tiers": {"rule_tiers": True},
    "gap_judgment": {"gap_judgment": True},
    "v19_rules": V19R,
}
starts = quarter_starts()
spec0 = {"universe": "config", "end": END, "mode": "paper", "extractor": "fixed"}
prepared = prepare_inputs(conn, {**spec0, "start": min(starts)})
print("prepared", flush=True)
jobs = []
for st in starts:
    jobs.append((f"base-{st}", {**spec0, "start": st, "flags": {}}))
    for n, f in variants.items():
        jobs.append((f"{n}-{st}", {**spec0, "start": st, "flags": f}))
WORKERS = min(6, int(os.environ.get("BT_WORKERS", "6")))


def _job(args):
    label, spec = args
    return label, run_backtest(None, {**spec, "label": label}, write=False, prepared=prepared)["metrics"]


# sequential-safe: fork pool would pickle prepared (GBs) — run sequentially, jobs are ~30s each
for label, spec in jobs:
    if label in DONE:
        continue
    try:
        m = run_backtest(None, {**spec, "label": label}, write=False, prepared=prepared)["metrics"]
        save(
            label,
            {
                "ret": m["return_pct"],
                "dd": m["max_drawdown_pct"],
                "rdd": m.get("return_over_maxdd"),
                "trades": m["trades"],
                "win": m.get("win_rate"),
                "flags": m.get("flags_counts"),
            },
        )
        print(f"done {label}", flush=True)
    except Exception as e:
        save(label, {"error": str(e)})
for name, flags in variants.items():
    lbl = f"sig-{name}"
    if lbl in DONE:
        continue
    try:
        r = signal_level_eval(conn, {**spec0, "start": min(starts)}, {name: flags}, prepared=prepared)
        save(lbl, r[name])
        print(f"done {lbl}", flush=True)
    except Exception as e:
        save(lbl, {"error": str(e)})
print("ALL DONE", flush=True)
