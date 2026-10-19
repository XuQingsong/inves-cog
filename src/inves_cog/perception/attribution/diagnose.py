"""Offline diagnostic packets. This module has no model call and no database."""

import json
import random
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path


def execute_calls(*_args, **_kwargs):
    """The packet records a plan. It does not send it."""
    raise RuntimeError("诊断工具不执行调用")


_PRIVATE = {"cells", "objects", "placebo", "reversed", "blind_map", "blind_table"}
_CELL_GROUPS = (
    ("original", "model"),
    ("original", "manual"),
    ("completed", "model"),
    ("completed", "manual"),
)


def build_packet(spec):
    """Return a hashed packet, or a refusal when preregistration fails."""
    refusal = _preregistration_error(spec)
    if refusal:
        return _seal({"refused": True, "reason": refusal}, ["拒绝生成"])
    missing = _missing_target(spec)
    if missing:
        return _seal({"refused": True, "reason": missing}, ["拒绝生成"])
    objects = _objects(spec)
    deleted = _delete(spec)
    blinded, mapping = _blind(spec, objects)
    plan = _plan(spec, objects)
    ranking = _ranking(spec)
    body = {
        "refused": False,
        "object_id": spec.get("object_id"),
        "cells": objects[:4],
        "objects": objects,
        "deleted": deleted,
        "placebo": objects[4]["payload"],
        "reversed": objects[5]["payload"],
        "blind_table": blinded,
        "blind_map": mapping,
        "call_plan": plan,
        "ranking": ranking,
        "executes_calls": False,
    }
    return _seal(body, ["四格", "删除变体", "对照对象", "盲审表", "调用计划", "诱饵评分"])


def write_packet(spec, directory):
    """Write the packet. Group names stay in the map file only."""
    packet = build_packet(spec)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    public = {key: value for key, value in packet.items() if key not in _PRIVATE}
    (folder / "packet.json").write_text(_text(public), encoding="utf-8")
    if packet.get("refused"):
        return packet
    (folder / "blind_map.json").write_text(_text(packet["blind_map"]), encoding="utf-8")
    (folder / "blind_table.json").write_text(_text(packet["blind_table"]), encoding="utf-8")
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
        published = _aware(item.get("published_at"))
        cutoff = _aware(as_of)
        if published == "naive" or cutoff == "naive":
            return "时间缺少时区"
        if published is None or cutoff is None or published >= cutoff:
            return "补齐材料不在对象时点之前"
        row = registered.get(info_id)
        registered_at = _aware(None if row is None else row.get("registered_at"))
        answer_at = _aware(generated)
        if registered_at == "naive" or answer_at == "naive":
            return "时间缺少时区"
        if row is None or registered_at is None or answer_at is None or registered_at >= answer_at:
            return "补齐材料未在参考答案之前登记"
        if row.get("sha256") != _digest(item):
            return "补齐材料哈希与预登记不符"
    answers = spec.get("reference_answers")
    if not isinstance(answers, list) or any(
        row.get("tier") not in {"可接受", "不可接受", "集合外待盲审"} for row in answers
    ):
        return "参考答案不是三档假说"
    return None


def _aware(value):
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if stamp.tzinfo is None or stamp.tzinfo.utcoffset(stamp) is None:
        return "naive"
    return stamp


def _missing_target(spec):
    delete = spec.get("delete")
    if not isinstance(delete, dict) or "info_id" not in delete:
        return None
    target_id = delete.get("info_id")
    items = (spec.get("materials") or {}).get("completed") or []
    if any(isinstance(item, dict) and item.get("info_id") == target_id for item in items):
        return None
    return "删除目标不存在"


