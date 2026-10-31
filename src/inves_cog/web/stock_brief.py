"""Investor stock page. Derived display only; scores, states and valuation stay upstream."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from inves_cog.ingest.fundamentals.health import BLOCKING
from inves_cog.ingest.market import NY
from inves_cog.perception.news.rules import rank_day
from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY, EXCLUDED
from inves_cog.web.brief import (
    MISSING,
    PAPER_LABEL,
    THEME_VOLUME,
    _beijing_text,
    _books,
    _card_for,
    _context,
    _day_window,
    _event_for,
    _event_title,
    _freshness,
    _holding_row,
    _live_anomalies,
    _member,
    _news_events,
    _news_summary,
    _object,
    _one,
    _parse_ts,
    _reports,
    _rows,
    _snap_ret,
    _themes,
    _visible_anomalies,
    event_reasons,
    format_fraction,
    format_points,
    half_up,
    human_reason,
    level,
    volume_multiple,
)
from inves_cog.web.pages import _tickers

# Frozen rule-A entry book minima live in ENTRY. The page translates a miss; it does not rescore.
_BOOK_BELOW = {
    "quality": "质量分低于门槛",
    "growth": "增长分低于门槛",
    "valuation": "估值分低于门槛",
    "timing": "时机分低于门槛",
}
_BOOK_MISSING = {"quality": "质量分缺失", "growth": "增长分缺失", "valuation": "估值分缺失"}
_HEALTH_REASON = {
    "no_bar": "缺少行情",
    "stale_fundamentals": "财报过期",
    "revenue_tag_gap": "营收口径有缺口",
    "q4_missing": "四季报缺失",
    "companyfacts_lag": "公司事实滞后",
    "core_field_missing": "核心字段缺失",
    "implausible_value": "数值不可信",
    "split_suspect": "疑似拆股，估值未启用",
    "insufficient_history": "历史不足，无法对照均线",
}
_TIER_WORD = (("attack", "进攻"), ("defense", "防守"), ("normal", "普通"))
_EVENT_TITLE = re.compile(r"^(?P<name>.*?) \d+ 只(?P<verb>集体下跌|集体上涨|同日下跌|同日上涨)$")
_LOWER = re.compile(r"[a-z_]")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_OVERSOLD = 30
_SPARK_LIMIT = 60
_NEWS_LIMIT = 10
_RETURN_LAGS = (5, 20, 60)
STOCK_FORMULAS = (
    "近 N 日涨跌 = 当日收盘 / N 个交易日前的收盘 − 1；交易日不足则暂缺。",
    "折线使用最近不超过 60 个交易日的收盘价，点数等于这些交易日的个数。",
    "成交量倍数 = 当日成交量 / 前 20 日均量；达到 1.3 倍称为放量。",
    "RSI 低于 30 标注接近超卖。RSI、距 50 日线、距 200 日线和距一年高点直接取上游。",
    "参考价 = 现价 / (1 + 上游百分比 / 100)。",
    "相对板块强弱直接取当日残差，正数为强于板块，负数为弱于板块。",
    "空头占比、回补天数与变化沿用最近一期不晚于截点的记录。",
    "主题当日表现 = 该主题有收益的成员当日收益算术平均。",
    "前瞻市盈率 = 现价 / 截点内最新一致预期每股收益。",
    "我的仓位只列出该持仓类型会执行的卖出价位，距离写成还需上涨或还需下跌。",
    "不可买卡点把规则 A 的缺失原因、排除红线、现金流约束和四本账门槛译成人话，不重算分数。",
    "页面只引用已有估值输入，不给出目标价。",
)


def session_return(closes, lag):
    """Close-to-close return across `lag` trading sessions. A short history stays missing."""
    if lag < 1 or len(closes) <= lag:
        return None
    base = closes[-1 - lag]
    if not base:
        return None
    return closes[-1] / base - 1


def spark_closes(closes):
    """The last 60 available closes. The count is however many sessions exist, at most 60."""
    return list(closes[-_SPARK_LIMIT:])


def pace_clause(multiple, rsi):
    if multiple is None:
        volume = f"放量{MISSING}"
    else:
        shown = f"{half_up(multiple, 1):.1f}"
        volume = f"放量 {shown} 倍" if multiple >= THEME_VOLUME else f"成交量 {shown} 倍"
    if rsi is None:
        oscillator = f"RSI {MISSING}"
    else:
        note = " 接近超卖" if rsi < _OVERSOLD else ""
        oscillator = f"RSI {int(half_up(rsi, 0))}{note}"
    return f"{volume}、{oscillator}"


def follow_clause(title):
    if not title:
        return "未见联动事件"
    match = _EVENT_TITLE.match(str(title))
    if match:
        return f"随 {match.group('name')}{match.group('verb')}"
    return f"随 {title}"


def position_clause(held, shares, buyable, blocker, kind=None):
    if held:
        count = MISSING if shares is None else str(int(half_up(shares, 0)))
        return f"纸面持有 {count} 股，{kind or MISSING}"
    if buyable is True:
        return "尚未持有，可买"
    if buyable is False:
        return f"不可买，{blocker or MISSING}"
    return f"买入资格{MISSING}"


def stock_oneliner(ticker, ret, follow, multiple, rsi, *, held, shares, buyable, blocker, kind=None):
    pace = pace_clause(multiple, rsi)
    position = position_clause(held, shares, buyable, blocker, kind)
    return f"{ticker} 今日 {format_fraction(ret)}，{follow}；{pace}；{position}。"


def resid_sentence(value):
    if value is None:
        return f"相对板块{MISSING}"
    if value == 0:
        return "与板块持平"
    shown = f"{half_up(abs(value), 1):.1f}"
    side = "强于板块" if value > 0 else "弱于板块"
    return f"{side} {shown}σ"


def forward_pe(price, eps):
    if price is None or eps in (None, 0):
        return None
    return float(price) / float(eps)


def plain_text(text):
    """Drop English tier codes from a sentence that is already meant for the page."""
    cleaned = "" if text is None else str(text)
    for word, label in _TIER_WORD:
        cleaned = cleaned.replace(word, label)
    if not cleaned or _LOWER.search(cleaned):
        return MISSING
    return cleaned


def plain_skip(text):
    """Human sentence for a stored skip. Rule ids and English tier names do not remain."""
    cleaned = human_reason(text)
    if not cleaned:
        return MISSING
    return plain_text(cleaned)


def _reason_text(reason):
    if not reason:
        return None
    if str(reason).startswith("missing_book:"):
        keys = [part for part in str(reason).split(":", 1)[1].split(",") if part]
        labels = [_BOOK_MISSING.get(key) for key in keys]
        if not keys or any(item is None for item in labels):
            return None
        return "、".join(labels)
    labels = [_HEALTH_REASON.get(part) for part in str(reason).split(";")]
    if not labels or any(item is None for item in labels):
        return None
    return "、".join(labels)


def buy_blocker(score):
    """One Chinese blocker for a name rule A will not buy. Passing names have none."""
    if not score or score.get("entry_pass"):
        return None
    if score.get("null_reason"):
        return _reason_text(score.get("null_reason")) or MISSING
    for line in score.get("red_lines") or []:
        if line in EXCLUDED:
            return line
    tier = score.get("tier")
    bounds = None if tier is None else ENTRY.get(tier)
    if bounds is not None:
        books = score.get("books") or {}
        for key, bound in zip(BOOK_KEYS, bounds, strict=True):
            value = books.get(key)
            if value is None or value < bound:
                return _BOOK_BELOW[key]
    if score.get("m32_ok") is False:
        return "进攻仓现金与增长不足"
    if tier is None:
        return "未分档"
    return MISSING


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    return float(value)


def _bars(connection, symbol, day):
    return _rows(
        connection,
        """
        SELECT * FROM ingest.bars_daily
        WHERE ticker = %s AND trade_date <= %s
        ORDER BY trade_date
        """,
        (symbol, day),
    )


def _score_row(connection, day, symbol):
    return _one(
        connection,
        """
        SELECT tech, derived, quality, growth, valuation, timing, red_lines, tier,
               m32_ok, gate_pass, entry_pass, null_reason
        FROM trading.daily_scores
        WHERE signal_date = %s AND ticker = %s
        ORDER BY (extractor = 'fixed') DESC, params_version DESC
        LIMIT 1
        """,
        (day, symbol),
    )


def _latest_score_row(connection, day, symbol):
    """B-068: today's score is written after the close; carry the latest earlier one."""
    return _one(
        connection,
        """
        SELECT signal_date, tech, derived, quality, growth, valuation, timing, red_lines, tier,
               m32_ok, gate_pass, entry_pass, null_reason
        FROM trading.daily_scores
        WHERE signal_date < %s AND ticker = %s
        ORDER BY signal_date DESC, (extractor = 'fixed') DESC, params_version DESC
        LIMIT 1
        """,
        (day, symbol),
    )


