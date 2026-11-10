"""Live anomalies: let the model pick a cause from ingested news.

Runs right after the rule linker. Only rows still without a rule link are
considered; every cited id must be one of the candidates we sent."""

from datetime import datetime, timedelta
from pathlib import Path

from inves_cog.ingest.market import NY
from inves_cog.params import load_params
from inves_cog.perception.attribution.retrieve import rank_items
from inves_cog.perception.live.link import LINK_GRACE, _basket_member_tickers, _window_start

TASK = "live_cause"
KINDS = ("news", "sec_8k", "form4", "macro")
CONFIDENCE = ("high", "medium", "low")
TIMING = ("news_before_move", "move_before_news", "unclear")
_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}
QUESTION = (
    "下面是一次股价异常和这段时间入库的候选新闻。请判断哪几条新闻最能解释这次异常。"
    "只能引用候选新闻里给出的 id；如果没有任何一条能解释，cause_info_ids 返回空数组。"
    "reason_zh 用一句中文说明原因（不超过 60 字，不要写 id）。"
    "reason_zh 必须全部用中文，人名、公司名可用常用中文译名，股票代码除外。"
    "如实转述承认、指控、传闻、确认的层级，不得升级或降级。"
    "confidence：新闻直接说明了涨跌原因为 high，较可能为 medium，只是猜测为 low。"
    "timing：新闻入库早于异常为 news_before_move，晚于异常为 move_before_news，否则 unclear。"
)


