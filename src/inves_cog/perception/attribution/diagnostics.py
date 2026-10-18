"""Score display marks. They do not change the six-part total."""

_DISPLAY = "时间与关联特征分"


def score_marks(candidate, items, components):
    """Name the time source and the co-mention rows that no link anchor cites."""
    anchors = _anchor_ids(candidate.get("links"))
    cited = [item for item in items if item.get("info_id") in set(candidate.get("info_ids") or [])]
    earliest = _earliest_id(cited)
    counted = components.get("narrative") is not None
    cooccurrence = _cooccurrence_count(cited, candidate, anchors) if counted else 0
    return {
        "display_name": _DISPLAY,
        "not_credibility": True,
        "时间分来源未被逐环引用": components.get("time") is not None and earliest not in anchors,
        "仅共现条数": cooccurrence,
    }


def _anchor_ids(links):
    found = set()
    for link in links or []:
        if not isinstance(link, dict):
            continue
        for anchor in link.get("anchors") or []:
            if isinstance(anchor, dict) and isinstance(anchor.get("info_id"), str):
                found.add(anchor["info_id"])
    return found


def _earliest_id(items):
    chosen = None
    stamp = None
    for item in items:
        published = item.get("published_at")
        if published is None:
            continue
        if stamp is None or published < stamp:
            chosen = item.get("info_id")
            stamp = published
    return chosen


def _cooccurrence_count(items, candidate, anchors):
    event = {
        row.get("entity_id") for row in candidate.get("chain") or [] if isinstance(row, dict) and row.get("entity_id")
    }
    names = {
        row.get("ticker") for row in candidate.get("affected") or [] if isinstance(row, dict) and row.get("ticker")
    }
    count = 0
    for item in items:
        if item.get("info_id") in anchors or not _comention(item, event, names):
            continue
        count += 1
    return count


def _comention(item, event, names):
    tags = [item.get(key) for key in ("entities", "tickers") if item.get(key) is not None]
    known = bool(tags) and all(
        isinstance(value, list) and all(isinstance(name, str) for name in value) for value in tags
    )
    root = item.get("source_root")
    root = root if isinstance(root, str) and root.strip() else None
    if not known or not root or not event or not names:
        return False
    mentioned = {name for value in tags for name in value}
    return bool(mentioned & event and mentioned & names)