def _snap_tag(snap, day=None):
    """IEX/SIP source tag; a snapshot from an earlier ET date shows its date."""
    moment = snap["as_of"].astimezone(NY)
    source = snap.get("source") or ""
    session = {"pre": "盘前", "regular": "盘中", "post": "盘后", "overnight": "隔夜"}.get(snap.get("session"), "")
    if day is not None and moment.date() != day:
        if source == "Alpaca:iex":
            return f"IEX {moment:%m/%d %H:%M:%S}"
        return f"{session} {moment:%m/%d %H:%M}".strip()
    if source == "Alpaca:iex":
        return f"IEX 实时 {moment:%H:%M:%S}"
    if source == "Alpaca:delayed_sip":
        return f"延迟 15 分 {moment:%H:%M}"
    return f"{session} {moment:%H:%M}".strip()


def _gate_score(row):
    if row is None:
        return None
    return {
        "books": _books(row) or {},
        "red_lines": list(row["red_lines"] or []),
        "tier": row["tier"],
        "m32_ok": row["m32_ok"],
        "gate_pass": row["gate_pass"],
        "entry_pass": bool(row["entry_pass"]),
        "null_reason": row["null_reason"],
        "tech": row["tech"],
        "derived": row["derived"],
    }


def _sessions(connection, day, symbol):
    rows = _rows(
        connection,
        """
        SELECT session, ret, resid_z
        FROM marketstate.daily
        WHERE trade_date = %s AND ticker = %s
        """,
        (day, symbol),
    )
    found = {row["session"]: row for row in rows}
    return found.get("close"), found.get("post")


