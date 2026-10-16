"""Claim extraction. Fields the text does not support stay absent."""

FIELDS = ("subject", "variable", "mechanism", "direction", "quantity", "horizon", "certainty", "source_level")


def claim_payload(items):
    _require_shortlist(items)
    return {
        "items": [
            {"info_id": item["info_id"], "headline": item.get("headline"), "summary": item.get("summary")}
            for item in items
            if "claims" not in item
        ]
    }


def normalize_claim(row):
    return {key: row[key] for key in FIELDS if key in row and row[key] is not None}


def attach_claims(items, client):
    _require_shortlist(items)
    pending = [item for item in items if "claims" not in item]
    if not pending:
        return [dict(item) for item in items]
    result = client.call("claim_extraction", claim_payload(pending))
    by_id = {
        row["info_id"]: [normalize_claim(claim) for claim in row.get("claims") or []]
        for row in result.get("items") or []
    }
    attached = []
    for item in items:
        if item.get("claims"):
            attached.append(dict(item))
            continue
        attached.append({**item, "claims": by_id.get(item["info_id"], [])})
    return attached


def _require_shortlist(items):
    if len(items) > 40:
        raise ValueError("说法抽取只接受前 40 条")