def _objects(spec):
    materials = spec.get("materials") or {}
    extractions = spec.get("extractions") or {}
    objects = []
    for material_name, extraction_name in _CELL_GROUPS:
        items = [item for item in materials.get(material_name) or [] if isinstance(item, dict)]
        allowed = {item.get("info_id") for item in items}
        raw = ((extractions.get(extraction_name) or {}).get(material_name)) or []
        kept = [row for row in raw if isinstance(row, dict) and row.get("info_id") in allowed]
        prepared = _apply_extraction(items, extraction_name, kept)
        payload = _candidate_payload(spec, prepared, direction=spec.get("direction"))
        objects.append(
            _named(
                spec,
                f"{material_name}/{extraction_name}",
                payload,
                len(objects),
                material=material_name,
                extraction=extraction_name,
                items=prepared,
                extraction_rows=kept,
            )
        )
    news = [item for item in materials.get("original") or [] if isinstance(item, dict)]
    placebo = spec.get("placebo") or {}
    baskets = [placebo["basket"]] if isinstance(placebo.get("basket"), str) and placebo.get("basket") else None
    objects.append(
        _named(
            spec,
            "安慰剂",
            _candidate_payload(
                spec, news, direction=spec.get("direction"), trade_date=placebo.get("trade_date"), baskets=baskets
            ),
            4,
        )
    )
    direction = spec.get("direction")
    flipped = "down" if direction == "up" else "up" if direction == "down" else None
    objects.append(_named(spec, "方向反转", _candidate_payload(spec, news, direction=flipped), 5))
    return objects


def _apply_extraction(items, extraction_name, rows):
    copied = [deepcopy(item) for item in items]
    if extraction_name != "manual":
        return copied
    by_id = {row.get("info_id"): row for row in rows if isinstance(row, dict)}
    for item in copied:
        row = by_id.get(item.get("info_id"))
        item["claims"] = deepcopy(row.get("claims") or []) if isinstance(row, dict) else []
    return copied


def _candidate_payload(spec, items, *, direction, trade_date=None, baskets=None):
    from inves_cog.llm.client import canonical_payload
    from inves_cog.perception.attribution.propose import candidate_payload

    anomaly = {}
    if spec.get("object_id") is not None:
        anomaly["anomaly_id"] = spec["object_id"]
    chosen_date = spec.get("trade_date") if trade_date is None else trade_date
    if chosen_date is not None:
        anomaly["trade_date"] = chosen_date
    if direction in {"up", "down"}:
        anomaly["direction"] = direction
    if baskets:
        anomaly["baskets"] = list(baskets)
    payload = candidate_payload(anomaly, items, [])
    return payload, sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def _named(spec, group, packed, slot, **extra):
    payload, digest = packed
    row = {
        "id": _opaque_id(spec, slot),
        "group": group,
        "payload": payload,
        "payload_sha256": digest,
    }
    row.update(extra)
    return row


def _opaque_id(spec, slot):
    return _digest({"object_id": spec.get("object_id"), "seed": spec.get("blind_seed", 0), "slot": slot})[:16]


def _delete(spec):
    target_id = (spec.get("delete") or {}).get("info_id")
    items = [item for item in (spec.get("materials") or {}).get("completed") or [] if isinstance(item, dict)]
    target = next(item for item in items if item.get("info_id") == target_id)
    root = target.get("source_root")
    removed = []
    kept = []
    for item in items:
        same = item.get("info_id") == target_id or (bool(root) and item.get("source_root") == root)
        if same:
            removed.append(item.get("info_id"))
            continue
        kept.append(deepcopy(item))
    removed_ids = set(removed)
    claims = [
        row for row in spec.get("claims") or [] if isinstance(row, dict) and row.get("info_id") not in removed_ids
    ]
    return {"removed": removed, "items": kept, "claims": claims, "sha256": _digest(removed)}


def _blind(spec, objects):
    rows = [{"id": obj["id"], "group": obj["group"]} for obj in objects]
    seed = int(_digest({"object_id": spec.get("object_id"), "seed": spec.get("blind_seed", 0)})[:16], 16)
    random.Random(seed).shuffle(rows)
    blinded = [{"order": index, "id": row["id"]} for index, row in enumerate(rows)]
    mapping = [{"order": index, "id": row["id"], "group": row["group"]} for index, row in enumerate(rows)]
    return blinded, mapping


def _plan(spec, objects):
    runs = _runs(spec)
    calls = [
        {"id": obj["id"], "run": run, "payload_sha256": obj["payload_sha256"]} for obj in objects for run in range(runs)
    ]
    return {"calls": calls, "runs": runs, "total_cap": 6 * runs, "executes": False}


def _runs(spec):
    value = spec.get("runs", 3)
    if type(value) is not int or value < 1:
        return 3
    return value


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