def _news(connection, symbol, cutoff):
    rows = _rows(
        connection,
        """
        SELECT published_at, first_seen_at, source, headline, extraction_source
        FROM ingest.info_items
        WHERE kind = 'news' AND first_seen_at <= %s AND %s = ANY(tickers)
          AND (published_at IS NULL OR published_at <= %s)
        ORDER BY published_at DESC NULLS LAST, info_id DESC
        LIMIT %s
        """,
        (cutoff, symbol, cutoff, _NEWS_LIMIT),
    )
    items = []
    for row in rows:
        published = _parse_ts(row["published_at"])
        items.append(
            {
                "summary": _news_summary(_object(row["extraction_source"]), row["headline"]),
                "source": row["source"] or MISSING,
                "published_beijing": _beijing_text(published),
            }
        )
    return items


def _consensus(connection, symbol, cutoff):
    snapshot = _one(
        connection,
        """
        SELECT request_id, fetched_at, status
        FROM valuation_v1.consensus_snapshots
        WHERE ticker = %s AND kind = 'response' AND fetched_at <= %s
        ORDER BY fetched_at DESC, id DESC
        LIMIT 1
        """,
        (symbol, cutoff),
    )
    if snapshot is None or snapshot["status"] != "ok":
        return None
    rows = _rows(
        connection,
        """
        SELECT horizon, eps_avg, eps_count
        FROM valuation_v1.consensus_snapshots
        WHERE request_id = %s AND kind = 'estimate' AND horizon = ANY(%s)
        """,
        (snapshot["request_id"], ["FY1", "FY2"]),
    )
    found = {row["horizon"]: row for row in rows}
    if not found:
        return None
    return {"fetched_at": snapshot["fetched_at"], "rows": found}


def _exposures(connection, ids, symbol):
    if not ids:
        return {}
    rows = _rows(
        connection,
        """
        SELECT anomaly_id, exposure
        FROM perception.ticker_status
        WHERE anomaly_id = ANY(%s) AND ticker = %s
        """,
        (ids, symbol),
    )
    return {row["anomaly_id"]: row["exposure"] for row in rows}


def _events_for(connection, context, day, symbol):
    chosen = []
    for row in _visible_anomalies(context["anomalies"], context["stocks"]):
        names = _tickers(row["members"])
        if symbol not in names:
            continue
        chosen.append(row)
    chosen.sort(key=lambda row: (-(row["max_abs_z"] or -1), row["anomaly_id"]))
    reports = _reports(connection, [row["anomaly_id"] for row in chosen])
    exposure = _exposures(connection, [row["anomaly_id"] for row in chosen], symbol)
    events = []
    for row in chosen:
        view = context["events"].get(row["anomaly_id"])
        reasons = event_reasons(reports.get(row["anomaly_id"]), day)
        title = _event_title(list(row["baskets"] or []), _tickers(row["members"]), row["direction"], context["catalog"])
        status = row["status"] if view is None else view["lifecycle"]
        shown = exposure.get(row["anomaly_id"]) or MISSING
        if _LOWER.search(str(shown)):
            shown = MISSING
        events.append(
            {
                "title": title,
                "status": status,
                "exposure": shown,
                "reasons": reasons,
            }
        )
    return events


def _trend_block(bars, day, close_row, post_row, member):
    closes = [float(row["close"]) for row in bars if row["close"] is not None]
    today = [row for row in bars if row["trade_date"] == day]
    prior = [row["volume"] for row in bars if row["trade_date"] < day and row["volume"] is not None]
    today_volume = None if not today else today[-1]["volume"]
    multiple = volume_multiple(today_volume, prior)
    returns = {lag: session_return(closes, lag) for lag in _RETURN_LAGS}
    price = member["price"]
    return {
        "close_date": next((row["trade_date"] for row in reversed(bars) if row["close"] is not None), None),
        "ret": None if close_row is None else _num(close_row["ret"]),
        "post": None if post_row is None else _num(post_row["ret"]),
        "ret_5": returns[5],
        "ret_20": returns[20],
        "ret_60": returns[60],
        "dev50": member["dev50"],
        "ma50": level(price, member["dev50"]),
        "price_vs_ma200": member["price_vs_ma200"],
        "ma200": level(price, member["price_vs_ma200"]),
        "drawdown252": member["drawdown252"],
        "year_high": level(price, member["drawdown252"]),
        "rsi": member["rsi"],
        "volume_multiple": multiple,
        "closes": spark_closes(closes),
        "price": price,
    }


def _quote_date(value):
    if value is None:
        return MISSING
    if isinstance(value, datetime):
        return value.astimezone(NY).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = _parse_ts(value)
    if parsed is None:
        return MISSING
    return parsed.astimezone(NY).date().isoformat()


def _beijing_day(value):
    parsed = value if isinstance(value, datetime) else _parse_ts(value)
    if parsed is None:
        return MISSING
    return parsed.astimezone(_SHANGHAI).date().isoformat()


