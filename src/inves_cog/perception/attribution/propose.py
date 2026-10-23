"""Candidate proposals. A wide anomaly is stored without asking the model."""

import json
from copy import deepcopy
from pathlib import Path

from inves_cog.perception.attribution.candidates import validate_candidates
from inves_cog.perception.attribution.documents import document_fields, passage_schema
from inves_cog.perception.attribution.grounding import claim_support, copy_support
from inves_cog.perception.attribution.links import inspect_links
from inves_cog.perception.attribution.material import material_fields

MECHANISMS = {"供给", "需求", "竞争", "客户融资", "估值倍数"}
PROMPT_VERSION = "evidence-bridge-v4.1-links"
_CONTRACT = Path(__file__).resolve().parents[4] / "docs/phase1/contracts/m8-candidate-prompt-v4"
_ANOMALY_KEYS = ("anomaly_id", "trade_date", "session", "baskets", "members", "direction", "universe")
_LINK_KEYS = ("links", "竞争解释", "反证条件", "证伪预测")


def candidate_instruction():
    """The v4 system message. The file is the only source."""
    return (_CONTRACT / "instruction.txt").read_text(encoding="utf-8")


def candidate_output():
    """Payload output contract. The file is the only source."""
    return json.loads((_CONTRACT / "output.json").read_text(encoding="utf-8"))


def _passage_output(output):
    """Add the passage option inside the v4 anchor template, not the filled example."""
    extra = passage_schema()
    schema = output.get("schema")
    if not isinstance(schema, dict):
        return output
    for candidate in schema.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        for link in candidate.get("links") or []:
            anchors = link.get("anchors") if isinstance(link, dict) else None
            if not isinstance(anchors, list):
                continue
            for anchor in anchors:
                if isinstance(anchor, dict):
                    anchor.update(extra)
    return output


def candidate_payload(anomaly, items, neighbors):
    rows = [_item_view(item) for item in items[:40]]
    output = candidate_output()
    if any("source_document" in row for row in rows):
        _passage_output(output)
    return {
        "anomaly": {key: anomaly[key] for key in _ANOMALY_KEYS if key in anomaly},
        "items": rows,
        "neighbors": neighbors,
        "output": output,
    }


def _item_view(item):
    published = item.get("published_at")
    if hasattr(published, "isoformat"):
        published = published.isoformat()
    view = {
        "info_id": item["info_id"],
        "published_at": published,
        "source_level": item.get("source_level"),
        "headline": item.get("headline"),
        "summary": item.get("summary"),
        "role": item.get("role"),
        "claims": [
            (
                {key: deepcopy(value) for key, value in claim.items() if key != "support"}
                if isinstance(claim, dict)
                else deepcopy(claim)
            )
            for claim in item.get("claims") or []
        ],
    }
    if any(isinstance(claim, dict) and "support" in claim for claim in item.get("claims") or []):
        view["claim_support"] = [claim_support(claim, item) for claim in item.get("claims") or []]
    # Date-only or timezone-unknown metadata is not an exact published_at.
    # Preserve its supplied bounds; this does not admit it to production windows.
    view.update(material_fields(item))
    view.update(document_fields(item))
    if item.get("published_interval") is not None:
        view["published_interval"] = deepcopy(item["published_interval"])
    return view


_NOT_OPERATING = {"price", "social_heat", "second_hit", "consensus", "flow"}
_REASONS = (
    "持仓的经营证伪或风险越限",
    "直接量化的经营变化",
    "异常中的新解释",
    "可能改变产业关系的新机制",
    "普通重复背景",
)


def review_queue(items):
    """Order the review budget. Authenticity does not set the rank, and a level-1 source is still checked."""
    if items is None:
        return None
    ordered = []
    for index, row in enumerate(items):
        rank, reason = _review_rank(row)
        ordered.append(
            (
                rank,
                index,
                {
                    "info_id": row.get("info_id"),
                    "rank": rank,
                    "reason": reason,
                    "must_verify": row.get("source_level") == 1,
                },
            )
        )
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _review_rank(row):
    held = row.get("held") is True
    if held and (row.get("falsified") is True or row.get("risk_breach") is True):
        return 1, _REASONS[0]
    if row.get("quantity") is not None and row.get("kind") not in _NOT_OPERATING:
        return 2, _REASONS[1]
    if row.get("anomaly_id") and row.get("reprint") is not True:
        return 3, _REASONS[2]
    new_edge = row.get("new_mechanism") is True or (
        row.get("mechanism") in MECHANISMS and row.get("relation_status") == "候选"
    )
    if new_edge and row.get("reprint") is not True:
        return 4, _REASONS[3]
    return 5, _REASONS[4]


def research_order(items):
    """Four research tiers. A candidate is not recent unless it is already marked recent."""
    if items is None:
        return None
    ordered = []
    for index, row in enumerate(items):
        rank, reason = _research_rank(row)
        ordered.append(
            (
                rank,
                index,
                {
                    "info_id": row.get("info_id"),
                    "rank": rank,
                    "reason": reason,
                    "operating_evidence": False,
                    "fundamental_standing": None,
                },
            )
        )
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _research_rank(row):
    if row.get("held") is True and row.get("risk") is True:
        return 1, "持仓风险"
    if row.get("candidate") is True and row.get("recent") is True:
        return 2, "近期候选"
    if row.get("driver_link") is True:
        return 3, "可改变驱动因子的关键环节"
    if row.get("unknown_anomaly") is True:
        return 4, "重大未知异常"
    return 5, None


