"""Synthetic candidate-payload items: member earnings events and sector/macro news.

These items are assembled from first-party rows (SEC 8-K receipt, earnings cards)
and from already-ingested macro/sector news. They are prepended to the retrieved
shortlist inside ``_retrieved`` so they always survive the 40-item payload cap,
and they obey the same point-in-time cutoff as every other input."""

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import trading_day

_NEW_YORK = ZoneInfo("America/New_York")

EARNINGS_ROLE = "财报事件"
SECTOR_ROLE = "板块或宏观"

_SESSION_LABEL = {"pre": "盘前", "post": "盘后", "intraday": "盘中", "closed": "休市"}

_DEFAULT_CFG = {
    "min_members": 5,
    "min_baskets": 2,
    "max_items": 10,
    "etfs": [],
    "macro_sources": [],
}


def _stamp(value):
    if isinstance(value, datetime):
        return value if value.utcoffset() is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value)
        except ValueError:
            return None
        return stamp if stamp.utcoffset() is not None else stamp.replace(tzinfo=timezone.utc)
    return None


def _members(anomaly):
    names = []
    for member in anomaly.get("members") or []:
        name = (member.get("ticker") or member.get("entity_id")) if isinstance(member, dict) else member
        if name and name not in names:
            names.append(name)
    return names


def _basket_ids(anomaly, registry):
    """Anomaly basket names resolved to registry ids (names may be ids already)."""
    by_name = {info.get("name"): basket_id for basket_id, info in registry.items() if info.get("name")}
    resolved = []
    for name in anomaly.get("baskets") or []:
        basket_id = name if name in registry else by_name.get(name)
        if basket_id and basket_id not in resolved:
            resolved.append(basket_id)
    return resolved


def _prev_trading_day(day):
    candidate = day - timedelta(days=1)
    while not trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def earnings_items(anomaly, events, cards, calendars, *, cutoff):
    """One synthetic item per member 8-K 2.02 accepted after the previous trading
    day's close and inside (event, window end], never past the cutoff."""
    end = _stamp(anomaly.get("ended_at"))
    limit = _stamp(cutoff)
    bounds = [v for v in (end, limit) if v is not None]
    upper = min(bounds) if bounds else None
    trade_day = anomaly.get("trade_date")
    if isinstance(trade_day, str):
        try:
            trade_day = date.fromisoformat(trade_day[:10])
        except ValueError:
            trade_day = None
    if trade_day is None:
        return []
    lower = datetime.combine(_prev_trading_day(trade_day), time(16, 0), tzinfo=_NEW_YORK)
    wanted = set(_members(anomaly))
    card_index = {(row.get("ticker"), str(row.get("report_date"))[:10]): row for row in cards or []}
    cal_index = {(row.get("ticker"), str(row.get("report_date"))[:10]): row for row in calendars or []}
    items = []
    for event in events or []:
        ticker = event.get("ticker")
        if ticker not in wanted or event.get("item") != "2.02":
            continue
        accepted = _stamp(event.get("accepted_at"))
        if accepted is None or accepted < lower or (upper is not None and accepted > upper):
            continue
        report_day = accepted.astimezone(_NEW_YORK).date().isoformat()
        card = card_index.get((ticker, report_day))
        calendar = cal_index.get((ticker, report_day))
        session = _SESSION_LABEL.get(event.get("session"), "未知时段")
        items.append(
            {
                "info_id": "earn:" + str(event.get("accession")),
                "kind": "earnings_event",
                "source": "SEC",
                "source_root": "SEC",
                "published_at": accepted,
                "first_seen_at": accepted,
                "headline": (
                    f"{ticker} 发布季度业绩（SEC 8-K 2.02，受理 "
                    f"{accepted.astimezone(timezone.utc).isoformat()}，{session}）"
                ),
                "summary": _earnings_summary(card, calendar, cutoff=limit),
                "tickers": [ticker],
                "entities": [ticker],
                "role": EARNINGS_ROLE,
            }
        )
    items.sort(key=lambda row: row["published_at"])
    return items


