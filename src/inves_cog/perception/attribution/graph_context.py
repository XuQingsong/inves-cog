"""Project supplied relationship versions; this does not reconstruct graph history."""

from datetime import datetime, timezone
from json import dumps

_TEXT = ("relation_id", "from_entity", "to_entity", "mechanism", "connection_type", "direction", "status")
_TIMES = (
    "first_discovered_at",
    "last_evidence_at",
    "reviewed_at",
    "updated_at",
    "last_updated_at",
    "created_at",
    "version_at",
    "version_recorded_at",
    "recorded_at",
    "valid_from",
)


def _stamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _source_ids(edge):
    sources = edge.get("source_info_ids")
    if not isinstance(sources, list):
        return []
    return sorted({value for value in sources if isinstance(value, str) and value})


def _supplied_signature(edge):
    signature = {key: edge.get(key) for key in _TEXT + _TIMES + ("revision",)}
    for key in _TIMES:
        stamp = _stamp(edge.get(key))
        if stamp is not None:
            signature[key] = stamp.isoformat()
    signature["source_info_ids"] = _source_ids(edge)
    for key in ("opposing_evidence", "invalidation_condition", "exit_reason", "falsified", "contradicted"):
        signature[key] = bool(edge.get(key))
    return dumps(signature, default=str, sort_keys=True)


def _core(members, baskets):
    core = set(members)
    for basket in baskets:
        peers = {name for name in basket.get("members") or [] if isinstance(name, str) and name}
        # Basket peers belong to the original anomaly scope, not to later graph hops.
        if set(members) & peers:
            core.update(peers)
    return core


def project_graph(members, baskets, edges, as_of):
    """Keep incident, visible current versions and only approved relationship fields."""
    core = _core(members, baskets)
    now = _stamp(as_of)
    kept, gaps = [], set()
    incident = 0
    supplied_versions = {}
    for edge in edges:
        if not isinstance(edge, dict):
            gaps.add("关系行结构未知")
            continue
        ends = (edge.get("from_entity"), edge.get("to_entity"))
        if any(not isinstance(end, str) or not end for end in ends):
            gaps.add("关系端点未知")
            continue
        if not core.intersection(ends):
            continue
        incident += 1
        identifier = edge.get("relation_id")
        if isinstance(identifier, str) and identifier:
            supplied_versions.setdefault(identifier, set()).add(_supplied_signature(edge))
        first = _stamp(edge.get("first_discovered_at"))
        if now is None or first is None:
            gaps.add("关系版本时点缺失或非法")
            continue
        if first > now:
            gaps.add("关系版本晚于分析时点")
            continue
        times = {"first_discovered_at": first.isoformat()}
        valid = True
        for key in _TIMES[1:]:
            if edge.get(key) is None:
                continue
            value = _stamp(edge[key])
            if value is None or value > now:
                gaps.add("关系版本时点缺失或非法" if value is None else "关系版本晚于分析时点")
                valid = False
                break
            times[key] = value.isoformat()
        if not valid:
            continue
        row = {key: edge[key] for key in _TEXT if isinstance(edge.get(key), str) and edge[key]}
        row.update(times)
        revision = edge.get("revision")
        if isinstance(revision, (str, int)) and not isinstance(revision, bool):
            row["revision"] = revision
        row["source_info_ids"] = _source_ids(edge)
        row["source_status"] = "来源ID已提供" if row["source_info_ids"] else "未知"
        if not row["source_info_ids"]:
            gaps.add("关系来源未知")
        if "status" not in row:
            gaps.add("关系状态未知")
        if "relation_id" not in row:
            gaps.add("关系ID未知")
        for key in ("falsified", "contradicted"):
            if type(edge.get(key)) is bool:
                row[key] = edge[key]
        for key in ("opposing_evidence", "invalidation_condition", "exit_reason"):
            if edge.get(key):
                row[key + "_present"] = True
        kept.append(row)
    versions = {}
    for row in kept:
        if row.get("relation_id"):
            versions.setdefault(row["relation_id"], set()).add(dumps(row, ensure_ascii=False, sort_keys=True))
    conflicts = {key for key, values in versions.items() if len(values) > 1}
    conflicts.update(key for key, values in supplied_versions.items() if len(values) > 1)
    if conflicts:
        gaps.add("同ID关系版本冲突")
    kept = [row for row in kept if row.get("relation_id") not in conflicts]
    kept = list({dumps(row, ensure_ascii=False, sort_keys=True): row for row in kept}.values())
    kept.sort(key=lambda row: dumps(row, ensure_ascii=False, sort_keys=True))
    if not kept:
        gaps.add("无可用的一跳关系版本")
    return {
        "neighbors": kept,
        "metadata": {
            "version": 1,
            "as_of": now.isoformat() if now is not None else None,
            "incident_rows": incident,
            "eligible_rows": len(kept),
            "gaps": sorted(gaps),
            "historical_version_reconstructed": False,
        },
    }
