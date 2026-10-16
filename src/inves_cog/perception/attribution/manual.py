"""Date-level checks for public pages read by hand on a later day.

A matching headline does not close a case. A printed date without a timezone
is not a minute, and a later read is not a collection that existed then.
"""

from datetime import date, timedelta


def remaining_gap(lead):
    kind = lead["kind"]
    if kind == "r1_release":
        if lead.get("app_store_snapshot") is True and lead.get("published_precision") == "minute":
            return None
        return "只有发布日期，没有榜单快照"
    if kind == "openai_arr":
        if lead.get("ft_original_frozen") is not True:
            return "FT 原文未冻结"
        if not lead.get("timezone"):
            return "发布时间没有时区"
        return None
    if kind == "muse_rank":
        day = date.fromisoformat(lead["published_on"])
        if date(2026, 9, 19) <= day <= date(2026, 9, 21) and lead.get("before_open") is True:
            return None
        return "日期不在 09-19 至 09-21 开盘前"
    raise ValueError("未知补证种类")


def strictly_before_primary(latest_on, anomaly_on):
    """True when every civil instant on that printed date is before the 72-hour window.

    The open is 13:30 UTC, so the window starts on the anomaly date minus three
    days. A printed date at least four calendar days earlier stays outside that
    window in any UTC offset from -12 to +14.
    """
    latest = date.fromisoformat(latest_on)
    return latest <= anomaly_on - timedelta(days=4)


def calendar_after(published_on, updated_on, anomaly_on):
    latest = max(date.fromisoformat(published_on), date.fromisoformat(updated_on))
    return latest > anomaly_on


def supplement_replay(read_on, published_on, anomaly_on):
    read = date.fromisoformat(read_on)
    published = date.fromisoformat(published_on)
    anomaly = anomaly_on if isinstance(anomaly_on, date) else date.fromisoformat(anomaly_on)
    if not published <= anomaly < read:
        raise ValueError("人工补证不能标成当时可见")
    return {"mode": "后补录历史复盘", "collected_then": False, "vectors_then": False}
