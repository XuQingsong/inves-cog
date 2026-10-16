"""Exceptional values require matching original statement facts, never an issuer waiver."""

import hashlib
import json
import math
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path

from lxml import html

TAGS = {
    "ni_ttm": {"NetIncomeLoss", "ProfitLossAttributableToOwnersOfParent", "ProfitLoss"},
    "rev_ttm": {"RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"},
    "eps_ttm": {"EarningsPerShareDiluted"},
    "shares": {
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    },
}


def local(node):
    return node.tag.split(":")[-1].lower() if isinstance(node.tag, str) else ""


def inline_facts(raw, *, source_url):
    document = html.fromstring(raw.encode() if isinstance(raw, str) else raw)
    contexts = {}
    for node in document.iter():
        if local(node) != "context":
            continue
        children = list(node.iter())
        if any(local(x) in {"explicitmember", "typedmember"} for x in children):
            continue
        values = {
            local(x): x.text.strip() for x in children if local(x) in {"startdate", "enddate", "instant"} and x.text
        }
        contexts[node.get("id")] = values
    facts = []
    for node in document.iter():
        if local(node) != "nonfraction" or node.get("contextref") not in contexts:
            continue
        tag = node.get("name", "").split(":")[-1]
        if not any(tag in names for names in TAGS.values()):
            continue
        text = "".join(node.itertext()).replace(",", "").replace("$", "").strip()
        try:
            value = float(text.replace("(", "-").replace(")", "")) * 10 ** int(node.get("scale", "0"))
            if node.get("sign") == "-":
                value = -abs(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(value):
            continue
        period = contexts[node.get("contextref")]
        facts.append(
            {
                "tag": tag,
                "value": value,
                "context_id": node.get("contextref"),
                "start": period.get("startdate"),
                "end": period.get("enddate", period.get("instant")),
                "dimensions": [],
            }
        )
    return {
        "source_url": source_url,
        "source_sha256": hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest(),
        "facts": facts,
    }


def apply_verification(state, original, *, reason):
    result = deepcopy(state)
    if state.extractor != "fixed" or "implausible_value" not in state.health_codes:
        return result
    if not original.get("source_sha256") or not original.get("source_url", "").startswith(
        "https://www.sec.gov/Archives/"
    ):
        return result
    violations = state.field_sources.get("implausible_value", {}).get("violations", [])
    required = set()
    for row in violations:
        if row["rule"] == 1:
            required.update(["ni_ttm", "rev_ttm"])
        elif row["rule"] == 2:
            required.update(["ni_ttm", "eps_ttm", "shares"])
        else:
            required.add({"ni": "ni_ttm", "eps": "eps_ttm", "rev": "rev_ttm"}.get(row.get("field"), "unknown"))
    evidence = {}
    for field in required:
        value = state.values.get(field)
        expected_end = state.values.get("shares_date") if field == "shares" else str(state.period_end)
        rows = [
            row
            for row in original["facts"]
            if row["tag"] in TAGS.get(field, set())
            and not row["dimensions"]
            and row["end"] == expected_end
            and (
                field == "shares"
                or row.get("start")
                and (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days >= 300
            )
        ]
        matched = next(
            (
                row
                for row in rows
                if value is not None and math.isclose(value, row["value"], rel_tol=1e-9, abs_tol=1e-8)
            ),
            None,
        )
        if matched is None:
            return result
        evidence[field] = matched
    if not evidence:
        return result
    result.health_codes = sorted((set(state.health_codes) - {"implausible_value", "ok"}) | {"extreme_value_verified"})
    result.field_sources.pop("implausible_value", None)
    result.field_sources["extreme_value_verified"] = {
        "source_url": original["source_url"],
        "source_sha256": original["source_sha256"],
        "verified_fields": evidence,
        "reason": reason,
        "original_violations": violations,
    }
    return result


@lru_cache(maxsize=1)
def registry():
    path = Path(__file__).resolve().parents[4] / "config/fundamental_verifications.json"
    return json.loads(path.read_text()) if path.exists() else []


def apply_registered(state):
    if state.extractor != "fixed":
        return state
    for record in registry():
        if (
            record.get("kind", "annual") == "annual"
            and record["ticker"] == state.ticker
            and record["period_end"] == str(state.period_end)
            and record.get("filed", "9999-12-31") <= str(state.filed)
        ):
            state = apply_verification(state, record["original"], reason=record["reason"])
    return state


def verify_registered_quarters(state, rows, *, as_of):
    result = deepcopy(state)
    if state.extractor != "fixed":
        return result
    for record in registry():
        if record.get("kind") != "interim" or record["ticker"] != state.ticker or record["filed"] > str(as_of):
            continue
        for row in rows:
            if (
                str(row["period_end"]) != record["period_end"]
                or row["accession"] != record["accession"]
                or row["parse_status"] != "parsed"
            ):
                continue
            if all(row.get(k) == v for k, v in record["values"].items()):
                result.health_codes = sorted((set(result.health_codes) - {"ok"}) | {"extreme_value_verified"})
                result.field_sources["extreme_value_verified"] = {
                    "reason": record["reason"],
                    "source_url": record["source_url"],
                    "source_sha256": record["source_sha256"],
                    "period_end": record["period_end"],
                    "verified_quarter_values": record["values"],
                    "ttm_verified": False,
                }
    return result