def _estimate_view(row, price):
    if row is None:
        return {"eps": None, "count": None, "forward_pe": None}
    eps = _num(row["eps_avg"])
    return {
        "eps": eps,
        "count": None if row["eps_count"] is None else int(row["eps_count"]),
        "forward_pe": forward_pe(price, eps),
    }


def _why_not(plan_payload, symbol):
    payload = plan_payload if isinstance(plan_payload, dict) else {}
    for skip in payload.get("skips") or []:
        if isinstance(skip, dict) and skip.get("ticker") == symbol and skip.get("reason_zh"):
            return plain_skip(skip.get("reason_zh"))
    return "符合买入条件，当日没有买入记录"


def _position_block(symbol, held, member, gate, context, valuation):
    plan_payload = _object(context["plan"]["payload"]) if context["plan"] else {}
    pending = [row for row in context["pending"] if row["ticker"] == symbol]
    if held:
        position = context["positions"][symbol]
        row = _holding_row(
            symbol, position, member, context["sell"], context["pending"], plan_payload, valuation, context
        )
        return {
            "kind": "held",
            "holding_kind": row["kind_label"],
            "shares": _num(row["shares"]),
            "avg_cost": row["avg_cost"],
            "price": row["price"],
            "pnl": row["pnl"],
            "levels": row["levels"],
            "ruler": row["ruler"],
            "day": row["day"],
            "ma200": row["ma200"],
            "pending": [plain_skip(item.get("reason_zh")) for item in pending],
            "next_step": plain_text(row["next_step"]),
            "blocker": None,
            "why_not": None,
        }
    buyable = None if gate is None else bool(gate["entry_pass"])
    if buyable is True:
        kind, blocker, why_not = "buyable", None, _why_not(plan_payload, symbol)
    elif buyable is False:
        kind, blocker, why_not = "blocked", buy_blocker(gate), None
    else:
        kind, blocker, why_not = "unknown", None, None
    return {
        "kind": kind,
        "shares": None,
        "price": member["price"],
        "ma50": level(member["price"], member["dev50"]),
        "year_high": level(member["price"], member["drawdown252"]),
        "blocker": blocker,
        "why_not": why_not,
        "next_step": None,
        "pending": [],
    }


def _theme_view(context, day, symbol):
    sector = context["catalog"]["sector_of"].get(symbol)
    if sector is None:
        return None, None
    for theme in _themes(context, day):
        if theme["sector"] == sector:
            return sector, theme["average"]
    return sector, None


def _lead_event(events):
    if not events:
        return "未见联动事件"
    return follow_clause(events[0]["title"])


def _sentences(symbol, trend, short_text, resid_text, sector, theme_ret, news, events, valuation, consensus, position):
    trend_sentence = (
        f"收盘 {format_fraction(trend['ret'])}，盘后 {format_fraction(trend['post'])}；"
        f"近 5 日 {format_fraction(trend['ret_5'])}，近 20 日 {format_fraction(trend['ret_20'])}，"
        f"近 60 日 {format_fraction(trend['ret_60'])}。"
    )
    theme_name = sector or MISSING
    funds_parts = [
        p for p in (short_text, resid_text, f"{theme_name}当日 {format_fraction(theme_ret)}") if p and p != MISSING
    ]
    funds_sentence = "；".join(funds_parts) + "。"
    if news:
        news_sentence = f"最近 {len(news)} 条，最新：{news[0]['summary']}。"
    else:
        news_sentence = "截点内没有该股新闻。"
    if events:
        event_sentence = f"{events[0]['title']}，状态 {events[0]['status']}。"
    else:
        event_sentence = "没有涉及该股的联动事件。"
    if not isinstance(valuation, dict):
        valuation_sentence = f"估值{MISSING}。"
    elif valuation.get("state") == "未估值":
        valuation_sentence = f"{valuation.get('text') or '未估值'}。"
    else:
        pe = valuation.get("pe_text") or MISSING
        implied = format_points(valuation.get("implied_growth"))
        growth = format_points(valuation.get("rev_cagr_3y"))
        valuation_sentence = f"市盈率 {pe}，隐含增速 {implied}，过去三年营收 {growth}。"
    if consensus is None:
        consensus_sentence = "暂无一致预期（轮询中）。"
    else:
        consensus_sentence = (
            f"FY1 每股收益 {_eps(consensus['fy1']['eps'])}，机构 {_count(consensus['fy1']['count'])} 家；"
            f"FY2 每股收益 {_eps(consensus['fy2']['eps'])}，机构 {_count(consensus['fy2']['count'])} 家；"
            f"前瞻市盈率 {_pe(consensus['fy1']['forward_pe'])} 与 {_pe(consensus['fy2']['forward_pe'])}；"
            f"快照 {consensus['as_of']}。"
        )
    if position["kind"] == "held":
        position_sentence = (
            f"纸面持有 {_count(position['shares'])} 股，盈亏 {format_fraction(position['pnl'])}，"
            f"下一步 {position['next_step']}。"
        )
    elif position["kind"] == "buyable":
        position_sentence = f"尚未持有，可买；为什么没买：{position['why_not']}。"
    elif position["kind"] == "blocked":
        position_sentence = f"不可买，{position['blocker'] or MISSING}。"
    else:
        position_sentence = f"买入资格{MISSING}。"
    return {
        "trend": trend_sentence,
        "funds": funds_sentence,
        "news": news_sentence,
        "events": event_sentence,
        "valuation": valuation_sentence,
        "consensus": consensus_sentence,
        "position": position_sentence,
    }


