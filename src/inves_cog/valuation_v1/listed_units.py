"""PIT listing-unit conversions; explicit source units and an audited relationship."""

import math
from copy import deepcopy

from inves_cog.valuation_v1.annual_inputs import valuation_state
from inves_cog.valuation_v1.calculations import settings


def convert_unit(value, source, relation, as_of, *, kind):
    day = str(as_of)[:10]
    targets = {"per_share": "USD/ADS", "shares": "ADS", "price": "USD/ADS"}
    ordinary = {"per_share": "USD/ordinary_share", "shares": "ordinary_shares"}
    audit = {
        "from_unit": source.get("unit"),
        "to_unit": targets[kind],
        "source": deepcopy(source),
        "relation": deepcopy(relation),
        "as_of": day,
        "status": "known",
        "factor": None,
    }

    def unknown(reason):
        return None, {**audit, "status": "unknown", "reason": reason}

    if not source.get("source") or not source.get("known_at") or source["known_at"] > day:
        return unknown("source unit missing or not yet visible")
    if not relation.get("source") or not relation.get("known_at") or relation["known_at"] > day:
        return unknown("ADS ratio source not yet visible; historical effective date not inferred")
    try:
        if not math.isfinite(float(value)) or not math.isfinite(relation["ratio"]) or relation["ratio"] <= 0:
            return unknown("invalid value or ADS ratio")
    except (ValueError, TypeError, OverflowError, KeyError):
        return unknown("missing value or ADS ratio")
    previous = source.get("listing_conversion")
    if previous and (source.get("unit") != targets[kind] or previous.get("to_unit") != targets[kind]):
        return unknown("inconsistent already-converted unit; prevent double conversion")
    if relation["id"] in source.get("split_event_ids", []):
        return unknown("ADS relationship is already represented as a split; explicit deduplication needed")
    if source.get("unit") == targets[kind]:
        return value, {**audit, "factor": 1, "already_listed": True}
    if source.get("unit") != ordinary.get(kind):
        return unknown("per-security unit unverified; USD currency alone does not establish ADS")
    factor = 1 / relation["ratio"] if kind == "shares" else relation["ratio"]
    return value * factor, {**audit, "factor": factor, "applied_relationship_ids": [relation["id"]]}


def eps_proof(state, relation):
    components = state.field_sources.get("eps_ttm", {}).get("components", [])
    scope = relation["eps_period_ends"]
    valid = state.period_end is not None and str(state.period_end) in scope and components
    valid = valid and all(
        c.get("tag") == "ifrs-full:DilutedEarningsLossPerShare"
        and c.get("unit") in {"TWD/shares", "USD/shares"}
        and c.get("filed", "9999") <= str(state.filed)
        for c in components
    )
    return {
        "unit": "USD/ordinary_share" if valid else None,
        "source": relation["source"],
        "known_at": max(str(state.filed), relation["known_at"]),
        "raw_field_source": deepcopy(state.field_sources.get("eps_ttm", {})),
        "scope": (
            "annual EPS and equivalent ADS separately disclosed in consolidated statement F-8; "
            "original FRED conversion retained"
        ),
    }


def historical_eps(state, ticker, as_of):
    try:
        state = valuation_state(state, as_of)
    except ValueError:
        return None  # Invalid optional annual input excludes this historical sample only.
    if state is None:
        return None
    relation = settings().get("listed_units", {}).get(ticker)
    if relation is None:
        return state.values.get("eps_ttm")
    value, _ = convert_unit(state.values.get("eps_ttm"), eps_proof(state, relation), relation, as_of, kind="per_share")
    return value


def normalize_listing(inputs, state, consensus, as_of):
    relation = settings().get("listed_units", {}).get(inputs.get("ticker"))
    if relation is None or state is None:
        return inputs
    out = deepcopy(inputs)
    audits, blockers = {"eps_ntm": {"status": "absent", "reason": "no available forecast"}}, []
    weighted = state.field_sources.get("diluted_shares_weighted", {})
    fields = {
        "eps_ttm": (out.get("eps_ttm"), eps_proof(state, relation), "per_share"),
        "diluted_shares": (
            state.values.get("diluted_shares_weighted"),
            {
                "unit": "ordinary_shares"
                if (
                    weighted.get("security_basis") == "ordinary_shares"
                    and weighted.get("end") == str(state.period_end)
                    and weighted.get("method") == "diluted_weighted_disclosed"
                    and weighted.get("unit") == "shares"
                    and weighted.get("period_kind") in {"quarter", "annual"}
                )
                else None,
                "known_at": weighted.get("filed"),
                "source": deepcopy(weighted),
            },
            "shares",
        ),
        "price": (
            out.get("price"),
            {
                "unit": "USD/ADS",
                "known_at": relation["known_at"],
                "source": {
                    "instrument": inputs["ticker"],
                    "exchange": "NYSE",
                    "binding": relation["source"],
                    "feed": "existing M1 US-listed USD daily bar",
                },
            },
            "price",
        ),
    }
    if consensus is not None and out.get("eps_ntm") is not None:
        fields["eps_ntm"] = (
            out["eps_ntm"],
            {
                "unit": consensus.get("eps_security_unit"),
                "known_at": str(consensus["as_of"]),
                "source": {"snapshot_source": consensus.get("source"), "as_of": str(consensus["as_of"])},
            },
            "per_share",
        )
    for key, (value, proof, kind) in fields.items():
        converted, audit = convert_unit(value, proof, relation, as_of, kind=kind)
        audits[key] = audit
        out[key] = converted
        if converted is None:
            if key == "eps_ntm":
                # K01 / FR-M5-05: unavailable forecast uses the existing TTM
                # branch. Actual security-unit gaps remain hard blockers.
                out["consensus_next_year_eps_growth"] = None
                out["consensus_reason"] = "forecast security unit unknown; TTM fallback: " + audit["reason"]
            else:
                blockers.append({"field": key, "reason": audit["reason"], "source": audit})
    out["listed_unit_audit"] = audits
    out["listed_unit_blockers"] = blockers
    out["fcf_per_share"] = (
        out["fcf_ttm"] / out["diluted_shares"] if out.get("fcf_ttm") is not None and out["diluted_shares"] else None
    )
    return out
