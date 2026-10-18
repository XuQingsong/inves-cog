"""Offline diagnostic packets. This module has no model call and no database."""

import json
import random
from hashlib import sha256
from pathlib import Path


def execute_calls(*_args, **_kwargs):
    """The packet records a plan. It does not send it."""
    raise RuntimeError("诊断工具不执行调用")


def build_packet(spec):
    """Return a hashed packet, or a refusal when preregistration fails."""
    order = []
    refusal = _preregistration_error(spec)
    if refusal:
        order.append("拒绝生成")
        return _seal({"refused": True, "reason": refusal}, order)
    cells = _cells(spec)
    order.append("四格")
    deleted = _delete(spec)
    order.append("删除变体")
    placebo, flipped = _controls(spec)
    order.append("安慰剂与方向反转")
    blinded, mapping = _blind(spec, cells, placebo, flipped)
    order.append("盲审表")
    plan = _plan(cells)
    order.append("调用计划")
    ranking = _ranking(spec)
    order.append("诱饵评分")
    body = {
        "refused": False,
        "object_id": spec.get("object_id"),
        "cells": cells,
        "deleted": deleted,
        "placebo": placebo,
        "reversed": flipped,
        "blind_table": blinded,
        "blind_map": mapping,
        "call_plan": plan,
        "ranking": ranking,
        "executes_calls": False,
    }
    return _seal(body, order)


def write_packet(spec, directory):
    """Write the packet. A refusal writes only the refusal file."""
    packet = build_packet(spec)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "packet.json").write_text(_text(packet), encoding="utf-8")
    if packet.get("refused"):
        return packet
    (folder / "blind_map.json").write_text(_text(packet["blind_map"]), encoding="utf-8")
    public = {key: value for key, value in packet.items() if key != "blind_map"}
    (folder / "blind_table.json").write_text(_text(public["blind_table"]), encoding="utf-8")
    return packet


def review_files(response_path, review_path):
    """Read caller-supplied files. Neither path is a repository fixture."""
    from inves_cog.perception.attribution.chain import _apply_score

    response = json.loads(Path(response_path).read_text(encoding="utf-8"))
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    anomaly = response.get("anomaly") or {}
    items = response.get("items") or []
    scored = _apply_score(response.get("candidates") or [], anomaly, items, None)
    notes = {row.get("candidate_index"): row.get("note") for row in review.get("conclusions") or []}
    rows = []
    for index, candidate in enumerate(scored):
        evidence = candidate.get("evidence") or {}
        rows.append(
            {
                "candidate_index": index,
                "components": (evidence.get("components") if isinstance(evidence, dict) else None),
                "marks": evidence.get("diagnostics") if isinstance(evidence, dict) else None,
                "human_note": notes.get(index),
            }
        )
    return {"rows": rows, "sha256": _digest(rows)}


def main(argv):
    if len(argv) < 3 or argv[1] != "--out":
        return 2
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    write_packet(spec, argv[2])
    return 0


def _preregistration_error(spec):
    as_of = spec.get("as_of")
    generated = spec.get("reference_answers_generated_at")
    registered = {row.get("info_id"): row for row in spec.get("preregistered") or [] if isinstance(row, dict)}
    original = {item.get("info_id") for item in spec.get("materials", {}).get("original") or []}
    for item in spec.get("materials", {}).get("completed") or []:
        if not isinstance(item, dict) or item.get("info_id") in original:
            continue
        info_id = item.get("info_id")
        if item.get("published_at") is None or as_of is None or item["published_at"] >= as_of:
            return "补齐材料不在对象时点之前"
        row = registered.get(info_id)
        if row is None or row.get("registered_at") is None or generated is None or row["registered_at"] >= generated:
            return "补齐材料未在参考答案之前登记"
        if row.get("sha256") != _digest(item):
            return "补齐材料哈希与预登记不符"
    answers = spec.get("reference_answers")
    if not isinstance(answers, list) or any(
        row.get("tier") not in {"可接受", "不可接受", "集合外待盲审"} for row in answers
    ):
        return "参考答案不是三档假说"
    return None