def _eps(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 2):.2f}"


def _pe(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 1):.1f}"


def _count(value):
    if value is None:
        return MISSING
    return str(int(half_up(value, 0)))


def page_brief_stock(connection, day, clock, symbol):
    """One ticker, cut off at the same clock as the other brief pages."""
    symbol = str(symbol or "").strip().upper()
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    bars = _bars(connection, symbol, day)
    is_today = day == clock.today_trade_date()
    raw_score = _score_row(connection, day, symbol)
    carried_from = None
    if raw_score is None and is_today:
        raw_score = _latest_score_row(connection, day, symbol)
        carried_from = None if raw_score is None else raw_score["signal_date"]
    stocks = context.get("stocks") or set()
    in_scope = (
        symbol in context["pool"]
        or symbol in context["positions"]
        or symbol in stocks
        or raw_score is not None
        or symbol in _segment_map()
        or _earnings_card(connection, symbol) is not None
    )
    if not bars:
        if not in_scope:
            return {
                "page": f"/s/{symbol}",
                "date": day,
                "symbol": symbol,
                "title": symbol,
                "no_data": True,
                "headings": [],
                "label": PAPER_LABEL,
            }
        # covered ticker without bars: fall through and let the page
        # render with its own missing-data markers
        bars = [{"trade_date": day, "close": None, "volume": None}]
    if not in_scope:
        return _untracked_page(connection, symbol, day, clock, bars)
    gate = _gate_score(raw_score)
    score_row = (
        None
        if gate is None
        else {
            "tech": gate["tech"],
            "derived": gate["derived"],
            "quality": gate["books"].get("quality"),
            "growth": gate["books"].get("growth"),
            "valuation": gate["books"].get("valuation"),
            "timing": gate["books"].get("timing"),
            "entry_pass": gate["entry_pass"],
            "tier": gate["tier"],
        }
    )
    close_row, post_row = _sessions(connection, day, symbol)
    daily = {} if close_row is None else {symbol: {"ret": _num(close_row["ret"])}}
    held = symbol in context["positions"]
    snap = (context.get("intraday") or {}).get(symbol) if is_today else None
    member = _member(
        symbol, day, {symbol: bars}, score_row, daily, held, [], snap=snap, elapsed=context.get("elapsed_minutes")
    )
    trend = _trend_block(bars, day, close_row, post_row, member)
    if snap is not None and _snap_ret(snap) is not None:
        trend["ret"] = _snap_ret(snap)
        trend["ret_tag"] = _snap_tag(snap, day)
        if snap["as_of"].astimezone(NY).date() != day:
            trend["ret_label"] = "最近"
        # 盘后 row: latest post-session snapshot (may be the previous session's)
        post_day = snap["as_of"].astimezone(NY).date()
        post_close = next((float(r["close"]) for r in bars if r["trade_date"] == post_day and r["close"]), None)
        if snap.get("session") == "post" and post_close:
            trend["post"] = float(snap["last"]) / post_close - 1
            trend["post_tag"] = _snap_tag(snap, day)
    valuation = _card_for(context, symbol, score_row, member["price"])
    # Fair and neutral prices stay off this payload.
    valuation.pop("neutral", None)
    short_text = None
    resid = None if close_row is None else _num(close_row["resid_z"])
    sector, theme_ret = _theme_view(context, day, symbol)
    news = _news(connection, symbol, context["cutoff"])
    events = _events_for(connection, context, day, symbol)
    consensus_raw = _consensus(connection, symbol, context["cutoff"])
    if consensus_raw is None:
        consensus = None
    else:
        consensus = {
            "as_of": _beijing_day(consensus_raw["fetched_at"]),
            "fy1": _estimate_view(consensus_raw["rows"].get("FY1"), member["price"]),
            "fy2": _estimate_view(consensus_raw["rows"].get("FY2"), member["price"]),
        }
    position = _position_block(symbol, held, member, gate, context, valuation)
    from inves_cog.web.risk_brief import EMPTY, RISK_FORMULAS, portfolio_view

    if held:
        found = portfolio_view(connection, day, context)["by_ticker"].get(symbol)
        position["risk_text"] = EMPTY if found is None else found["text"]
        position["risk_level"] = None if found is None else found["level"]
    buyable = None if gate is None else gate["entry_pass"]
    if held:
        buyable = False
    oneliner = stock_oneliner(
        symbol,
        trend["ret"],
        _lead_event(events),
        trend["volume_multiple"],
        trend["rsi"],
        held=held,
        shares=position.get("shares"),
        buyable=False if held else buyable,
        blocker=position.get("blocker"),
        kind=position.get("holding_kind"),
    )
    sentences = _sentences(
        symbol,
        trend,
        short_text,
        resid_sentence(resid),
        sector,
        theme_ret,
        news,
        events,
        valuation,
        consensus,
        position,
    )
    news_stamp = news[0]["published_beijing"] if news else MISSING
    news_feed = _news_feed(connection, symbol, day, context)
    next_earnings = _next_earnings(context["earnings_cal"], symbol, day)
    tech = context["technicals"].get(symbol)
    range_row = context["ranges"].get(symbol)
    value_stamp = MISSING if range_row is None else day.isoformat()
    consensus_stamp = "暂无" if consensus is None else consensus["as_of"]
    return {
        "page": f"/s/{symbol}",
        "date": day,
        "freshness": _freshness(context, clock) if is_today else None,
        "carried_from": None if carried_from is None else carried_from.isoformat(),
        "symbol": symbol,
        "title": symbol,
        "oneliner": oneliner,
        "headings": ["走势与位置", "资金与情绪", "新闻与事件", "基本面与估值", "我的仓位"],
        "trend": trend,
        "short_text": short_text,
        "resid_text": resid_sentence(resid),
        "sector": sector,
        "theme_ret": theme_ret,
        "news": news,
        "news_feed": news_feed,
        "event": _event_for(_news_events(connection, day, day == clock.today_trade_date(), clock), symbol),
        "next_earnings": next_earnings,
        "earnings_card": _earnings_card(connection, symbol),
        "price_now": _safe(connection, lambda: _price_now(connection, symbol, day, bars, snap), {}),
        "chart": _safe(connection, lambda: _chart_data(bars), []),
        "earnings_marks": _safe(connection, lambda: _earnings_marks(connection, symbol, day), []),
        "anomaly_marks": _safe(connection, lambda: _anomaly_marks(connection, symbol, day), []),
        "peers": _safe(connection, lambda: _peers_table(connection, symbol, day, _segment_map()), ([], None)),
        "bar_stats": _safe(connection, lambda: _bar_stats(connection, symbol, day, bars, next_earnings), {}),
        "intraday_series": _safe(connection, lambda: _intraday_series(connection, symbol, day), []),
        "analyst": _safe(connection, lambda: _analyst_summary(connection, symbol), {}),
        "analyst_actions": _safe(connection, lambda: _analyst_actions(connection, symbol, day), []),
        "earnings_hist": _safe(connection, lambda: _earnings_hist(connection, symbol, bars), []),
        "news_modules": {
            "live": _safe(connection, lambda: [dict(r) for r in _live_anomalies(connection, day, False)], [])
        },
        "tech": tech,
        "events": events,
        "books": None if gate is None else gate["books"],
        "valuation": valuation,
        "consensus": consensus,
        "position": position,
        "sentences": sentences,
        "stamps": [
            {"label": "行情", "value": day.isoformat()},
            {"label": "新闻", "value": news_stamp},
            {"label": "估值", "value": value_stamp},
            {"label": "一致预期", "value": consensus_stamp},
        ],
        "formulas": [*STOCK_FORMULAS, *RISK_FORMULAS],
        "label": PAPER_LABEL,
    }


