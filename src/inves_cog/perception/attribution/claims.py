"""Claim extraction. Fields the text does not support stay absent."""

from inves_cog.perception.attribution.documents import document_fields, passage_schema
from inves_cog.perception.attribution.grounding import copy_support
from inves_cog.perception.attribution.material import material_fields
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
                        "support": [
                            {
                                "info_id": "string",
                                "field": "claim field name",
                                "source_field": "headline|summary",
                                "quote": "exact supplied text",
                                "comparison_basis": "string",
                                "statement_kind": "level|change|plan|realized|interpretation",
                            }
                        ],
                        "source_level": {"type": "integer", "enum": [1, 2, 3, 4]},
                    }
                ],
            }
        ],
        "mechanism": sorted(MECHANISMS),
        "direction": ["up", "down"],
        "source_level": [1, 2, 3, 4],
        "source_level_policy": (
            "Copy the input item's integer source_level; omit if absent. Never infer or regrade it."
        ),
        "fact_policy": (
            "Omit unsupported direction or mechanism. Split facts with different directions; "
            "do not infer operating changes from a rating."
        ),
        "grounding_policy": {
            "version": "literal-field-support-v1",
            "variable": (
                "Direction describes this variable against an explicit comparable baseline, not its "
                "stock-price implication. A level or unchanged value does not supply up/down. Omit "
                "unsupported fields."
            ),
            "basis": (
                "Keep comparison units, measurement basis and time separate. Incomparable reported totals "
                "do not establish realized demand change. Reported plans are not realized output; "
                "preserve future horizon."
            ),
            "anchors": (
                "For each asserted field supply an exact headline/summary quote from this item's info_id. "
                "Add comparison basis and statement kind only if supported. Quotes will be checked "
                "literally; they do not establish semantic truth or operating proof."
            ),
        },
        "omit_when_unsupported": True,
        "forbidden": list(_FORBIDDEN),
    }


def claim_payload(items):
    _require_shortlist(items)
    rows = [_item_payload(item) for item in items if "claims" not in item]
    output = claim_output()
    if any("source_document" in row for row in rows):
        output["items"][0]["claims"][0]["support"][0].update(passage_schema())
    return {"items": rows, "output": output}


def _source_level(value):
    return value if type(value) is int and value in {1, 2, 3, 4} else None


def _item_payload(item):
    row = {"info_id": item["info_id"], "headline": item.get("headline"), "summary": item.get("summary")}
    row.update(material_fields(item))
    row.update(document_fields(item))
    level = _source_level(item.get("source_level"))
    if level is not None:
        row["source_level"] = level
    return row


def normalize_claim(row):
    if not isinstance(row, dict):
        return None
    kept = {}
    for key in FIELDS:
        if key not in row or row[key] is None or not _allowed(key, row[key]):
            continue
        kept[key] = row[key]
    return copy_support(row, kept) if kept else None


def read_claims(result):
    """Keep supported claim fields. A malformed claims value is an explicit degrade, not an empty result."""
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise ValueError("结构不合格")
    by_id = {}
    for row in result["items"]:
        if not isinstance(row, dict) or not isinstance(row.get("info_id"), str) or not row["info_id"]:
            raise ValueError("结构不合格")
        if row["info_id"] in by_id:
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
        return _source_level(value) is not None
    return key in _TEXT and isinstance(value, str)


def attach_claims(items, client):
    _require_shortlist(items)
    pending = [item for item in items if "claims" not in item]
    if not pending:
        return [_bind_source_level(item, item.get("claims") or []) for item in items]
    requested = {item["info_id"] for item in pending}
    if len(requested) != len(pending):
        raise ValueError("结构不合格")
    result = client.call("claim_extraction", claim_payload(pending))
    by_id = read_claims(result)
    if set(by_id) != requested:
        raise ValueError("结构不合格")
    attached = []
    for item in items:
        claims = item.get("claims") or by_id.get(item["info_id"], [])
        attached.append(_bind_source_level(item, claims))
    return attached


def _bind_source_level(item, claims):
    """The item carries source authority; a model's level is never that authority."""
    level = _source_level(item.get("source_level"))
    bound = []
    for claim in claims:
        if not isinstance(claim, dict):
            bound.append(claim)
            continue
        row = dict(claim)
        row.pop("source_level", None)
        if level is not None:
            row["source_level"] = level
        bound.append(row)
    return {**item, "claims": bound}


def _require_shortlist(items):
    if len(items) > 40:
        raise ValueError("说法抽取只接受前 40 条")
