"""Date-level checks for public pages read by hand on a later day.

A matching headline does not close a case. A printed date without a timezone
is not a minute, and a later read is not a collection that existed then.
"""

from datetime import date, datetime, timedelta


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


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
    read = _day(read_on)
    published = _day(published_on)
    anomaly = _day(anomaly_on)
    if not published <= anomaly < read:
        raise ValueError("人工补证不能标成当时可见")
    return {"mode": "后补录历史复盘", "collected_then": False, "vectors_then": False}


def attach_backfill(anomaly, lead, read_on):
    """Label a later page against an anomaly. A gap or a late read cannot pass the clause."""
    anomaly_on = _day(anomaly["trade_date"])
    replay = supplement_replay(read_on, lead["published_on"], anomaly_on)
    gap = remaining_gap(lead)
    aligned = anomaly_on.isoformat() in lead["case_id"]
    return {
        "anomaly_id": anomaly["anomaly_id"],
        "lead_id": lead["id"],
        "mode": replay["mode"],
        "collected_then": replay["collected_then"],
        "vectors_then": replay["vectors_then"],
        "gap": gap,
        "aligned": aligned,
        "case_clause_met": gap is None and aligned and replay["collected_then"] and replay["vectors_then"],
    }
