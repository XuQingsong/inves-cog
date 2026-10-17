"""Claim extraction. Fields the text does not support stay absent."""

from inves_cog.perception.attribution.propose import MECHANISMS

FIELDS = ("subject", "variable", "mechanism", "direction", "quantity", "horizon", "certainty", "source_level")
_FORBIDDEN = ("score", "confidence", "fundamental", "evidence", "operating_impact_proven", "enters_hypothesis")
_TEXT = {"subject", "variable", "quantity", "horizon", "certainty"}


def claim_output():
    """Return schema carried in the payload. Claims are an array; rules sit beside it."""
    return {
        "items": [
            {
                "info_id": "string",
                "claims": [
                    {
                        "subject": "string",
                        "variable": "string",
                        "mechanism": "string",
                        "direction": "up|down",
                        "quantity": "string",
                        "horizon": "string",
                        "certainty": "string",
                        "source_level": "1|2|3|4",
                    }
                ],
            }
        ],
        "mechanism": sorted(MECHANISMS),
        "direction": ["up", "down"],
        "source_level": [1, 2, 3, 4],
        "omit_when_unsupported": True,
        "forbidden": list(_FORBIDDEN),
    }


def claim_payload(items):
    _require_shortlist(items)
    return {
        "items": [
            {"info_id": item["info_id"], "headline": item.get("headline"), "summary": item.get("summary")}
            for item in items
            if "claims" not in item
        ],
        "output": claim_output(),
    }


def normalize_claim(row):
    if not isinstance(row, dict):
        return None
    kept = {}
    for key in FIELDS:
        if key not in row or row[key] is None or not _allowed(key, row[key]):
            continue
        kept[key] = row[key]
    return kept or None


def read_claims(result):
    """Keep supported claim fields. A malformed claims value is an explicit degrade, not an empty result."""
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise ValueError("结构不合格")
    by_id = {}
    for row in result["items"]:
        if not isinstance(row, dict) or not isinstance(row.get("info_id"), str) or not row["info_id"]:
            raise ValueError("结构不合格")
        claims = row.get("claims")
        if not isinstance(claims, list):
            raise ValueError("结构不合格")
        parsed = []
        for claim in claims:
            if not isinstance(claim, dict):
                raise ValueError("结构不合格")
            kept = normalize_claim(claim)
            if kept:
                parsed.append(kept)
        by_id[row["info_id"]] = parsed
    return by_id


def _allowed(key, value):
    if key == "mechanism":
        return value in MECHANISMS
    if key == "direction":
        return value in {"up", "down"}
    if key == "source_level":
        return value in {1, 2, 3, 4}
    return key in _TEXT and isinstance(value, str)


def attach_claims(items, client):
    _require_shortlist(items)
    pending = [item for item in items if "claims" not in item]
    if not pending:
        return [dict(item) for item in items]
    result = client.call("claim_extraction", claim_payload(pending))
    by_id = read_claims(result)
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
