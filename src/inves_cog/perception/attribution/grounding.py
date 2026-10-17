"""Literal source anchors for review. They do not establish semantic support."""

from copy import deepcopy
from hashlib import sha256
from json import dumps

CLAIM_FIELDS = {"subject", "variable", "mechanism", "direction", "quantity", "horizon", "certainty"}
_TEXT = ("info_id", "ticker", "field", "source_field", "quote", "inference", "comparison_basis", "statement_kind")


def support_view(value):
    """Bound optional model annotations without accepting model verdicts or scores."""
    if not isinstance(value, list):
        return {"malformed": True}
    rows = []
    for row in value[:120]:
        if not isinstance(row, dict):
            rows.append({"malformed": True})
            continue
        kept = {key: row[key] for key in _TEXT if isinstance(row.get(key), str) and len(row[key]) <= 800}
        if row.get("malformed") or any(key in row and key not in kept for key in _TEXT):
            kept["malformed"] = True
        rows.append(kept)
    if len(value) > 120:
        rows.append({"malformed": True})
    return rows


def _source_hash(item):
    data = {key: item.get(key) for key in ("info_id", "headline", "summary")}
    return sha256(dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _anchors(support, items, *, fields=None, tickers=None, cited=None):
    sources = {}
    for item in items:
        sources.setdefault(item["info_id"], []).append(item)
    audits = []
    normalized = support_view(support)
    rows = normalized if isinstance(normalized, list) else [{"malformed": True}]
    for index, row in enumerate(rows):
        problems = []
        if not isinstance(row, dict):
            row = {"malformed": True}
        if row.get("malformed"):
            problems.append("标注结构不合格")
        info_id = row.get("info_id")
        found = sources.get(info_id) or []
        if len(found) != 1 or (cited is not None and info_id not in cited):
            problems.append("非本次唯一引用来源")
        field = row.get("source_field")
        quote = row.get("quote")
        text = found[0].get(field) if len(found) == 1 and field in {"headline", "summary"} else None
        if not isinstance(quote, str) or not quote.strip() or not isinstance(text, str) or quote not in text:
            problems.append("原文片段未精确匹配")
        if fields is not None and row.get("field") not in fields:
            problems.append("未绑定本条说法字段")
        if tickers is not None and row.get("ticker") not in tickers:
            problems.append("未绑定本候选受影响标的")
        audit = {
            "index": index,
            "info_id": info_id,
            "field": row.get("field"),
            "ticker": row.get("ticker"),
            "source_field": field,
            "literal_anchor_valid": not problems,
            "problems": problems,
            "semantic_verdict": None,
        }
        if not problems:
            audit.update(quote=quote, source_content_hash=_source_hash(found[0]))
        for key in ("inference", "comparison_basis", "statement_kind"):
            if isinstance(row.get(key), str):
                audit[key] = row[key]
        audits.append(audit)
    return audits


def claim_support(claim, item):
    if not isinstance(claim, dict):
        return {
            "kind": "literal_references_only",
            "anchors": [],
            "unanchored_fields": [],
            "malformed_claim": True,
            "semantic_verdict": None,
            "operating_impact_proven": False,
        }
    fields = {key for key in CLAIM_FIELDS if claim.get(key) is not None}
    audit = _anchors(claim.get("support", []), [item], fields=fields)
    anchored = {row["field"] for row in audit if row["literal_anchor_valid"]}
    return {
        "kind": "literal_references_only",
        "anchors": audit,
        "unanchored_fields": sorted(fields - anchored),
        "semantic_verdict": None,
        "model_annotations_unverified": True,
        "operating_impact_proven": False,
    }


def candidate_support(candidate, items):
    tickers = {row["ticker"] for row in candidate.get("affected") or []}
    audit = _anchors(candidate.get("support", []), items, tickers=tickers, cited=set(candidate.get("info_ids") or []))
    anchored = {row["ticker"] for row in audit if row["literal_anchor_valid"]}
    return {
        "kind": "literal_references_only",
        "anchors": audit,
        "unanchored_tickers": sorted(tickers - anchored),
        "semantic_verdict": None,
        "model_annotations_unverified": True,
        "operating_impact_proven": False,
    }


def copy_support(source, target):
    if "support" in source:
        target["support"] = deepcopy(support_view(source["support"]))
    return target
