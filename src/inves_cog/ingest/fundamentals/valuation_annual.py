"""Optional TSM annual valuation basis; Rule A financial fields stay untouched."""

import json
import math
import re
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta

from inves_cog.ingest.fundamentals.extractors import day, extract_state

KEY = "valuation_annual_basis"
CONTRACT = "tsm_disclosed_annual_v1"
REQUIRED = {
    "RevenueFromContractsWithCustomers": "TWD",
    "DilutedEarningsLossPerShare": "TWD/shares",
    "CashFlowsFromUsedInOperatingActivities": "TWD",
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": "TWD",
    "AdjustedWeightedAverageShares": "shares",
}


def aligned_facts(data, filing):
    """Keep one issuer/filing's consolidated native-currency annual facts only."""
    end, filed, accession = str(filing["report_date"]), str(filing["filing_date"]), filing["accession"]
    if str(data.get("cik", "")).lstrip("0") != "1046179":
        raise ValueError("TSM instance issuer mismatch")
    output = {"cik": 1046179, "facts": {}}
    for tax, tags in data.get("facts", {}).items():
        for tag, node in tags.items():
            for unit, rows in node.get("units", {}).items():
                if unit not in {"TWD", "TWD/shares", "shares"}:
                    continue  # The report's convenience USD column is not FRED conversion.
                selected = {}
                for row in rows:
                    start, stop = row.get("start"), row.get("end")
                    if (
                        row.get("accn") != accession
                        or row.get("filed") != filed
                        or str(row.get("form", "")).removesuffix("/A") != "20-F"
                        or row.get("dimensions")
                        or row.get("d9_only")
                        or not stop
                        or stop > end
                        or start
                        and not 350 <= (day(stop) - day(start)).days <= 380
                    ):
                        continue
                    value = row.get("val")
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                        continue
                    identity = (start, stop)
                    if identity in selected and selected[identity]["val"] != value:
                        raise ValueError("Conflicting annual facts: " + tag)
                    selected[identity] = deepcopy(row)
                if selected:
                    output["facts"].setdefault(tax, {})[tag] = output["facts"].get(tax, {}).get(tag, {"units": {}})
                    output["facts"][tax][tag]["units"][unit] = list(selected.values())
    facts = output["facts"].get("ifrs-full", {})
    # TSM's Revenue alternative remains explicitly enumerated, never guessed.
    revenue = "RevenueFromContractsWithCustomers" if "RevenueFromContractsWithCustomers" in facts else "Revenue"
    required = {**REQUIRED}
    required[revenue] = required.pop("RevenueFromContractsWithCustomers")
    matched = {}
    for tag, unit in required.items():
        rows = [r for r in facts.get(tag, {}).get("units", {}).get(unit, []) if r.get("start") and r["end"] == end]
        if len(rows) != 1:
            raise ValueError("Missing/ambiguous aligned annual fact: " + tag)
        matched[tag] = rows[0]
    if len({r["start"] for r in matched.values()}) != 1:
        raise ValueError("Annual cashflow, EPS, revenue and weighted shares have different starts")
    return output, matched["AdjustedWeightedAverageShares"]


def attach_valuation_annual(state, data, *, filing, fx, as_of):
    if state.ticker != "TSM" or state.extractor != "fixed":
        return state
    filed = day(filing["filing_date"])
    known_at = filed + timedelta(days=1)  # No exact Accepted timestamp: conservative PIT availability.
    if known_at > day(as_of):
        return state
    proof = {
        "contract": CONTRACT,
        "known_at": str(known_at),
        "filed": str(filed),
        "accession": filing["accession"],
        "period_end": str(filing["report_date"]),
        "basis": "consolidated annual; USD per ordinary share; ADS conversion belongs to M5",
    }
    try:
        if (
            str(filing.get("cik", "")).lstrip("0") != "1046179"
            or str(filing.get("form", "")).removesuffix("/A") != "20-F"
            or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", filing["accession"])
        ):
            raise ValueError("Invalid TSM annual filing identity")
        aligned, weighted = aligned_facts(data, filing)
        annual = extract_state(aligned, ticker="TSM", as_of=known_at, foreign=True, filings=[filing], fx=fx)
        if str(annual.period_end) != str(filing["report_date"]):
            raise ValueError("Extracted annual period differs from original report")
        for key in ["rev_ttm", "ni_ttm", "eps_ttm", "fcf_ttm"]:
            if annual.values.get(key) is None or not math.isfinite(annual.values[key]):
                raise ValueError("Incomplete annual valuation field: " + key)
        if weighted["val"] <= 0:
            raise ValueError("Nonpositive diluted weighted shares")
        annual.values["diluted_shares_weighted"] = weighted["val"]
        annual.field_sources["diluted_shares_weighted"] = {
            **weighted,
            "method": "diluted_weighted_disclosed",
            "unit": "shares",
            "tag": "ifrs-full:AdjustedWeightedAverageShares",
            "period_kind": "annual",
            "duration_days": (day(weighted["end"]) - day(weighted["start"])).days,
            "security_basis": "ordinary_shares",
            "listed_share_ratio": 5,
        }
        annual.filed = known_at
        payload = json.loads(json.dumps(asdict(annual), default=str))
        payload.update(
            filed=str(annual.filed), period_end=str(annual.period_end), known_at=str(known_at), contract=CONTRACT
        )
        # Persistable values_extra JSON: no datetimes or mutable references to core fields.
        state.values[KEY] = payload
        state.field_sources[KEY] = proof
    except ValueError as exc:
        state.values[KEY] = None
        state.field_sources[KEY] = {**proof, "reason": str(exc)}
    return state