def params(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[4]
    return dict(load_params(root / "config/params/p-2026.10").values["live_cause"])


def _z(row):
    z = row.get("peak_z")
    if z is None:
        z = row.get("last_z")
    return z


def is_major(row, rules):
    z = _z(row)
    return z is not None and abs(z) >= rules["major_z"]


def is_focus(connection, row, core, held):
    """Market rows, held names and core companies (any member for baskets)."""
    if row["scope"] == "market":
        return True
    names = {row["subject"]} if row["scope"] == "stock" else set(_basket_member_tickers(connection, row["subject"]))
    return bool(names & (set(core) | set(held)))


def calls_used(connection, day):
    """Model calls spent today on live causes (every try counts)."""
    row = connection.execute(
        "SELECT coalesce(sum(llm_attempts), 0) AS n FROM perception.live_anomalies WHERE trade_date=%s",
        (day,),
    ).fetchone()
    return int((row or {}).get("n") or 0)


def query_entities(connection, row, core):
    if row["scope"] == "stock":
        return [row["subject"]], None
    if row["scope"] == "basket":
        members = [t for t in _basket_member_tickers(connection, row["subject"]) if t != "__none__"]
        return members, members
    return sorted(set(core) | {"SPY", "QQQ"}), None


def window(day, now):
    """Previous session 16:00 ET -> now, bounded by the trade day's 20:00 ET,
    so news landing after the move can still be found (move_before_news)."""
    day_end = datetime(day.year, day.month, day.day, 20, 0, tzinfo=NY)
    return _window_start(day), min(now, day_end)


def fetch_pool(connection, row, day, now, core, rules):
    """News-type items first seen inside the window that name the query entities."""
    start, end = window(day, now)
    entities, members = query_entities(connection, row, core)
    oldest = start - timedelta(hours=rules["max_age_hours"])
    form4_oldest = start - timedelta(hours=rules["form4_max_age_hours"])
    macro = " OR kind='macro'" if row["scope"] == "market" else ""
    rows = connection.execute(
        f"""SELECT info_id, kind, source, source_level, published_at, first_seen_at, headline,
                   left(coalesce(summary, ''), %s) AS summary, tickers, entities
            FROM ingest.info_items
            WHERE first_seen_at >= %s AND first_seen_at <= %s
              AND kind = ANY(%s)
              AND (tickers && %s{macro})
              AND (published_at IS NULL OR published_at >= %s)
              AND (kind <> 'form4' OR published_at >= %s)
            ORDER BY abs(extract(epoch FROM first_seen_at - %s::timestamptz)), info_id LIMIT %s""",
        (
            rules["summary_chars"],
            start,
            end,
            list(KINDS),
            entities or ["__none__"],
            oldest,
            form4_oldest,
            row["first_seen_at"],  # keep the items nearest the move on both sides
            rules["pool_limit"],
        ),
    ).fetchall()
    return [dict(r) for r in rows], entities, members, (start, end)


def _dedupe(items):
    """Same headline seen twice keeps the earliest copy."""
    seen = {}
    for item in sorted(items, key=lambda r: (r["first_seen_at"], r["info_id"])):
        key = " ".join((item.get("headline") or "").lower().split())
        seen.setdefault(key, item)
    return list(seen.values())


def candidates(connection, row, day, now, core, rules):
    pool, entities, members, span = fetch_pool(connection, row, day, now, core, rules)
    pool = _dedupe(pool)
    for item in pool:
        item.setdefault("entities", [])
        item["entities"] = list(item.get("entities") or [])
        item["tickers"] = list(item.get("tickers") or [])
        if item.get("published_at") is None:
            item["published_at"] = item["first_seen_at"]
    # Later commentary always scores as fresh; rank the two sides separately so
    # the story that preceded the move keeps its slots.
    cutoff = row["first_seen_at"] + LINK_GRACE
    before = [i for i in pool if i["first_seen_at"] <= cutoff]
    after = [i for i in pool if i["first_seen_at"] > cutoff]
    top_k, pre_slots = rules["top_k"], rules["pre_slots"]
    kwargs = {"start": row["first_seen_at"], "members": members}
    before = rank_items(before, entities, limit=top_k, **kwargs)
    after = rank_items(after, entities, limit=top_k, **kwargs)
    take_before = max(min(len(before), pre_slots), top_k - len(after))
    chosen = before[:take_before] + after[: top_k - min(take_before, len(before))]
    chosen.sort(key=lambda i: (i["first_seen_at"], i["info_id"]))
    return chosen, span


def _et(value):
    return value.astimezone(NY).strftime("%m-%d %H:%M") if hasattr(value, "astimezone") else ""


def _pct(value):
    return f"{value * 100:+.1f}%" if isinstance(value, (int, float)) else None


def payload(row, ranked):
    session = {"pre": "盘前", "regular": "盘中", "post": "盘后"}.get(row.get("session"), row.get("session"))
    anomaly = {
        "对象": row["subject"],
        "层级": {"stock": "个股", "basket": "板块", "market": "市场"}.get(row["scope"], row["scope"]),
        "方向": "上涨" if row["direction"] == "up" else "下跌",
        "时段": session,
        "首次出现（美东）": _et(row["first_seen_at"]),
        "首次涨跌（较昨收）": _pct(row.get("first_ret")),
        "峰值涨跌（较昨收）": _pct(row.get("peak_ret")),
    }
    if row["scope"] == "basket" and isinstance(row.get("members"), dict):
        anomaly["成员涨跌"] = {k: _pct(v) for k, v in list(row["members"].items())[:12]}
    news = [
        {
            "id": n,
            "发布（美东）": _et(item.get("published_at")),
            "入库（美东）": _et(item.get("first_seen_at")),
            "来源": item.get("source") or "",
            "标题": item.get("headline") or "",
            "摘要": item.get("summary") or "",
        }
        for n, item in enumerate(ranked, 1)
    ]
    return {"异常": anomaly, "候选新闻": news, "问法": QUESTION}


def validate(reply, ranked, span):
    """-> dict(confidence, reason, info_ids, timing, items) or None (discard)."""
    if not isinstance(reply, dict):
        return None
    raw = reply.get("cause_info_ids")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return None
    start, end = span
    chosen = []
    for value in raw:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        if not 1 <= number <= len(ranked):
            return None
        item = ranked[number - 1]
        if not start <= item["first_seen_at"] <= end:
            return None
        if item not in chosen:
            chosen.append(item)
    confidence = reply.get("confidence")
    confidence = confidence if confidence in CONFIDENCE else "low"
    timing = reply.get("timing") if reply.get("timing") in TIMING else "unclear"
    reason = reply.get("reason_zh")
    reason = " ".join(reason.split())[:120] if isinstance(reason, str) else ""
    if not chosen or not reason:
        return {"confidence": None, "reason": None, "info_ids": [], "timing": None, "items": []}
    return {
        "confidence": confidence,
        "reason": reason,
        "info_ids": [i["info_id"] for i in chosen],
        "timing": timing,
        "items": chosen,
    }


def _key(row):
    return (row["trade_date"], row["session"], row["scope"], row["subject"], row["direction"])


_KEY_SQL = "trade_date=%s AND session=%s AND scope=%s AND subject=%s AND direction=%s"


def _mark(connection, row, now, major, counted):
    connection.execute(
        f"""UPDATE perception.live_anomalies
            SET llm_attempts=llm_attempts + %s, llm_last_at=%s, llm_last_major=%s, updated_at=now()
            WHERE {_KEY_SQL}""",
        (1 if counted else 0, now, major, *_key(row)),
    )


def _write(connection, row, verdict):
    first = min(i["first_seen_at"] for i in verdict["items"])
    lag = (row["first_seen_at"] - first).total_seconds() / 60.0
    connection.execute(
        f"""UPDATE perception.live_anomalies
            SET cause_source='llm', cause_reason=%s, cause_confidence=%s, cause_timing=%s,
                cause_info_ids=%s, cause_lag_minutes=%s, updated_at=now()
            WHERE {_KEY_SQL} AND cause_event_id IS NULL""",
        (verdict["reason"], verdict["confidence"], verdict["timing"], verdict["info_ids"], lag, *_key(row)),
    )


def due(row, now, rules, *, major, fresh_news):
    """First appearance, upgrade to major, or news newer than the last try."""
    if row.get("cause_confidence") == "high":
        return False
    if (row.get("llm_attempts") or 0) >= rules["max_attempts"]:
        return False
    last = row.get("llm_last_at")
    if last is None:
        return True
    if now - last < timedelta(minutes=rules["min_interval_minutes"]):
        return False
    return (major and not row.get("llm_last_major")) or fresh_news


def _copy_sibling(connection, row, sibling):
    connection.execute(
        f"""UPDATE perception.live_anomalies
            SET cause_source='llm', cause_reason=%s, cause_confidence=%s, cause_timing=%s,
                cause_info_ids=%s, cause_lag_minutes=%s, updated_at=now()
            WHERE {_KEY_SQL} AND cause_event_id IS NULL""",
        (
            sibling["cause_reason"],
            sibling["cause_confidence"],
            sibling["cause_timing"],
            sibling["cause_info_ids"],
            row.get("_sibling_lag"),
            *_key(row),
        ),
    )


def llm_causes(connection, day, now, core, held, client, rules=None):
    """One pass. Returns counts incl. today's call usage against the cap."""
    from inves_cog.llm.usage import usage_context

    rules = rules or params()
    rows = [
        dict(r)
        for r in connection.execute(
            """SELECT * FROM perception.live_anomalies
               WHERE trade_date=%s AND cause_event_id IS NULL
               ORDER BY first_seen_at""",
            (day,),
        ).fetchall()
    ]
    used = calls_used(connection, day)
    stats = {"called": 0, "written": 0, "rejected": 0, "copied": 0, "skipped_cap": 0, "used": used}
    cap = rules["daily_cap"]
    focus_from = cap * rules["focus_share"]
    for row in rows:
        row["_major"] = is_major(row, rules)
        row["_focus"] = is_focus(connection, row, core, held)
    rows.sort(key=lambda r: (not r["_major"], not r["_focus"], -abs(_z(r) or r.get("peak_ret") or 0)))
    confirmed = {
        (r["scope"], r["subject"], r["direction"]): r
        for r in rows
        if r.get("cause_source") == "llm" and r.get("cause_confidence") == "high"
    }
    for row in rows:
        if row.get("cause_confidence") == "high":
            continue
        sibling = confirmed.get((row["scope"], row["subject"], row["direction"]))
        if sibling is not None:
            first = connection.execute(
                "SELECT min(first_seen_at) AS at FROM ingest.info_items WHERE info_id = ANY(%s)",
                (sibling["cause_info_ids"],),
            ).fetchone()
            if first and first["at"]:
                row["_sibling_lag"] = (row["first_seen_at"] - first["at"]).total_seconds() / 60.0
            _copy_sibling(connection, row, sibling)
            stats["copied"] += 1
            continue
        if stats["called"] >= rules["per_pass_calls"]:
            break
        last = row.get("llm_last_at")
        if last is not None and now - last < timedelta(minutes=rules["min_interval_minutes"]):
            continue
        if (row.get("llm_attempts") or 0) >= rules["max_attempts"]:
            continue
        ranked, span = candidates(connection, row, day, now, core, rules)
        fresh = last is not None and any(i["first_seen_at"] > last for i in ranked)
        if not due(row, now, rules, major=row["_major"], fresh_news=fresh):
            continue
        if used >= cap or (used >= focus_from and not (row["_major"] or row["_focus"])):
            stats["skipped_cap"] += 1
            continue
        if not ranked:
            _mark(connection, row, now, row["_major"], counted=False)
            continue
        used += 1
        stats["called"] += 1
        try:
            with usage_context(purpose=TASK, info_ids=[i["info_id"] for i in ranked]):
                reply = client.call(TASK, payload(row, ranked))
        except Exception as exc:  # model down -> count the try, keep 原因未明
            print(f"live_cause failed {row['subject']}: {type(exc).__name__}", flush=True)
            _mark(connection, row, now, row["_major"], counted=True)
            continue
        _mark(connection, row, now, row["_major"], counted=True)
        verdict = validate(reply, ranked, span)
        if verdict is None:
            stats["rejected"] += 1
            continue
        if not verdict["info_ids"]:
            continue
        if _RANK[verdict["confidence"]] >= _RANK.get(row.get("cause_confidence"), 0):
            _write(connection, row, verdict)
            stats["written"] += 1
            if verdict["confidence"] == "high":
                confirmed[(row["scope"], row["subject"], row["direction"])] = {
                    **row,
                    "cause_reason": verdict["reason"],
                    "cause_confidence": "high",
                    "cause_timing": verdict["timing"],
                    "cause_info_ids": verdict["info_ids"],
                }
    stats["used"] = used
    stats["cap"] = cap
    return stats
