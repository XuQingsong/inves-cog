"""Label a historical replay by what was visible at the time.

An item whose publish time is on or before the replay instant, but whose
first-seen time is later, was recorded afterwards. That replay is
后补录历史复盘: the system had not collected the item, and its vector
cannot be claimed to have existed. 当时可见 requires every item to have
been seen already. A missing first-seen time stays unknown and is not
filled from the publish time. Vectors count only when each item has an
embedding timestamp at or before that instant.
"""


def _seen(item):
    if "first_seen_at" not in item or item.get("first_seen_at") is None:
        return None
    return item["first_seen_at"]


def then_visible(items, as_of):
    visible = []
    for item in items:
        seen = _seen(item)
        if seen is None:
            continue
        if max(item["published_at"], seen) <= as_of:
            visible.append(item)
    return visible


def replay_mode(items, as_of):
    unknown = [item["info_id"] for item in items if _seen(item) is None]
    late = [
        item["info_id"]
        for item in items
        if _seen(item) is not None and item["published_at"] <= as_of and _seen(item) > as_of
    ]
    if unknown:
        return {
            "mode": "未知",
            "late_ids": late,
            "unknown_ids": unknown,
            "collected_then": False,
            "vectors_then": False,
        }
    if late:
        return {
            "mode": "后补录历史复盘",
            "late_ids": late,
            "collected_then": False,
            "vectors_then": False,
        }
    vectors = all(
        item.get("embedding_created_at") is not None and item["embedding_created_at"] <= as_of for item in items
    )
    return {"mode": "当时可见", "late_ids": [], "collected_then": True, "vectors_then": vectors}
