"""Project supplied relationship versions; this does not reconstruct graph history."""

import re
import unicodedata
from datetime import datetime, timezone
from json import dumps, loads

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
        if edge.get("status_basis") == "SEC原文引文核对":
            row["status_basis"] = edge["status_basis"]
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


_OBSERVED = {"观察到", "有支持", "已确立"}
_CITED = {"业务关系", "经营传导"}
_BASIS = "SEC原文引文核对"
_TICKER = "ticker:"
_RELATIONS = """
SELECT relation_id, from_entity, to_entity, connection_type, mechanism, direction, status,
       first_discovered_at, reviewed_at, last_evidence_at, source_info_ids, evidence
FROM graph.relations
WHERE status <> '驳回'
  AND (from_entity = ANY(%s) OR to_entity = ANY(%s))
  AND first_discovered_at <= %s
  AND (reviewed_at IS NULL OR reviewed_at <= %s)
ORDER BY relation_id
"""
_TEXTS = """
SELECT accession, text
FROM graph.source_texts
WHERE accession = ANY(%s) AND fetched_at <= %s
"""


def attach_graph(connection, anomalies, as_of):
    """Read visible graph rows onto each anomaly. An empty read leaves a caller's edges alone."""
    for anomaly in anomalies or []:
        if not isinstance(anomaly, dict):
            continue
        edges = read_graph_edges(connection, anomaly.get("members") or [], as_of)
        if edges:
            anomaly["edges"] = edges
    return anomalies


def read_graph_edges(connection, members, as_of):
    """One cutoff for live and replay. Citation checks are derived and are not written back."""
    names = []
    for member in members or []:
        name = member.get("ticker") if isinstance(member, dict) else member
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    if not names or as_of is None:
        return []
    keys = []
    for name in names:
        keys.append(name)
        prefixed = _TICKER + name
        if prefixed not in keys:
            keys.append(prefixed)
    found = [_mapping(row) for row in connection.execute(_RELATIONS, (keys, keys, as_of, as_of)).fetchall()]
    texts = _source_texts(connection, found, as_of)
    edges = []
    for row in found:
        edge = _prepared_edge(row, texts)
        if edge is not None:
            edges.append(edge)
    return edges


def _source_texts(connection, rows, as_of):
    accessions = []
    for row in rows:
        citation = _citation(row.get("evidence"))
        accession = citation.get("accession") if isinstance(citation, dict) else None
        if isinstance(accession, str) and accession and accession not in accessions:
            accessions.append(accession)
    grouped = {accession: [] for accession in accessions}
    if not accessions:
        return grouped
    for row in connection.execute(_TEXTS, (accessions, as_of)).fetchall():
        mapped = _mapping(row)
        accession = mapped.get("accession")
        text = mapped.get("text")
        if accession in grouped and isinstance(text, str):
            grouped[accession].append(text)
    return grouped


def _prepared_edge(row, texts):
    edge = {
        "relation_id": row.get("relation_id"),
        "from_entity": _ticker_name(row.get("from_entity")),
        "to_entity": _ticker_name(row.get("to_entity")),
        "connection_type": row.get("connection_type"),
        "mechanism": row.get("mechanism"),
        "direction": row.get("direction"),
        "status": row.get("status"),
        "first_discovered_at": row.get("first_discovered_at"),
        "reviewed_at": row.get("reviewed_at"),
        "last_evidence_at": row.get("last_evidence_at"),
        "source_info_ids": list(row.get("source_info_ids") or []),
    }
    if edge["status"] in _OBSERVED:
        return edge
    if edge["connection_type"] in _CITED and _quote_matches(row.get("evidence"), texts):
        edge["status"] = "观察到"
        edge["status_basis"] = _BASIS
    return edge


def _quote_matches(evidence, texts):
    citation = _citation(evidence)
    if not isinstance(citation, dict):
        return False
    quote = citation.get("quote")
    accession = citation.get("accession")
    if not isinstance(quote, str) or not isinstance(accession, str) or accession not in texts:
        return False
    wanted = _normalize(quote)
    if not wanted:
        return False
    return any(wanted in _normalize(text) for text in texts[accession])


def _citation(evidence):
    if isinstance(evidence, str):
        try:
            evidence = loads(evidence)
        except ValueError:
            return None
    if hasattr(evidence, "obj"):
        evidence = evidence.obj
    if not isinstance(evidence, dict):
        return None
    return evidence.get("citation")


def _ticker_name(entity):
    if isinstance(entity, str) and entity.startswith(_TICKER):
        rest = entity[len(_TICKER) :]
        if rest:
            return rest
    return entity


def _normalize(text):
    folded = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", folded).strip()


def _mapping(row):
    if isinstance(row, dict):
        return row
    return dict(row)
