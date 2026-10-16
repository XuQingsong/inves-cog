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
    first_seen = item.get("first_seen_at") or item["published_at"]
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


def supplement_calls(requested, already_used, rules=None):
    budget = (rules or m8_rules())["search_daily_budget"]
    room = budget - already_used
    if room <= 0:
        return 0, "补证未执行"
    if requested > room:
        return room, "补证未执行"
    return requested, None


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


def _monitors(present, monitored):
    found = []
    for row in monitored:
        entity_id = row.get("entity_id")
        if not entity_id or entity_id in present or entity_id in found:
            continue
        if set(row.get("tickers") or []) & present:
            found.append(entity_id)
    return found
