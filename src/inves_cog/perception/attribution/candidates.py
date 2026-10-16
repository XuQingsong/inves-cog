"""Drop candidates the model cannot support, then keep one unscored default."""

from inves_cog.perception.attribution.evidence import basket_specificity, exposure_gradient, time_alignment
from inves_cog.perception.attribution.second_hit import denial_response

DEFAULT = "无事件/资金面"
_FINGERPRINTS = ("exposure_gradient", "unexposed_control", "time_order", "denial_response")


def validate_candidates(candidates, retrieved_ids, universe):
    kept = []
    for candidate in candidates:
        citations = list(candidate.get("info_ids") or [])
        if not citations or any(item not in retrieved_ids for item in citations):
            continue
        affected = [row for row in candidate.get("affected") or [] if row.get("ticker") in universe]
        kept.append({**candidate, "affected": affected, "scored": True})
    kept.append({"mechanism": DEFAULT, "info_ids": [], "affected": [], "scored": False})
    return kept


def market_confirmed(*, claim_time, response, independent, alternative):
    return bool(claim_time and response and independent and alternative is not None and alternative >= 0.5)


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
