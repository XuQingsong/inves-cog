"""Drop candidates the model cannot support, then keep one unscored default."""

import math
from copy import deepcopy

from inves_cog.perception.attribution.evidence import basket_specificity, exposure_gradient, time_alignment
from inves_cog.perception.attribution.grounding import copy_support
from inves_cog.perception.attribution.second_hit import denial_response

_LINK_KEYS = ("links", "竞争解释", "反证条件", "证伪预测")

DEFAULT = "无事件/资金面"
_FINGERPRINTS = ("exposure_gradient", "unexposed_control", "time_order", "denial_response")


def validate_candidates(candidates, retrieved_ids, universe):
    """Keep a cited mechanism. A model score or operating label does not come through."""
    kept = []
    for candidate in candidates:
        citations = list(candidate.get("info_ids") or [])
        if not citations or any(item not in retrieved_ids for item in citations):
            continue
        kept.append(_cited(candidate, citations, universe))
    kept.append({"mechanism": DEFAULT, "info_ids": [], "affected": [], "scored": False})
    return kept


def _cited(candidate, citations, universe):
    direction = candidate.get("direction")
    copied = {
        "mechanism": candidate.get("mechanism"),
        "info_ids": citations,
        "affected": _affected(candidate.get("affected") or [], universe),
        "chain": list(candidate.get("chain") or []),
        "control_baskets": list(candidate.get("control_baskets") or []),
        "direction": direction if direction in {"up", "down"} else None,
        "scored": True,
        "score": None,
        "confidence": None,
        "fundamental": None,
        "evidence": None,
    }
    for key in _LINK_KEYS:
        if key in candidate:
            copied[key] = deepcopy(candidate[key])
    return copy_support(candidate, copied)


def _affected(rows, universe):
    kept = []
    for row in rows:
        ticker = row.get("ticker")
        if ticker not in universe:
            continue
        item = {"ticker": ticker}
        basket = row.get("basket_id")
        if isinstance(basket, str) and basket:
            item["basket_id"] = basket
        if row.get("direction") in {"up", "down"}:
            item["direction"] = row["direction"]
        kept.append(item)
    return kept


def market_confirmed(*, claim_time, response, independent, alternative):
    return (
        claim_time is True
        and response is True
        and independent is True
        and isinstance(alternative, (int, float))
        and not isinstance(alternative, bool)
        and math.isfinite(alternative)
        and 0.5 <= alternative <= 1.0
    )


def market_consensus(items):
    """Count roots, search, and sell-side notes. Social is off, and this stays off the fundamental column."""
    if items is None:
        return None
    roots = set()
    ratios = []
    sell_side = False
    sell_side_unknown = False
    for row in items:
        if row.get("kind") == "social":
            continue
        root = row.get("source_root")
        if root:
            roots.add(root)
        if row.get("search_ratio") is not None:
            ratios.append(row["search_ratio"])
        if row.get("kind") != "commentary":
            continue
        level = row.get("source_level")
        if level in (2, 3):
            sell_side = True
        elif level is None:
            sell_side_unknown = True
    if sell_side:
        commentary = True
    elif sell_side_unknown:
        commentary = None
    else:
        commentary = False
    if not ratios:
        search = None
    elif all(value == ratios[0] for value in ratios):
        search = ratios[0]
    else:
        search = None
    return {
        "source_roots": len(roots),
        "search_ratio": search,
        "sell_side": commentary,
        "social_connected": False,
        "confidence": None,
        "market_only": True,
        "fundamental_standing": None,
        "operating_evidence": False,
    }


def market_fingerprint(reading):
    """A failed check rules that explanation out. Passing checks do not name the only cause."""
    if reading is None:
        return None
    checks = {
        "exposure_gradient": _gradient_check(reading),
        "unexposed_control": _control_check(reading),
        "time_order": _order_check(reading),
        "denial_response": _denial_check(reading),
    }
    return {
        "checks": checks,
        "incompatible": [name for name in _FINGERPRINTS if checks[name] is False],
        "identifies_unique_cause": False,
        "market_association": None,
        "fundamental_standing": None,
        "operating_impact_proven": False,
    }


def _gradient_check(reading):
    if "members" not in reading or "relations" not in reading or "direction" not in reading:
        return None
    score = exposure_gradient(reading["members"], reading["relations"], direction=reading["direction"])
    if score is None:
        return None
    return score > 0


def _control_check(reading):
    if "expected" not in reading or "control" not in reading:
        return None
    score = basket_specificity(reading["expected"], reading["control"])
    if score is None:
        return None
    return score > 0


def _order_check(reading):
    published = reading.get("published")
    start = reading.get("session_start")
    end = reading.get("session_end")
    if published is None or start is None or end is None:
        return None
    return time_alignment(published, start, end) > 0


def _denial_check(reading):
    if "denial" not in reading:
        return None
    result = denial_response(reading["denial"])
    if result is None:
        return None
    return result["weakened"]


def independent_of_price(items):
    """Two source roots, a monitored heat spike, or a level-1/2/3 commentary. Price does not count."""
    roots = set()
    heat = False
    commentary = False
    for row in items:
        if row.get("kind") == "price":
            continue
        root = row.get("source_root")
        if root:
            roots.add(root)
        if row.get("heat_spike") is True and (row.get("entity") or row.get("monitor")):
            heat = True
        if row.get("kind") == "commentary" and row.get("source_level") in (1, 2, 3):
            commentary = True
    return len(roots) >= 2 or heat or commentary


def verified_from_evidence(records, *, as_of, expected_direction):
    from inves_cog.perception.attribution.operating import operating_verdict

    verdict = operating_verdict(records, as_of=as_of, expected_direction=expected_direction)
    return verdict.outcome == "支持"
