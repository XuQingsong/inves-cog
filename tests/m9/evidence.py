"""Produce compact, explicitly synthetic M9 review examples; never a live/PIT acceptance claim."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from inves_cog.clock import FrozenClock
from inves_cog.overlay.rules import generate_overlay
from inves_cog.shadow.pipeline import MemoryOutputs, run_shadows
from tests.harness.tools.golden import load_golden
from tests.m9.fixtures import snapshot

ROOT = Path(__file__).resolve().parents[2]


def generate():
    days = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20"]
    walk = []
    for day in [*days, "2026-11-06"]:
        clock = FrozenClock(datetime.fromisoformat(day + "T12:15:00Z"))
        for branch in ("A", "B"):
            after_deadline = day >= "2026-10-20"
            lifecycle = ("条件风险" if branch == "A" else "已验证·有影响") if after_deadline else "基本面核查中"
            events = [
                {
                    "event_id": "synthetic-toshiba-" + branch,
                    "lifecycle": lifecycle,
                    "mechanism": "供给",
                    "direction": "不利",
                    "created_at": "2026-10-02T00:00:00Z",
                    "next_filing_at": "2026-11-06T12:00:00Z",
                    "affected": [
                        {"ticker": "WDC", "exposure": "直接"},
                        {"ticker": "STX", "exposure": "直接"},
                        {"ticker": "MU", "exposure": "概念关联"},
                    ],
                }
            ]
            payload = generate_overlay(events, clock=clock, version=len(walk) + 1, source_asof=clock.now_utc())
            walk.append(
                {
                    "fixture": "synthetic_branch_contract",
                    "day": day,
                    "branch": branch,
                    "cooling": {ticker: row["cooling_off"] for ticker, row in payload["tickers"].items()},
                    "payload": payload,
                }
            )
    names = [row["ticker"] for row in yaml.safe_load((ROOT / "config/universe.yaml").read_text())["stocks"]]
    golden = load_golden("m9_factor_shadow.json")["f01_growth_adjusted_valuation"]
    be = next(row["input"] for row in golden if row["id"] == "BE-like-loss")
    # LITE values are a labelled illustration of the published B1 PSG/FCF score example.
    # No claim is made that these are a real LITE quote, filing or rule-A decision.
    lite = {
        "ps": 37.2,
        "rev_growth": 60,
        "pe": None,
        "prev_eps_ttm": -1,
        "prev_net_margin_pct": -5,
        "fcf_yield": -1 / 6,
    }
    bundle = {
        "kind": "synthetic",
        "target": days[-1],
        "scores": {
            "LITE": snapshot(ticker="LITE", books={"quality": 35, "growth": 85, "valuation": 10, "timing": 70}),
            "BE": snapshot(ticker="BE"),
        },
        "factor_inputs": {"LITE": lite, "BE": be},
        "observations": {},
        "m8": {"events": []},
        "plan": {"plan_id": "synthetic-plan", "orders": []},
    }
    with TemporaryDirectory(prefix="inves-m9-evidence-") as directory:
        result = run_shadows(
            clock=FrozenClock(datetime.fromisoformat(days[-1] + "T12:20:00Z")),
            target=days[-1],
            bundle=bundle,
            tickers=names,
            outputs=MemoryOutputs(directory),
        )
    report = {
        "kind": "synthetic_offline_contract_examples",
        "closes_real_five_day_pit": False,
        "timestamp_semantics": "FrozenClock fixture timestamps only; not actual historical publication times",
        "production_writes": 0,
        "model_calls": 0,
        "toshiba_branch_walk": walk,
        "factor_sample": result["factors"],
        "tickers": len(names),
        "factor_rows": len(result["factors"]),
        "input_scope": (
            "LITE is a synthetic B1 illustration; BE uses the loader-backed BE-like golden case; "
            "other inputs explicitly missing"
        ),
        "actual_source_gaps": [
            "K01 existing M8 completed historical snapshots",
            "K02 M4/overlay dispatch ordering and winter window",
        ],
    }
    path = ROOT / "handoff/M9/synthetic-contract-evidence.json"
    metadata = {key: value for key, value in report.items() if key != "factor_sample"}
    header = json.dumps(metadata, ensure_ascii=False, default=str, allow_nan=False, indent=2)[:-2]
    rows = ",\n    ".join(
        json.dumps(row, ensure_ascii=False, default=str, allow_nan=False, sort_keys=True)
        for row in report["factor_sample"]
    )
    encoded = header + ',\n  "factor_sample": [\n    ' + rows + "\n  ]\n}\n"
    assert json.loads(encoded) == report
    path.write_text(encoded)
    print(
        json.dumps(
            {
                "evidence": str(path.relative_to(ROOT)),
                "kind": report["kind"],
                "factor_rows": report["factor_rows"],
                "toshiba_branches": len(walk),
                "closes_real_five_day_pit": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    generate()