def _earnings_summary(card, calendar, *, cutoff):
    parts = []
    actual = estimate = None
    if card is not None:
        for event in (card.get("card") or {}).get("events") or []:
            if event.get("kind") != "earnings_result":
                continue
            seen = _stamp(event.get("first_seen_at"))
            if seen is None or (cutoff is not None and seen > cutoff):
                continue
            facts = event.get("facts") or {}
            actual = facts.get("eps_actual")
            estimate = facts.get("eps_est")
    if actual is not None and estimate is not None:
        parts.append(f"实际 EPS {actual}，预期 {estimate}（来源：earnings_cards，新闻标题解析）")
    else:
        parts.append("实际业绩未解析")
    forecast = (calendar or {}).get("eps_forecast")
    if forecast is not None:
        source = (calendar or {}).get("source") or "earnings_calendar"
        if estimate is None or str(forecast) != str(estimate):
            parts.append(f"earnings_calendar 预期 {forecast}（来源：{source}）")
    return "；".join(parts)


def sector_macro_items(anomaly, pool, *, registry, keywords, cfg=None, cutoff=None):
    """Sector-wide / macro news for anomalies spanning many members or baskets.

    Sources: kind='macro' rows, rows from configured macro sources, ETF-tagged
    news (ETF list in config), and ticker-less news whose headline/summary hits
    an affected basket's keyword list. Only attached when the anomaly has at
    least ``min_members`` members or ``min_baskets`` baskets."""
    cfg = {**_DEFAULT_CFG, **(cfg or {})}
    members = _members(anomaly)
    baskets = _basket_ids(anomaly, registry)
    if len(members) < cfg["min_members"] and len(baskets) < cfg["min_baskets"]:
        return []
    limit = _stamp(cutoff)
    etfs = set(cfg.get("etfs") or [])
    macro_sources = set(cfg.get("macro_sources") or [])
    etf_map = _etf_baskets(registry, etfs)
    word_map = _basket_keywords(baskets, registry, keywords or {})
    scored = []
    for item in pool or []:
        published = _stamp(item.get("published_at"))
        seen = _stamp(item.get("first_seen_at"))
        if published is None or seen is None:
            continue
        if limit is not None and max(published, seen) > limit:
            continue
        matched = _matched_baskets(item, baskets, etf_map, word_map, etfs, macro_sources)
        if matched is None:
            continue
        scored.append((len(matched), published, item))
    scored.sort(key=lambda row: (-row[0], -row[1].timestamp()))
    return [{**item, "role": SECTOR_ROLE} for _, _, item in scored[: cfg["max_items"]]]


def _etf_baskets(registry, etfs):
    """benchmark ETF -> basket ids, from factor_basis.tickers."""
    mapping = {}
    for basket_id, info in registry.items():
        basis = info.get("factor_basis") or {}
        if basis.get("kind") != "benchmark":
            continue
        for ticker in basis.get("tickers") or []:
            if ticker in etfs:
                mapping.setdefault(ticker, []).append(basket_id)
    return mapping


def _basket_keywords(baskets, registry, keywords):
    """Keywords per anomaly basket; an L3 basket inherits its L2 sector's list."""
    by_name = {info.get("name"): basket_id for basket_id, info in registry.items()}
    mapping = {}
    for basket_id in baskets:
        words = keywords.get(basket_id)
        if words is None:
            sector = ((registry.get(basket_id) or {}).get("factor_basis") or {}).get("sector")
            parent = by_name.get(sector)
            words = keywords.get(parent) if parent else None
        if words:
            mapping[basket_id] = [re.compile(r"\b" + re.escape(str(word)) + r"s?\b", re.IGNORECASE) for word in words]
    return mapping


def _matched_baskets(item, baskets, etf_map, word_map, etfs, macro_sources):
    """Affected-basket ids this item speaks to; None when the item is out of scope."""
    tickers = set(item.get("tickers") or [])
    matched = set()
    for etf in tickers & set(etf_map):
        matched.update(bid for bid in etf_map[etf] if bid in baskets)
    if tickers & etfs:
        return matched
    if not tickers:
        text = " ".join(str(item.get(key) or "") for key in ("headline", "summary"))
        for basket_id, words in word_map.items():
            if any(word.search(text) for word in words):
                matched.add(basket_id)
        if matched:
            return matched
    if item.get("kind") == "macro" or item.get("source") in macro_sources:
        return set()
    return None


def attach_context(anomaly, feed, *, registry, cfg=None, cutoff=None):
    """Feed rows come from the loader; this tags the anomaly for ``_retrieved``."""
    cfg = {**_DEFAULT_CFG, **(cfg or {})}
    items = earnings_items(anomaly, feed.get("events"), feed.get("cards"), feed.get("calendars"), cutoff=cutoff)
    items += sector_macro_items(
        anomaly,
        feed.get("pool"),
        registry=registry,
        keywords=feed.get("keywords"),
        cfg=cfg,
        cutoff=cutoff,
    )
    anomaly["context_items"] = items
    return anomaly
