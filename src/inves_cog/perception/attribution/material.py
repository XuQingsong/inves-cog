"""Keep source text, current review paraphrases and research gaps distinct."""

from copy import deepcopy
from re import fullmatch
from urllib.parse import urlsplit


def material_fields(item):
    """Optional provenance for model inputs; legacy source items are unchanged."""
    if "evidence_role" not in item and "source_provenance" not in item:
        return {}
    role = item.get("evidence_role")
    if role == "source" and "source_provenance" not in item:
        return {"evidence_role": role}
    if role != "current_context":
        raise ValueError("审阅说明不能作为新闻事实输入")
    provenance = item.get("source_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("当前补充材料缺来源")
    parents = provenance.get("parent_info_ids")
    if (
        not isinstance(parents, list)
        or not parents
        or any(not isinstance(x, str) or not x or x == item.get("info_id") for x in parents)
        or len(parents) != len(set(parents))
    ):
        raise ValueError("补充材料必须有独立信息编号和原来源引用")
    url = provenance.get("source_url")
    parsed = urlsplit(url) if isinstance(url, str) else None
    if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("补充材料缺公开来源URL")
    fingerprint = provenance.get("reference_record_sha256")
    if not isinstance(fingerprint, str) or not fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("补充材料缺留存记录哈希")
    if (
        provenance.get("read_mode") != "current_review"
        or provenance.get("content_kind") != "review_paraphrase"
        or item.get("source_level") is not None
    ):
        raise ValueError("当前审阅不能继承信源等级或冒称历史原件")
    keys = ("parent_info_ids", "source_url", "reference_record_sha256", "read_mode", "content_kind")
    return {"evidence_role": role, "source_provenance": {key: deepcopy(provenance[key]) for key in keys}}


def separate_review_material(items, context):
    """Assemble a new review input, without splitting or editing publisher text.

    ``context_refs`` is an explicit local catalog link, never a text heuristic.
    Unknown publication and receipt times of a rereading stay unknown. Notes
    are returned separately and must not be supplied to claim extraction.
    """
    originals, supplements, gaps = [], {}, []
    identifiers = [item["info_id"] for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("原来源编号重复")
    for original in items:
        item = deepcopy(original)
        if "claims" in item:
            raise ValueError("新输入不能携带旧模型说法")
        refs = item.pop("context_refs", [])
        if not isinstance(refs, list) or len(refs) != len(set(refs)):
            raise ValueError("补充材料引用不合格")
        originals.append(item)
        for identifier in refs:
            record = context[identifier]
            info_id = "context:" + identifier
            if info_id in identifiers:
                raise ValueError("补充材料编号与原来源冲突")
            facts = record.get("facts")
            limits = record.get("limits", [])
            if (
                not isinstance(facts, str)
                or not facts.strip()
                or not isinstance(limits, list)
                or any(not isinstance(x, str) or not x.strip() for x in limits)
            ):
                raise ValueError("事实与缺证说明必须显式分列")
            if info_id not in supplements:
                supplements[info_id] = {
                    "info_id": info_id,
                    "headline": "Current source review paraphrase",
                    "summary": facts,
                    "published_at": None,
                    "first_seen_at": None,
                    "source_level": None,
                    "source_root": item.get("source_root") or item["info_id"],
                    "evidence_role": "current_context",
                    "source_provenance": {
                        "parent_info_ids": [],
                        "source_url": record["public_url"],
                        "reference_record_sha256": record["reference_record_sha256"],
                        "read_mode": "current_review",
                        "content_kind": "review_paraphrase",
                    },
                }
            supplements[info_id]["source_provenance"]["parent_info_ids"].append(item["info_id"])
            gaps.append(
                {
                    "parent_info_id": item["info_id"],
                    "context_info_id": info_id,
                    "evidence_role": "research_gap",
                    "items": deepcopy(limits),
                }
            )
    for supplement in supplements.values():
        material_fields(supplement)
    return {"items": originals + list(supplements.values()), "research_gaps": gaps}
