"""Optional disclosed valuation denominator; never replace the Rule A shares field."""

import math
from copy import deepcopy
from datetime import date

TAGS = {
    "us-gaap": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "ifrs-full": ("AdjustedWeightedAverageShares", "WeightedAverageNumberOfDilutedSharesOutstanding"),
}


def select_weighted_shares(companyfacts, *, ticker, as_of):
    """Return one disclosed duration, without adding classes, deriving or annualizing."""
    as_of = str(as_of)
    candidates, rejected = [], set()
    data = companyfacts.get("facts", companyfacts)
    for taxonomy, tags in TAGS.items():
        for priority, tag in enumerate(tags):
            for unit, rows in data.get(taxonomy, {}).get(tag, {}).get("units", {}).items():
                if unit != "shares":
                    rejected.add("weighted denominator unit is not shares")
                    continue
                for row in rows:
                    try:
                        start, end, filed = [date.fromisoformat(str(row[k])) for k in ("start", "end", "filed")]
                        days = (end - start).days + 1
                        value = float(row["val"])
                    except (KeyError, TypeError, ValueError, OverflowError):
                        rejected.add("weighted denominator duration or number invalid")
                        continue
                    if str(end) > as_of or str(filed) > as_of:
                        continue
                    kind = "quarter" if 80 <= days <= 120 else "annual" if 350 <= days <= 380 else None
                    if kind is None or not math.isfinite(value) or value <= 0:
                        rejected.add("weighted denominator duration/value invalid; cumulative counts are not quarterly")
                        continue
                    if str(row.get("form", "")).removesuffix("/A") not in {"10-Q", "10-K", "20-F", "40-F", "6-K"}:
                        rejected.add("weighted denominator filing form unverified")
                        continue
                    dims = row.get("dimensions") or {}
                    # This is the existing, explicitly validated V D9 exception.
                    allowed_v = ticker == "V" and dims == {
                        "us-gaap:StatementClassOfStockAxis": "us-gaap:CommonClassAMember"
                    }
                    if dims and not allowed_v:
                        rejected.add("unverified dimensional/share-class denominator; classes are not summed")
                        continue
                    candidates.append(
                        (
                            end,
                            filed,
                            not bool(dims),
                            kind == "quarter",
                            -priority,
                            value,
                            {
                                "method": "diluted_weighted_disclosed",
                                "tag": taxonomy + ":" + tag,
                                "unit": unit,
                                "start": str(start),
                                "end": str(end),
                                "filed": str(filed),
                                "accn": row.get("accn"),
                                "duration_days": days,
                                "period_kind": kind,
                                "security_basis": "consolidated_common_equivalent",
                                "approximation": kind == "quarter",
                                "valuation_use": "latest disclosed period denominator; not a TTM weighted average",
                                "split_basis": {
                                    "method": "as_disclosed_in_source_filing",
                                    "source_filed": str(filed),
                                    "original_adjustment_chain": deepcopy(row.get("split_adjustment", [])),
                                },
                                "dimensions": deepcopy(dims),
                                "origin": row.get("origin", "SEC_companyfacts"),
                            },
                        )
                    )
    if not candidates:
        return None, {
            "method": "diluted_weighted_disclosed",
            "reason": "; ".join(sorted(rejected)) or "diluted weighted shares tag absent in retained source",
        }
    # Consolidated disclosures take precedence over class-specific alternatives.
    latest_end = max(r[0] for r in candidates)
    current = [r for r in candidates if r[0] == latest_end]
    if any(r[2] for r in current):
        current = [r for r in current if r[2]]
    best = max(r[:5] for r in current)
    chosen = [r for r in current if r[:5] == best]
    if len({r[5] for r in chosen}) > 1:
        return None, {
            "method": "diluted_weighted_disclosed",
            "reason": "conflicting weighted denominator values for the same visible period/filing; not summed",
        }
    value, proof = chosen[0][5:]
    if ticker in {"TSM", "ASML", "NOK", "ARM", "SKHY"}:
        proof.update(
            security_basis="ordinary_shares",
            listed_share_ratio=5 if ticker == "TSM" else 1 if ticker in {"ASML", "NOK", "ARM"} else None,
            security_basis_reference="existing M2 interims.BASIS; ADS conversion must be established separately",
        )
    return value, proof


def attach_valuation_shares(state, companyfacts, *, as_of):
    if state.extractor == "fixed":
        value, proof = select_weighted_shares(
            companyfacts, ticker=state.ticker, as_of=min(str(as_of), str(state.filed))
        )
        state.values["diluted_shares_weighted"] = value
        state.field_sources["diluted_shares_weighted"] = proof
    return state
