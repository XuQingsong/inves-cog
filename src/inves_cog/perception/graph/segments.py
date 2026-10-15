"""Dollar exposure drafts from M2's sourced raw segments, without invented prose quotes."""

import math

from inves_cog.perception.graph.drafting import draft_id


def validate_segment_draft(row, segments, *, clock):
    matches = [
        s
        for s in segments
        if s["row_id"] == row.get("segment_id")
        or (
            row.get("segment_id") is None
            and row.get("from_entity") == s["ticker"]
            and row.get("to_entity") == s["segment_raw"]
            and row.get("accession") == s["accession"]
            and row.get("exposure_usd") == s.get("revenue")
            and row.get("exposure_asof") == str(s["period_end"])
        )
    ]
    source = matches[0] if len(matches) == 1 else None
    if source is None or source.get("revenue") is None or not math.isfinite(source["revenue"]):
        return None
    if source.get("evidence", {}).get("currency") != "USD" or source["revenue"] < 0:
        return None
    if (
        row.get("exposure_basis") != "分部收入"
        or row.get("exposure_usd") != source["revenue"]
        or row.get("accession") != source["accession"]
    ):
        return None
    proof = {
        key: source.get(key)
        for key in ["row_id", "ticker", "accession", "filed", "period_end", "segment_raw", "revenue", "evidence"]
    }
    result = {
        **row,
        "from_entity": source["ticker"],
        "to_entity": source["segment_raw"],
        "connection_type": "经营传导",
        "mechanism": "需求",
        "structured_source": proof,
        "exposure_asof": str(source["period_end"]),
        "status": "候选",
        "drafted_by": "glm-5.3",
        "drafted_at": clock.now_utc(),
        "reviewed_at": None,
    }
    return {**result, "relation_id": draft_id(result)}


def draft_segments(llm, segments, *, clock):
    reply = llm.call("exposure_draft", {"source_texts": [], "segments": segments})
    rows = [
        validate_segment_draft(row, segments, clock=clock)
        for row in reply.get("exposures", [])
        if isinstance(row, dict)
    ]
    return [row for row in rows if row is not None]
