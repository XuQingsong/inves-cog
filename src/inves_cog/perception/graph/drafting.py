"""Evidence-bound drafts using the shared, registry-routed dialogue client."""

import hashlib
import json
import math
import re


def valid_citation(row, sources):
    citation = row.get("citation")
    if not isinstance(citation, dict):
        return False
    for source in sources:
        if citation.get("accession") != source["accession"] or citation.get("section") != source["section"]:
            continue
        start, end = citation.get("char_start"), citation.get("char_end")
        offset = source.get("char_start", 0)
        if (
            type(start) is int
            and type(end) is int
            and offset <= start < end <= offset + len(source["text"])
            and source["text"][start - offset : end - offset] == citation.get("quote")
        ):
            return True
        quote = citation.get("quote")
        if isinstance(quote, str) and quote.strip() and source["text"].count(quote) == 1:
            # Resolve exact unique source text, never a semantic approximation of a quote.
            position = source["text"].index(quote)
            citation.update(char_start=offset + position, char_end=offset + position + len(quote))
            return True
    return False


def draft_id(row):
    identity = {key: value for key, value in row.items() if key not in {"status", "drafted_at", "reviewed_at"}}
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


class DraftService:
    def __init__(self, *, llm, clock):
        self.llm, self.clock = llm, clock

    def draft(self, sources, *, relationships=True, exposures=True):
        payload = {"source_texts": sources}
        relation_reply = self.llm.call("graph_seed_draft", payload) if relationships else {}
        exposure_reply = self.llm.call("exposure_draft", payload) if exposures else {}
        relations = []
        for row in relation_reply.get("relations", []):
            if not isinstance(row, dict) or not valid_citation(row, sources):
                continue
            if row.get("connection_type") not in {"业务关系", "市场共振", "市场叙事", "经营传导"}:
                continue
            if row.get("mechanism") not in {"供给", "需求", "竞争", "客户融资", "估值倍数"}:
                continue
            if not isinstance(row.get("to_entity"), str) or not row["to_entity"].strip():
                continue
            row["from_entity"] = sources[0]["ticker"]
            relations.append(row)
        exposures = []
        for row in exposure_reply.get("exposures", []):
            if not isinstance(row, dict):
                continue
            if not (row.get("accession") or row.get("info_id")) or not valid_citation(row, sources):
                continue
            if row.get("exposure_basis") not in {"收入占比", "RPO", "合同", "应收", "预付", "分部收入"}:
                continue
            amount = row.get("exposure_usd")
            if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
                continue
            # Unsupported free-form numbers cannot become dollar exposures solely from an id.
            quoted = row["citation"]["quote"].replace(",", "")
            numbers = []
            for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(billion|million|thousand)?\b", quoted, re.I):
                scale = {"billion": 1e9, "million": 1e6, "thousand": 1e3, None: 1}[
                    match[2].lower() if match[2] else None
                ]
                numbers.append(float(match[1]) * scale)
            if amount not in numbers or not re.search(r"\$|\bUSD\b|U\.S\. dollars?", quoted, re.I):
                continue
            row["from_entity"] = sources[0]["ticker"]
            exposures.append(row)

        def attach(row):
            return {
                **row,
                "relation_id": draft_id(row),
                "status": "候选",
                "drafted_by": "glm-5.3",
                "drafted_at": self.clock.now_utc(),
                "reviewed_at": None,
            }

        return {"relations": [attach(row) for row in relations], "exposures": [attach(row) for row in exposures]}
