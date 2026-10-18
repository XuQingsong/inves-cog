"""Optional version-bound body passages. Literal fidelity is not semantic proof."""

from copy import deepcopy
from hashlib import sha256
from json import dumps

from inves_cog.ingest.info import extraction_body
from inves_cog.perception.attribution.material import material_fields

_SOURCE = (
    "info_id",
    "headline",
    "summary",
    "body",
    "source",
    "source_root",
    "source_level",
    "url",
    "published_at",
    "published_interval",
    "first_seen_at",
    "entities",
    "tickers",
)


def _hash(value):
    return sha256(
        dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _record_hash(item):
    return _hash({**{key: item.get(key) for key in _SOURCE}, **material_fields(item)})


def make_document(item, spans, *, char_budget):
    """Construct explicitly selected passages; no ranking or silent truncation."""
    if type(char_budget) is not int or char_budget < 0:
        raise ValueError("原文片段预算无效")
    body = item.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("原文正文缺失")
    text = extraction_body(body)
    if not text or not isinstance(spans, list) or not spans:
        raise ValueError("原文片段缺失")
    if not isinstance(item.get("info_id"), str) or not item["info_id"]:
        raise ValueError("原文编号缺失")
    record_hash = _record_hash(item)
    passages, omitted = [], []
    previous = 0
    used = 0
    for span in spans:
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            raise ValueError("原文片段坐标无效")
        begin, end = span
        if type(begin) is not int or type(end) is not int or not previous <= begin < end <= len(text):
            raise ValueError("原文片段坐标无效")
        if begin > previous:
            omitted.append([previous, begin])
        used += end - begin
        if used > char_budget:
            raise ValueError("原文片段超预算，不得静默截断")
        passages.append(
            {"passage_id": _hash([record_hash, begin, end]), "begin": begin, "end": end, "text": text[begin:end]}
        )
        previous = end
    if previous < len(text):
        omitted.append([previous, len(text)])
    return {
        "version": 1,
        "source_record_hash": record_hash,
        "source_text_hash": _hash(text),
        "normalization": "R19-nfkc-visible-body-v1",
        "read_mode": "current_review" if item.get("evidence_role") == "current_context" else "source_record",
        "available_chars": len(text),
        "passages": passages,
        "omitted_ranges": omitted,
    }


def document_fields(item):
    """Validate against this supplied source before either model receives it."""
    if "source_document" not in item:
        return {}
    document = item["source_document"]
    if (
        not isinstance(document, dict)
        or type(document.get("version")) is not int
        or type(document.get("available_chars")) is not int
    ):
        raise ValueError("原文片段结构无效")
    rows = document.get("passages")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("原文片段结构无效")
    spans = [[row.get("begin"), row.get("end")] for row in rows]
    expected = make_document(item, spans, char_budget=len(extraction_body(item.get("body") or "")))
    if document != expected:
        raise ValueError("原文片段版本或内容不符")
    return {"source_document": deepcopy(expected)}


def source_coverage(item):
    fields = document_fields(item)
    if not fields:
        return {}
    doc = fields["source_document"]
    return {
        "source_document_review": {
            **{
                key: deepcopy(doc[key])
                for key in (
                    "version",
                    "source_record_hash",
                    "source_text_hash",
                    "normalization",
                    "read_mode",
                    "available_chars",
                    "omitted_ranges",
                )
            },
            "selected_ranges": [{key: row[key] for key in ("passage_id", "begin", "end")} for row in doc["passages"]],
            "all_supplied_body_present": not doc["omitted_ranges"],
            "semantic_sufficiency": None,
            "original_article_completeness": None,
        }
    }


def passage_schema():
    return {
        "source_field": "headline|summary|passage",
        "passage_id": "for passage: copy the supplied passage_id",
        "source_record_hash": "for passage: copy the supplied source_record_hash",
        "source_text_hash": "for passage: copy the supplied source_text_hash",
        "quote_begin": "for passage: integer character offset within the selected passage",
        "quote_end": "for passage: exclusive integer character offset within the selected passage",
    }


def passage_anchor(item, reference):
    """Validate one quote inside one supplied passage, without judging inference."""
    try:
        doc = document_fields(item)["source_document"]
        if (
            reference.get("source_record_hash") != doc["source_record_hash"]
            or reference.get("source_text_hash") != doc["source_text_hash"]
        ):
            return False
        rows = [row for row in doc["passages"] if row["passage_id"] == reference.get("passage_id")]
        if len(rows) != 1:
            return False
        begin, end = reference.get("quote_begin"), reference.get("quote_end")
        return (
            type(begin) is int
            and type(end) is int
            and 0 <= begin < end <= len(rows[0]["text"])
            and rows[0]["text"][begin:end] == reference.get("quote")
        )
    except (KeyError, TypeError, ValueError):
        return False
