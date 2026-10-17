"""Retrieval window and embedding isolation. Background is not a direct trigger."""

from datetime import timedelta

from inves_cog.perception.attribution.rules import m8_rules


def window_items(items, start, now, limit=40):
    chosen = []
    for item in items:
        if not _visible(item, now):
            continue
        role = _role(item["published_at"], start)
        if role is None:
            continue
        chosen.append({**item, "role": role})
    chosen.sort(key=lambda row: row.get("rank", 0), reverse=True)
    return chosen[:limit]


def _visible(item, now):
    first_seen = item.get("first_seen_at")
    if "first_seen_at" not in item or first_seen is None:
        return False
    return max(item["published_at"], first_seen) <= now


def _role(published, start):
    if published >= start - timedelta(hours=72):
        return "primary"
    if published >= start - timedelta(days=7):
        return "background"
    return None


def approved_vectors(rows, rules=None):
    rules = rules or m8_rules()
    model = rules["embedding_model"]
    dimensions = rules["embedding_dimensions"]
    return [row for row in rows if row.get("model") == model and row.get("dimensions") == dimensions]


def retrieval_mode(rows, rules=None):
    if approved_vectors(rows, rules):
        return "vector"
    return "rules"


def retrieval_gap(rows):
    """Missing or unapproved vectors stay on the rule path and are named."""
    if rows is None or retrieval_mode(rows) == "vector":
        return None
    return "向量检索降到规则检索"


def supplement_calls(requested, already_used, rules=None):
    budget = (rules or m8_rules())["search_daily_budget"]
    room = budget - already_used
    if room <= 0:
        return 0, "补证未执行"
    if requested > room:
        return room, "补证未执行"
    return requested, None


def supplement_plan(found_count, requested, already_used, *, now, rules=None):
    """Search only under five hits. This plans the call and does not make it."""
    if found_count >= 5:
        return {"calls": 0, "note": None, "first_seen_at": None}
    calls, note = supplement_calls(requested, already_used, rules)
    return {"calls": calls, "note": note, "first_seen_at": now if calls else None}


def stamp_supplement(item, now):
    """A search result is first seen now. Alignment still reads published_at."""
    return {**item, "first_seen_at": now, "supplement": True}


_SOURCE_WEIGHT = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}


def overlap_ratio(item_entities, query_entities):
    query = set(query_entities)
    if not query:
        return 0.0
    return min(len(query & set(item_entities)) / len(query), 1.0)


def relevance(item, query_entities):
    overlap = overlap_ratio(item.get("entities") or [], query_entities)
    similarity = item.get("similarity") or 0.0
    level = item.get("source_level")
    weight = _SOURCE_WEIGHT.get(int(level), 0.0) if level is not None else 0.0
    return 0.5 * overlap + 0.3 * similarity + 0.2 * weight


def rank_items(items, query_entities, limit=40):
    scored = [{**item, "relevance": relevance(item, query_entities)} for item in items]
    scored.sort(key=lambda row: row["relevance"], reverse=True)
    return scored[:limit]


def vector_query(anomaly):
    """Basket names, direction, and member names. Neighbors are not part of the query."""
    parts = [*(anomaly.get("baskets") or []), anomaly.get("direction"), *(anomaly.get("members") or [])]
    return " ".join(str(part) for part in parts if part)


def shortlist(items, entities, start, now, rules=None):
    """Visible window, then the union, then the top 40 by the retrieval score."""
    opened = window_items(items, start, now, limit=max(len(items), 1))
    return rank_items(retrieval_union(opened, entities, rules), entities)


def retrieval_union(items, entities, rules=None, *, vector_limit=50):
    """Rule hits and the top approved vectors, then one row per source root."""
    rules = rules or m8_rules()
    vector_ids = _top_vectors(items, rules, vector_limit)
    entity_set = set(entities)
    pooled = []
    for item in items:
        paths = _paths(item, entity_set, vector_ids)
        if paths:
            pooled.append({**item, "paths": paths})
    return _dedup_roots(pooled, entity_set)


def _top_vectors(items, rules, limit):
    ranked = [item for item in items if _approved_similarity(item, rules)]
    ranked.sort(key=lambda row: (-(row.get("similarity") or 0.0), row.get("info_id") or ""))
    return {row["info_id"] for row in ranked[:limit]}


def _approved_similarity(item, rules):
    if item.get("similarity") is None:
        return False
    model = item.get("model") == rules["embedding_model"]
    dimensions = item.get("dimensions") == rules["embedding_dimensions"]
    return model and dimensions


def _paths(item, entity_set, vector_ids):
    paths = []
    names = set(item.get("entities") or []) | set(item.get("tickers") or [])
    if names & entity_set:
        paths.append("rule")
    if item.get("info_id") in vector_ids:
        paths.append("vector")
    return paths