def covered_gate_reasons():
    """Production gate codes this page knows how to say. Tests fail if a new one appears."""
    return set(_HEALTH_REASON) | set(BLOCKING) | set(EXCLUDED) | set(_BOOK_BELOW) | set(_BOOK_MISSING)


def _news_feed(connection, symbol, day, context):
    """This ticker's last-7-day news, ranked by importance then time."""
    start, end = _day_window(day)
    start = start - timedelta(days=7)
    rows = _rows(
        connection,
        """
        SELECT info_id, published_at, first_seen_at, source, headline, tickers, url, extraction_source
        FROM ingest.info_items
        WHERE kind = 'news' AND published_at >= %s AND published_at < %s AND %s = ANY(tickers)
        ORDER BY published_at DESC, info_id
        """,
        (start, end, symbol),
    )
    items = []
    for row in rows:
        published = _parse_ts(row["published_at"])
        seen = _parse_ts(row["first_seen_at"])
        items.append(
            {
                "info_id": row["info_id"],
                "summary": _news_summary(_object(row["extraction_source"]), row["headline"]),
                "headline": row["headline"] or "",
                "url": row["url"],
                "source": row["source"] or MISSING,
                "published_at": None if published is None else published.isoformat(),
                "published_beijing": _beijing_text(published),
                "tickers": [name for name in (row["tickers"] or []) if isinstance(name, str)],
                "first_seen_at": None if seen is None else seen.isoformat(),
                "late": seen is not None and seen > context["cutoff"],
            }
        )
    held = set(context["positions"])
    universe = set(context["pool"]) | held
    ranked = rank_day(items, universe, held, day)
    feed = [n for n in ranked if symbol in n["rule"].primary_tickers or symbol in n["tickers"]]
    feed.sort(key=lambda n: (-n["rule"].importance, -(n["published"].timestamp() if n["published"] else 0)))
    return feed[:15]


def _next_earnings(earnings, symbol, day):
    if not earnings:
        return None
    future = sorted(r for r in earnings if r["ticker"] == symbol and r["report_date"] >= day)
    return future[0] if future else None


def _safe(connection, fn, fallback):
    """Each optional block runs in a savepoint so one failure can't poison
    the read-only transaction shared by the rest of the page."""
    try:
        with connection.transaction():
            return fn()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("stock page optional block failed: %r", exc)
        return fallback


def _segment_map():
    from inves_cog.perception.core_companies import core_companies

    return core_companies()