def _cells(spec):
    materials = spec.get("materials") or {}
    extractions = spec.get("extractions") or {}
    cells = []
    for material_name in ("original", "completed"):
        allowed = {item.get("info_id") for item in materials.get(material_name) or []}
        items = [item for item in materials.get(material_name) or [] if isinstance(item, dict)]
        for extraction_name in ("model", "manual"):
            raw = ((extractions.get(extraction_name) or {}).get(material_name)) or []
            kept = [row for row in raw if isinstance(row, dict) and row.get("info_id") in allowed]
            cell = {
                "material": material_name,
                "extraction": extraction_name,
                "items": items,
                "extraction_rows": kept,
            }
            cell["sha256"] = _digest(cell)
            cells.append(cell)
    return cells


def _delete(spec):
    target_id = (spec.get("delete") or {}).get("info_id")
    items = list((spec.get("materials") or {}).get("completed") or [])
    target = next((item for item in items if item.get("info_id") == target_id), None)
    root = target.get("source_root") if isinstance(target, dict) else None
    removed = []
    kept = []
    for item in items:
        same = item.get("info_id") == target_id or (root and item.get("source_root") == root)
        if same:
            removed.append(item.get("info_id"))
            continue
        kept.append({key: value for key, value in item.items() if key not in {"summary", "claims"}})
    claims = [
        row for row in spec.get("claims") or [] if isinstance(row, dict) and row.get("info_id") not in set(removed)
    ]
    return {"removed": removed, "items": kept, "claims": claims, "sha256": _digest(removed)}


def _controls(spec):
    news = list((spec.get("materials") or {}).get("original") or [])
    placebo = {
        "kind": "安慰剂",
        "anomaly": False,
        "trade_date": (spec.get("placebo") or {}).get("trade_date"),
        "basket": (spec.get("placebo") or {}).get("basket"),
        "items": news,
    }
    direction = spec.get("direction")
    flipped = "down" if direction == "up" else "up" if direction == "down" else None
    reversed_row = {"kind": "方向反转", "direction": flipped, "items": news}
    return placebo, reversed_row


def _blind(spec, cells, placebo, flipped):
    rows = []
    for cell in cells:
        rows.append(
            {"id": f"{cell['material']}-{cell['extraction']}", "group": f"{cell['material']}/{cell['extraction']}"}
        )
    rows.append({"id": "placebo", "group": "安慰剂", "body": placebo})
    rows.append({"id": "reversed", "group": "方向反转", "body": flipped})
    seed = int(_digest({"object_id": spec.get("object_id"), "ids": [row["id"] for row in rows]})[:16], 16)
    random.Random(seed).shuffle(rows)
    blinded = [{"order": index, "id": row["id"]} for index, row in enumerate(rows)]
    mapping = [{"order": index, "id": row["id"], "group": row["group"]} for index, row in enumerate(rows)]
    return blinded, mapping


def _plan(cells):
    calls = [{"cell": f"{cell['material']}/{cell['extraction']}", "payload_sha256": cell["sha256"]} for cell in cells]
    return {"calls": calls, "total_cap": len(calls), "executes": False}


def _ranking(spec):
    from inves_cog.perception.attribution.chain import _apply_score

    anomaly = spec.get("anomaly") or {}
    items = spec.get("score_items") or []
    candidates = [spec.get("correct_candidate"), spec.get("decoy_candidate")]
    candidates = [row for row in candidates if isinstance(row, dict)]
    scored = _apply_score(candidates, anomaly, items, None)
    table = []
    for row in scored:
        evidence = row.get("evidence") or {}
        table.append(
            {
                "mechanism": row.get("mechanism"),
                "label": row.get("label"),
                "score": row.get("score"),
                "marks": evidence.get("diagnostics"),
            }
        )
    table.sort(key=lambda row: ((row["score"] is None), -(row["score"] or 0), row.get("label") or ""))
    return table


def _seal(body, order):
    sealed = dict(body)
    sealed["generation_order"] = list(order)
    sealed["sha256"] = _digest({key: value for key, value in sealed.items() if key != "sha256"})
    return sealed


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode()).hexdigest()


def _text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
