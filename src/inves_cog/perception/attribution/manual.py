"""Date-level checks for public pages read by hand on a later day.

A matching headline does not close a case. A printed date without a timezone
is not a minute, and a later read is not a collection that existed then.
"""

from datetime import date, datetime, timedelta, timezone

from inves_cog.perception.attribution.replay import then_visible


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


def open_relation(published_on, anomaly_on):
    """Compare a date-only civil day with the US open at 13:30 UTC.

    Unknown clock and timezone use the same offset span as the primary-window
    check, UTC-12 through UTC+14. A whole interval before the open is early.
    Overlap stays unknown. Do not invent a minute.
    """
    published = _day(published_on)
    anomaly = _day(anomaly_on)
    open_at = datetime(anomaly.year, anomaly.month, anomaly.day, 13, 30, tzinfo=timezone.utc)
    start = datetime(published.year, published.month, published.day, tzinfo=timezone.utc)
    earliest = start - timedelta(hours=14)
    latest = start + timedelta(days=1, hours=12)
    if latest < open_at:
        return "早于开盘"
    if earliest > open_at:
        return "晚于开盘"
    return "未知"


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


def production_visible(items, as_of, mode="严格当时可见"):
    """Production visibility ignores the historical-case switch."""
    if mode != "严格当时可见":
        raise ValueError("生产路径不接受案例模式")
    return then_visible(items, as_of)


def historical_case(lead, anomaly_on, read_on):
    """A later real page may enter the historical case. It was not collected then."""
    anomaly = _day(anomaly_on)
    published = _day(lead["published_on"])
    result = {
        "evidence_mode": "后补录历史案例",
        "collected_then": False,
        "vectors_then": False,
        "closes_case": False,
        "closes_ac_m8_06": False,
        "usable": False,
        "role": None,
        "uncertainty": "晚于案例截止，不能进入候选",
    }
    if published > anomaly:
        return result
    replay = supplement_replay(read_on, lead["published_on"], anomaly)
    if replay["collected_then"]:
        raise ValueError("人工补证不能标成当时可见")
    kind = lead["kind"]
    if kind == "r1_release":
        role, uncertainty = "发布", "只有日期，没有分钟，没有榜单快照"
        usable = lead.get("published_precision") == "date"
    elif kind == "openai_arr":
        role = "背景"
        uncertainty = "FT 原文未冻结；页面没有时区；更新日仍早于异常，不是二次命中"
        usable = lead.get("source_root") == "reuters" and strictly_before_primary(lead["updated_on"], anomaly)
    elif kind == "muse_rank":
        role = "背景"
        if strictly_before_primary(lead["published_on"], anomaly):
            uncertainty = "早于 72 小时主窗口"
        else:
            uncertainty = "只有日期，不能证明落入 72 小时主窗口，也不能改成 09-19"
        usable = True
    elif kind in {"coreweave_debt", "barclays_downgrade", "cpi_hot", "toshiba_supply", "tdk_second_hit"}:
        role, uncertainty = "案例材料", "四级转载；保留原始发布时间与后见时间"
        usable = True
    else:
        raise ValueError("未知补证种类")
    result.update(usable=usable, role=role, uncertainty=uncertainty, replay=replay["mode"])
    return result
