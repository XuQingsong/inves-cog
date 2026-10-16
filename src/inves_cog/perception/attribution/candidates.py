"""Drop candidates the model cannot support, then keep one unscored default."""

DEFAULT = "无事件/资金面"


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


def verified_from_evidence(records, *, as_of, expected_direction):
    from inves_cog.perception.attribution.operating import operating_verdict

    verdict = operating_verdict(records, as_of=as_of, expected_direction=expected_direction)
    return verdict.outcome == "支持"
