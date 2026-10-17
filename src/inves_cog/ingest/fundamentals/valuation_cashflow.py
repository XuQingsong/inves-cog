"""Optional ARM valuation cash flow; existing financial fields are untouched."""

import math
from copy import deepcopy
from datetime import date, timedelta

TAGS = {"ocf": "NetCashProvidedByUsedInOperatingActivities", "capex": "PaymentsToAcquirePropertyPlantAndEquipment"}


def paired_periods(companyfacts, as_of):
    periods = {}
    facts = companyfacts.get("facts", companyfacts).get("us-gaap", {})
    for field, tag in TAGS.items():
        for currency, rows in facts.get(tag, {}).get("units", {}).items():
            for row in rows:
                try:
                    start, end, filed = [date.fromisoformat(str(row[k])) for k in ("start", "end", "filed")]
                    value = float(row["val"])
                except (KeyError, ValueError, TypeError, OverflowError):
                    continue
                if (
                    str(filed) > as_of
                    or str(end) > as_of
                    or start > end
                    or not math.isfinite(value)
                    or row.get("dimensions")
                    or not row.get("accn")
                    or str(row.get("form", "")).removesuffix("/A") not in {"20-F", "6-K"}
                    or (field == "capex" and value < 0)
                ):
                    continue
                key = (start, end, filed, row["accn"], currency)
                component = periods.setdefault(key, {})
                values = component.setdefault(field, set())
                values.add(value)
    paired = []
    for (start, end, filed, accession, currency), values in periods.items():
        if currency != "USD" or any(len(values.get(k, ())) != 1 for k in TAGS):
            continue
        paired.append(
            {
                "start": str(start),
                "end": str(end),
                "filed": str(filed),
                "accn": accession,
                "unit": currency,
                "ocf": next(iter(values["ocf"])),
                "capex": next(iter(values["capex"])),
                "tags": {k: "us-gaap:" + v for k, v in TAGS.items()},
                "fx": {"method": "identity", "original_currency": currency, "target_currency": "USD"},
            }
        )
    return paired


def select_cashflow(companyfacts, *, period_end, as_of):
    end, as_of = str(period_end), str(as_of)[:10]
    proof = {
        "method": "valuation_ocf_minus_pure_ppe",
        "period_end": end,
        "as_of": as_of,
        "unit": "USD",
        "original_fields_unchanged": True,
    }
    periods = paired_periods(companyfacts, as_of)
    current = [p for p in periods if p["end"] == end]
    annual = [
        p for p in periods if 350 <= (date.fromisoformat(p["end"]) - date.fromisoformat(p["start"])).days + 1 <= 380
    ]
    matches = []
    for p in current:
        if p in annual:
            matches.append([(1, p)])
            continue
        start = date.fromisoformat(p["start"])
        days = (date.fromisoformat(end) - start).days + 1
        if not 80 <= days <= 300:
            continue
        for a in annual:
            if a["end"] != str(start - timedelta(days=1)):
                continue
            try:
                previous_end = date.fromisoformat(end).replace(year=date.fromisoformat(end).year - 1)
            except ValueError:
                continue
            previous = [q for q in periods if q["start"] == a["start"] and q["end"] == str(previous_end)]
            if previous:
                matches.append([(1, a), (1, p), (-1, max(previous, key=lambda q: (q["filed"], q["accn"])))])
    if not matches:
        return None, {
            **proof,
            "reason": (
                "no exact visible same-currency OCF/PPE pair and aligned annual/current/prior YTD; "
                "no investing proxy or old annual substitution"
            ),
            "missing_periods": {
                "target_end": end,
                "required": "annual + current YTD - prior matching YTD, or exact target annual",
                "paired_visible_periods": [{k: p[k] for k in ("start", "end", "filed", "unit")} for p in periods],
            },
        }
    chosen = max(
        matches, key=lambda terms: (terms[-2 if len(terms) == 3 else 0][1]["filed"], max(p["filed"] for _, p in terms))
    )
    ocf = sum(sign * p["ocf"] for sign, p in chosen)
    capex = sum(sign * p["capex"] for sign, p in chosen)
    if capex < 0:
        return None, {
            **proof,
            "reason": "aligned pure PPE aggregate has invalid negative payment sign",
            "missing_periods": {"capex_sign": "unverified"},
        }
    return ocf - capex, {
        **proof,
        "period_kind": "annual" if len(chosen) == 1 else "ttm",
        "ocf": ocf,
        "capex": capex,
        "formula": "annual + current_ytd - prior_ytd; OCF - PPE" if len(chosen) == 3 else "annual OCF - PPE",
        "components": [{"coefficient": sign, **deepcopy(p)} for sign, p in chosen],
    }


def attach_valuation_cashflow(state, companyfacts, *, as_of):
    if state.ticker == "ARM" and state.extractor == "fixed" and state.period_end is not None:
        value, proof = select_cashflow(
            companyfacts, period_end=state.period_end, as_of=min(str(as_of), str(state.filed))
        )
        state.values["valuation_fcf_ttm"] = value
        state.field_sources["valuation_fcf_ttm"] = proof
    return state
