"""Label a historical replay by what was visible at the time.

An item whose publish time is on or before the replay instant, but whose
first-seen time is later, was recorded afterwards. That replay is
后补录历史复盘: the system had not collected the item, and its vector
cannot be claimed to have existed. 当时可见 requires every item to have
been seen already. Vectors count only when each item has an embedding
timestamp at or before that instant.
"""


def _seen(item):
    return item.get("first_seen_at") or item["published_at"]


def then_visible(items, as_of):
    return [item for item in items if max(item["published_at"], _seen(item)) <= as_of]


def replay_mode(items, as_of):
    late = [item["info_id"] for item in items if item["published_at"] <= as_of and _seen(item) > as_of]
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