def propose_candidates(anomaly, items, neighbors, client, universe):
    read_candidates.rejections = []
    if anomaly.get("universe") == "wide":
        return []
    if not items:
        return validate_candidates([], set(), universe)
    result = client.call("anomaly_candidates", candidate_payload(anomaly, items, neighbors))
    raw = read_candidates(soften_links(result))
    validated = validate_candidates(raw, {item["info_id"] for item in items}, universe)
    return [_gate_row(row, items, neighbors) for row in validated]


def soften_links(result):
    """A non-array links field stays on the v3 path as missing evidence."""
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        return result
    rows = []
    changed = False
    for row in result["candidates"]:
        if isinstance(row, dict) and "links" in row and not isinstance(row.get("links"), list):
            copied = deepcopy(row)
            copied.pop("links", None)
            rows.append(copied)
            changed = True
        else:
            rows.append(row)
    if not changed:
        return result
    return {**result, "candidates": rows}


def _gate_row(row, items, neighbors):
    if row.get("scored") is False and "links" not in row:
        return row
    return inspect_links(row, items, neighbors)


def read_candidates(result):
    """Keep cited mechanisms. One bad candidate is dropped; every bad candidate still degrades."""
    read_candidates.rejections = []
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        raise ValueError("结构不合格")
    rows = []
    structural = 0
    for row in result["candidates"]:
        try:
            parsed = _candidate_row(row)
        except ValueError as exc:
            if str(exc) != "结构不合格":
                raise
            structural += 1
            read_candidates.rejections.append({"reason": "candidate_format_rejected", "field": _format_field(row)})
            continue
        if parsed is not None:
            rows.append(parsed)
    if structural and not rows:
        raise ValueError("结构不合格")
    return rows[:5]


def _format_field(row):
    """Name the first field that makes this candidate structurally unusable."""
    if not isinstance(row, dict):
        return "candidates"
    if not isinstance(row.get("mechanism"), str):
        return "mechanism"
    info_ids = row.get("info_ids")
    if not isinstance(info_ids, list) or any(not isinstance(item, str) or not item for item in info_ids):
        return "info_ids"
    if "links" in row and not isinstance(row.get("links"), list):
        return "links"
    for key in ("chain", "affected", "control_baskets"):
        if key in row and row[key] is not None and not isinstance(row[key], list):
            return key
    if isinstance(row.get("chain"), list):
        for item in row["chain"]:
            if not isinstance(item, dict) or not isinstance(item.get("entity_id"), str) or not item.get("entity_id"):
                return "chain"
            if "new" in item and item["new"] is not None and not isinstance(item["new"], bool):
                return "chain"
    if isinstance(row.get("affected"), list):
        for item in row["affected"]:
            if not isinstance(item, dict) or not isinstance(item.get("ticker"), str) or not item.get("ticker"):
                return "affected"
    baskets = row.get("control_baskets")
    if isinstance(baskets, list) and any(not isinstance(item, str) or not item for item in baskets):
        return "control_baskets"
    direction = row.get("direction")
    if direction is not None and direction not in {"up", "down"}:
        return "direction"
    return "candidates"


def _candidate_row(row):
    if not isinstance(row, dict):
        raise ValueError("结构不合格")
    mechanism = row.get("mechanism")
    if not isinstance(mechanism, str):
        raise ValueError("结构不合格")
    info_ids = row.get("info_ids")
    if not isinstance(info_ids, list) or any(not isinstance(item, str) or not item for item in info_ids):
        raise ValueError("结构不合格")
    if "links" in row and not isinstance(row.get("links"), list):
        raise ValueError("结构不合格")
    parsed = {
        "mechanism": mechanism,
        "info_ids": list(info_ids),
        "chain": _chain(_required_list(row, "chain")),
        "affected": _affected_rows(_required_list(row, "affected")),
        "control_baskets": _string_list(_required_list(row, "control_baskets")),
    }
    direction = row.get("direction")
    if direction is not None:
        if direction not in {"up", "down"}:
            raise ValueError("结构不合格")
        parsed["direction"] = direction
    if mechanism not in MECHANISMS:
        return None
    for key in _LINK_KEYS:
        if key in row:
            parsed[key] = deepcopy(row[key])
    return copy_support(row, parsed)


def _required_list(row, key):
    if key not in row or row[key] is None:
        return []
    value = row[key]
    if not isinstance(value, list):
        raise ValueError("结构不合格")
    return value


def _string_list(rows):
    if any(not isinstance(item, str) or not item for item in rows):
        raise ValueError("结构不合格")
    return list(rows)


def _chain(rows):
    kept = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("entity_id"), str) or not row["entity_id"]:
            raise ValueError("结构不合格")
        item = {"entity_id": row["entity_id"]}
        if "new" in row and row["new"] is not None:
            if not isinstance(row["new"], bool):
                raise ValueError("结构不合格")
            item["new"] = row["new"]
        kept.append(item)
    return kept


def _affected_rows(rows):
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("结构不合格")
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            raise ValueError("结构不合格")
        item = {"ticker": ticker}
        if "basket_id" in row and row["basket_id"] is not None:
            basket = row["basket_id"]
            if not isinstance(basket, str):
                raise ValueError("结构不合格")
            if basket:
                item["basket_id"] = basket
        if "direction" in row and row["direction"] is not None:
            if row["direction"] not in {"up", "down"}:
                raise ValueError("结构不合格")
            item["direction"] = row["direction"]
        kept.append(item)
    return kept
