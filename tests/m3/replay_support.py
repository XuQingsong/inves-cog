"""Independent oracle comparison; no external project code is executed."""

import gzip
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path

from inves_cog.ingest.fundamentals.extractors import extract_state
from inves_cog.ingest.fundamentals.state import StateStore
from tests.harness.tools.golden import load_golden

ROOT = Path(__file__).resolve().parents[2]
TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax Revenues SalesRevenueNet NetIncomeLoss "
    "EarningsPerShareDiluted NetCashProvidedByUsedInOperatingActivities "
    "PaymentsToAcquirePropertyPlantAndEquipment GrossProfit"
).split()
BOOKS = {"quality": "公司质量", "growth": "成长与预期", "valuation": "估值", "timing": "入场时机"}
TIERS = {"defense": "防守", "normal": "普通", "attack": "进攻", None: None}
CERTAINTY = {"low": "低", "medium": "中", "high": "高"}
TECH = (
    "price price_vs_ma200 ma50_vs_ma200 ma200_slope20 mom3 mom6 rsi dev50 vol_ratio up_share vol20 drawdown252"
).split()


def price_rows(ticker):
    raw = json.loads(gzip.decompress(load_golden(f"v18/prices/{ticker}.json.gz")))
    result = []
    for row in raw["rows"]:
        parsed = {"trade_date": datetime.strptime(row["date"], "%m/%d/%Y").date(), "adj_factor": 1}
        for key in ("open", "close", "volume"):
            value = str(row[key]).replace("$", "").replace(",", "")
            parsed[key] = float(value) if value not in {"N/A", "--", "None"} else None
        result.append(parsed)
    return sorted(result, key=lambda row: row["trade_date"])


def states_for(ticker, last, expected_hash):
    raw = gzip.decompress((ROOT / f"tests/fixtures/phase1/m2/muse/companyfacts/{ticker}_facts.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == expected_hash
    data = json.loads(raw)
    nodes = data.get("facts", data).get("us-gaap", {})
    # Muse aacea04 code/paper_trade_2026.py L60–83: initial 2025-12-31 state, then filed dates;
    # only this project's M2 extractor is called, with price-derived values rebuilt by M3.
    days = {date(2025, 12, 31)}
    for tag in TAGS:
        for entries in nodes.get(tag, {}).get("units", {}).values():
            for row in entries:
                if str(row.get("form", "")).startswith(("10-Q", "10-K", "20-F", "6-K")):
                    day = date.fromisoformat(row["filed"])
                    if date(2026, 1, 1) <= day <= last:
                        days.add(day)
    states = []
    for day in sorted(days):
        state = extract_state(data, ticker=ticker, as_of=day, extractor="legacy", price=1)
        state.filed = day
        states.append(state)
    return StateStore(states)


def compare_frozen():
    from inves_cog.trading.scoring import score_history

    oracle = json.loads(gzip.decompress(load_golden("v18/scores_20days.json.gz")))
    hashes = load_golden("v18/companyfacts_used.json")["companyfacts_sha256_uncompressed"]
    mismatches, compared, count = [], 0, 0
    for ticker, days in oracle["scores"].items():
        last = date.fromisoformat(max(days))
        states = states_for(ticker, last, hashes[ticker])
        # Muse aacea04 code/paper_trade_v18_full30.py L193–245: run full 2026 chronology
        # before selecting the frozen 20 comparison dates, preserving tier and streak state.
        rows = score_history(
            ticker,
            price_rows(ticker),
            state_asof=states.state_asof,
            extractor="legacy",
            start=date(2026, 1, 1),
            end=last,
        )
        actuals = {str(row["signal_date"]): row for row in rows}
        for day, expected in days.items():
            actual = actuals[day]
            pairs = {key: (actual["tech"][key], expected[key]) for key in TECH}
            pairs.update({key: (actual["books"][key], expected["books"][name]) for key, name in BOOKS.items()})
            pairs.update(
                {
                    key: (actual[key], expected[key])
                    for key in ("consec_pass", "entry_pass", "hold_ok", "fund_bad", "runway_ok")
                }
            )
            pairs.update(
                rank=(actual["rank_score"], expected["rank"]),
                redlines=(actual["red_lines"], expected["redlines"]),
                tier=(TIERS[actual["tier"]], expected["tier"]),
                certainty=(CERTAINTY[actual["certainty"]], expected["certainty"]),
                hold_score=(actual["hold_score"], expected["fund_score"]),
                val_adj=(
                    actual["m31_adjusted_valuation"]
                    if actual["m31_adjusted_valuation"] is not None
                    else actual["books"]["valuation"],
                    expected.get("val_adj"),
                ),
            )
            for field, (a, b) in pairs.items():
                equal = (
                    math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
                    if (isinstance(a, (int, float)) and isinstance(b, (int, float)))
                    else a == b
                )
                if not equal:
                    mismatches.append({"ticker": ticker, "day": day, "field": field, "actual": a, "expected": b})
                compared += 1
            count += 1
    return {"states": count, "fields_compared": compared, "mismatches": mismatches}