def _dedup_roots(items, entities):
    groups = []
    index = {}
    for item in items:
        root = item.get("source_root")
        key = ("root", root) if root else ("id", item.get("info_id"))
        if key not in index:
            index[key] = len(groups)
            groups.append([item])
        else:
            groups[index[key]].append(item)
    kept = []
    for group in groups:
        group.sort(key=lambda row: _root_key(row, entities))
        winner = dict(group[0])
        paths = []
        for row in group:
            for path in row.get("paths") or []:
                if path not in paths:
                    paths.append(path)
        winner["paths"] = paths
        kept.append(winner)
    return kept


def _root_key(row, entities):
    published = row.get("published_at")
    stamp = published.isoformat() if hasattr(published, "isoformat") else str(published or "")
    return (-relevance(row, entities), stamp, row.get("info_id") or "")


def retrieval_entities(members, baskets, edges, monitored):
    """Members, their basket peers, one hop of any status, then monitors tied to that set."""
    seeds = _unique(members)
    peers = _basket_peers(seeds, baskets)
    neighbors = _one_hop(set(seeds) | set(peers), edges)
    present = set(seeds) | set(peers) | set(neighbors)
    monitors = _monitors(present, monitored)
    return {
        "members": seeds,
        "basket_peers": peers,
        "neighbors": neighbors,
        "monitored": monitors,
        "entities": seeds + peers + neighbors + monitors,
    }


def _unique(names):
    found = []
    for name in names or []:
        if name and name not in found:
            found.append(name)
    return found


def _basket_peers(seeds, baskets):
    seed_set = set(seeds)
    peers = []
    for basket in baskets:
        names = _unique(basket.get("members") or [])
        if not seed_set & set(names):
            continue
        for name in names:
            if name not in seed_set and name not in peers:
                peers.append(name)
    return peers


def _one_hop(core, edges):
    neighbors = []
    for edge in edges:
        ends = (edge.get("from_entity"), edge.get("to_entity"))
        if any(end is None for end in ends):
            continue
        outside = [end for end in ends if end not in core]
        inside = [end for end in ends if end in core]
        if len(inside) == 1 and len(outside) == 1 and outside[0] not in neighbors:
            neighbors.append(outside[0])
    return neighbors


_EXPLORE_DAILY = 3


def explore_quota(items):
    """Three flagged low-heat, new-mechanism items enter research. They are not operating evidence."""
    if items is None:
        return None
    selected = []
    seen = set()
    for row in items:
        if len(selected) >= _EXPLORE_DAILY:
            break
        info_id = row.get("info_id")
        if not info_id or info_id in seen:
            continue
        seen.add(info_id)
        if row.get("low_heat") is not True or row.get("new_mechanism") is not True:
            continue
        selected.append(
            {
                "info_id": info_id,
                "enters_research": True,
                "operating_evidence": False,
                "fundamental_standing": None,
            }
        )
    return {
        "selected": selected,
        "limit": _EXPLORE_DAILY,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


_DISCARD_WEEKLY = 20


def discard_review(items):
    """At most 20 discarded items go to review, in the order given. This function does not shuffle."""
    if items is None:
        return None
    selected = []
    seen = set()
    for row in items:
        if len(selected) >= _DISCARD_WEEKLY:
            break
        info_id = row.get("info_id")
        if not info_id or info_id in seen:
            continue
        seen.add(info_id)
        if row.get("discarded") is not True:
            continue
        later = row.get("later_important")
        selected.append(
            {
                "info_id": info_id,
                "human_review": True,
                "counts_as_miss": later if later in {True, False} else None,
                "operating_evidence": False,
                "fundamental_standing": None,
            }
        )
    return {
        "selected": selected,
        "limit": _DISCARD_WEEKLY,
        "shuffled": False,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


_FULL_TEXT_DAYS = 90


def text_retention(reading):
    """Full text stays for 90 days from first seen. Later, only the summary and vector remain."""
    if reading is None:
        return None
    item = reading.get("item")
    as_of = reading.get("as_of")
    if not isinstance(item, dict) or as_of is None:
        return None
    seen = item.get("first_seen_at")
    if seen is None:
        return None
    try:
        age = as_of - seen
    except TypeError:
        return None
    if not isinstance(age, timedelta) or age < timedelta(0):
        return None
    within = age <= timedelta(days=_FULL_TEXT_DAYS)
    body = item.get("body")
    summary = item.get("summary")
    return {
        "full_text": body if within and _text(body) else None,
        "full_text_retained": within and _text(body),
        "summary": summary if _text(summary) else None,
        "summary_retained": _text(summary),
        "vector_retained": _vector(item),
        "searchable": True,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


def _text(value):
    return isinstance(value, str) and value != ""


def _vector(item):
    if item.get("has_vector") is True:
        return True
    vector = item.get("vector")
    return isinstance(vector, (list, tuple)) and len(vector) > 0


def _monitors(present, monitored):
    found = []
    for row in monitored:
        entity_id = row.get("entity_id")
        if not entity_id or entity_id in present or entity_id in found:
            continue
        if set(row.get("tickers") or []) & present:
            found.append(entity_id)
    return found