def _earnings_card(connection, symbol):
    """B-072: this ticker's latest earnings card row; None when absent."""
    try:
        row = connection.execute(
            "SELECT ticker, report_date, report_time, stage, card, missing "
            "FROM perception.earnings_cards WHERE ticker=%s ORDER BY report_date DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        return {**dict(row), "report_date": str(row["report_date"])}
    except Exception:
        return None


def _chart_data(bars, limit_days=260):
    """1y of daily OHLC + volume for the client-side lightweight chart."""
    rows = [
        {
            "d": str(r["trade_date"]),
            "o": float(r.get("open") or r["close"]),
            "h": float(r.get("high") or r["close"]),
            "l": float(r.get("low") or r["close"]),
            "c": float(r["close"]),
            "v": int(r["volume"] or 0),
        }
        for r in bars
        if r["close"] is not None
    ]
    return rows[-limit_days:]


def _price_now(connection, symbol, day, bars, snap):
    """Latest quote: same-day intraday snapshot wins, else latest close."""
    if snap and snap.get("last") is not None:
        return {
            "px": float(snap["last"]),
            "at": str(snap["as_of"]),
            "session": snap.get("session"),
            "source": "快照",
            "ret": _snap_ret(snap),
        }
    close = next((float(r["close"]) for r in reversed(bars) if r["close"] is not None), None)
    prev = None
    seen = [float(r["close"]) for r in bars if r["close"] is not None]
    if len(seen) >= 2:
        prev = seen[-2]
    return {
        "px": close,
        "at": str(bars[-1]["trade_date"]) if bars else None,
        "session": "close",
        "source": "收盘",
        "ret": (close / prev - 1) if close and prev else None,
    }


def _peers_table(connection, symbol, day, segment_map):
    """Same-segment core companies + same L2/L3 baskets: px, today, 5d."""
    seg = segment_map.get(symbol)
    peers = sorted(t for t, s in segment_map.items() if s == seg and t != symbol)[:6]
    baskets = connection.execute(
        "SELECT basket_id, name, members FROM graph.baskets WHERE level IN ('L2','L3')"
    ).fetchall()
    for b in baskets:
        names = [m["ticker"] if isinstance(m, dict) else m for m in (b["members"] or [])]
        if symbol in names:
            for t in names:
                if t != symbol and t not in peers:
                    peers.append(t)
    peers = peers[:8]
    out = []
    for t in peers:
        pb = _bars(connection, t, day)
        closes = [float(r["close"]) for r in pb if r["close"] is not None]
        if len(closes) >= 6:
            out.append(
                {"ticker": t, "px": closes[-1], "ret": closes[-1] / closes[-2] - 1, "ret5": closes[-1] / closes[-6] - 1}
            )
        elif len(closes) >= 2:
            out.append({"ticker": t, "px": closes[-1], "ret": closes[-1] / closes[-2] - 1, "ret5": None})
    return out, seg


def _earnings_marks(connection, symbol, day):
    rows = connection.execute(
        "SELECT report_date, time FROM ingest.earnings_calendar WHERE ticker=%s AND report_date <= %s",
        (symbol, day),
    ).fetchall()
    return [{"d": str(r["report_date"]), "t": r["time"]} for r in rows]


def _anomaly_marks(connection, symbol, day):
    days = []
    try:
        rows = connection.execute(
            "SELECT DISTINCT trade_date FROM perception.anomalies a "
            "WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(a.members) m "
            "            WHERE m->>'ticker' = %s)",
            (symbol,),
        ).fetchall()
        days += [str(r["trade_date"]) for r in rows]
    except Exception:
        pass
    try:
        live = connection.execute(
            "SELECT DISTINCT trade_date FROM perception.live_anomalies WHERE subject=%s",
            (symbol,),
        ).fetchall()
        days += [str(r["trade_date"]) for r in live]
    except Exception:
        pass
    return sorted(set(days))


def _untracked_page(connection, symbol, day, clock, bars):
    """Not in pool: price + chart only, everything else states 不在监控范围."""
    snap_row = connection.execute(
        "SELECT last, as_of, session FROM ingest.intraday_snapshots WHERE ticker=%s ORDER BY as_of DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    snap = dict(snap_row) if snap_row else None
    price = _price_now(connection, symbol, day, bars, snap)
    return {
        "page": f"/s/{symbol}",
        "date": day,
        "symbol": symbol,
        "title": symbol,
        "untracked": True,
        "price_now": price,
        "chart": _chart_data(bars),
        "earnings_marks": _earnings_marks(connection, symbol, day),
        "anomaly_marks": _anomaly_marks(connection, symbol, day),
        "headings": [],
        "label": PAPER_LABEL,
    }


def _bar_stats(connection, symbol, day, bars, next_earnings):
    """Day hi/lo, 52w hi/lo + position, volume ratio, next earnings."""
    closes = [float(r["close"]) for r in bars if r["close"] is not None]
    if not closes:
        return {}
    last = closes[-1]
    w52 = closes[-260:]
    hi52, lo52 = max(w52), min(w52)
    today = bars[-1]
    vols = [int(r["volume"] or 0) for r in bars[-21:-1] if r["volume"]]
    avg = sum(vols) / len(vols) if vols else None
    vr = int(today["volume"] or 0) / avg if avg else None
    pos = (last - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else None
    return {
        "day_hi": float(today["high"]) if today.get("high") else last,
        "day_lo": float(today["low"]) if today.get("low") else last,
        "hi52": hi52,
        "lo52": lo52,
        "pos52": pos,
        "vol": int(today["volume"] or 0),
        "vol_ratio": vr,
        "next_earnings": next_earnings,
    }


def _intraday_series(connection, symbol, day):
    rows = connection.execute(
        "SELECT as_of, last FROM ingest.intraday_snapshots WHERE ticker=%s AND as_of >= %s::date ORDER BY as_of",
        (symbol, day),
    ).fetchall()
    return [{"t": str(r["as_of"]), "p": float(r["last"])} for r in rows if r["last"] is not None]


def _analyst_summary(connection, symbol):
    """Latest consensus raw.analyst: target prices + rating counts."""
    row = connection.execute(
        "SELECT eps_cq, eps_cy, pt_mean, pt_median, coverage, raw "
        "FROM fundamentals.consensus_snapshot WHERE ticker=%s ORDER BY captured_at DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    raw = (row or {}).get("raw") or {}
    analyst = raw.get("analyst") or {}
    return {
        "eps_cq": row.get("eps_cq") if row else None,
        "eps_cy": row.get("eps_cy") if row else None,
        "pt_mean_col": row.get("pt_mean") if row else None,
        "pt_median_col": row.get("pt_median") if row else None,
        "coverage": row.get("coverage") if row else None,
        "pt_low": analyst.get("targetLowPrice"),
        "pt_high": analyst.get("targetHighPrice"),
        "pt_mean": analyst.get("targetMeanPrice"),
        "pt_median": analyst.get("targetMedianPrice"),
        "opinions": analyst.get("numberOfAnalystOpinions"),
        "trend": analyst.get("recommendationTrend") or {},
        "market_cap": analyst.get("marketCap"),
        "forward_pe": analyst.get("forwardPE"),
    }


def _analyst_actions(connection, symbol, day):
    return connection.execute(
        "SELECT action_date, firm, action, from_grade, to_grade, pt_action, prior_pt, current_pt, source "
        "FROM ingest.analyst_actions WHERE ticker=%s AND action_date<=%s ORDER BY action_date DESC LIMIT 60",
        (symbol, day),
    ).fetchall()


def _earnings_hist(connection, symbol, bars):
    """Last 8 quarters: EPS actual vs estimate + next-day move per report timing."""
    row = connection.execute(
        "SELECT raw FROM fundamentals.consensus_snapshot WHERE ticker=%s ORDER BY captured_at DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    hist = ((row or {}).get("raw") or {}).get("earnings_history") or []
    last_day = str(bars[-1]["trade_date"]) if bars else "9999"
    cal = {
        str(r["report_date"]): r
        for r in connection.execute(
            "SELECT report_date, time FROM ingest.earnings_calendar WHERE ticker=%s AND report_date<=%s",
            (symbol, last_day),
        ).fetchall()
    }
    # historical report dates: earnings events published right after each quarter end
    events = {}
    try:
        for r in connection.execute(
            "SELECT published_at FROM perception.news_events "
            "WHERE subject=%s AND kind='earnings_result' ORDER BY published_at",
            (symbol,),
        ).fetchall():
            ts = r["published_at"]
            events[
                str(ts.astimezone(ZoneInfo("America/New_York")).date() if hasattr(ts, "astimezone") else str(ts)[:10])
            ] = ts
    except Exception:
        pass
    closes = {str(r["trade_date"]): float(r["close"]) for r in bars if r["close"] is not None}
    dates = sorted(closes)

    def move(report_date, timing):
        if report_date not in dates:
            return None
        i = dates.index(report_date)
        if timing == "post":
            base = closes[dates[i]]
            nxt = closes[dates[i + 1]] if i + 1 < len(dates) else None
        else:
            base = closes[dates[i - 1]] if i > 0 else None
            nxt = closes[dates[i]]
        return (nxt / base - 1) if base and nxt else None

    out = []
    for q in hist[-8:]:
        qd = str(q.get("quarter_date") or "")
        rd = min((d for d in cal if d >= qd), default=None)
        timing = (cal.get(rd) or {}).get("time") if rd else None
        if rd is None and events:
            # closest earnings event within 90d after quarter end; timing by publish hour ET
            cand = min((d for d in events if qd <= d <= str(date.fromisoformat(qd) + timedelta(days=90))), default=None)
            if cand:
                rd = cand
                ts = events[cand]
                et = ts.astimezone(ZoneInfo("America/New_York")) if hasattr(ts, "astimezone") else None
                timing = "post" if et is None or et.hour >= 16 else "pre"
        out.append(
            {
                "q": qd,
                "est": float(q["eps_est"]) if q.get("eps_est") is not None else None,
                "act": float(q["eps_actual"]) if q.get("eps_actual") is not None else None,
                "gap": float(q["surprise_pct"]) if q.get("surprise_pct") is not None else None,
                "next_day": move(rd, timing) if rd else None,
                "report_date": rd,
            }
        )
    return out
