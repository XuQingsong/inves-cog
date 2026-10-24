"""Investor brief pages. Simple derived values live only in this module."""

import re
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from inves_cog.ingest.market import NY, trading_day
from inves_cog.web.pages import (
    PAPER_LABEL,
    _anomalies,
    _events,
    _object,
    _one,
    _open,
    _parse_ts,
    _plan,
    _rows,
    _tickers,
    _universe,
)

PARAMS_ROOT = Path(__file__).resolve().parents[3] / "config" / "params"
UNIVERSE_PATH = Path(__file__).resolve().parents[3] / "config" / "universe.yaml"
# Returns in marketstate are fractions. Two percentage points is 0.02.
ROTATION_GAP = 0.02
BROAD_DROP = -0.02
BREADTH_RATIO = 0.5
MOVE_BAND = 0.07
DISASTER_NEAR = 0.20
VALUE_FAR = 2.0
NEWS_GAP = 1
STALE_NEWS_DAYS = 3
PENDING_GAP = 2
PRIOR_DAYS = 20
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")
LEADER_COUNT = (4, 5)
MISSING = "暂缺"
UNTRUSTED = "原因暂不可信"
JUDGMENT_ROTATION = "板块轮动而非全面恐慌"
JUDGMENT_BROAD = "普跌"
JUDGMENT_MIXED = "分化"
INDEX_LABELS = {"SPY": "标普 500", "QQQ": "纳指 100", "IWM": "罗素小盘"}
STYLE_LABELS = {
    "mtum_vlue": "动量相对价值",
    "rsp_spy": "等权相对市值加权",
    "iwm_qqq": "小盘相对纳指",
}
ETF_LABELS = {
    "XLP": "必需消费",
    "KRE": "区域银行",
    "XLU": "公用事业",
    "XLV": "医疗",
    "XLE": "能源",
    "XLF": "金融",
    "XLI": "工业",
    "XLK": "科技",
    "XLY": "可选消费",
    "XLC": "通信",
    "SMH": "半导体",
    "SOXX": "半导体",
    "IGV": "软件",
}
AI_SECTORS = {
    "AI 算力芯片",
    "AI 网络与光通信",
    "AI 服务器与算力云",
    "存储",
    "半导体设备",
    "数据中心电力与散热",
}
THEME_SOLD = -0.05
THEME_DOWN = -0.01
THEME_UP = 0.01
THEME_VOLUME = 1.3
THEME_RSI = 35
_RULE_ID = re.compile(r"M-\d+")
FORMULAS = (
    "主题平均涨跌 = 该主题有收益的成员当日收益算术平均。",
    "成交量倍数 = 当日成交量 / 前20日均量。",
    "止盈线 = 成本 × 卖出参数中的翻倍倍数。",
    "灾难止损线 = 峰值与现价的较大者 × 卖出参数中的灾难比例。",
    "200日线 = 现价 / (1 + 距200日线百分比/100)。",
    "50日线 = 现价 / (1 + 距50日线百分比/100)。",
    "一年高点 = 现价 / (1 + 距一年高点百分比/100)。",
    "估值展示复制打分里的市盈率与估值输入，不重算，不展示中性价。",
    "轮动：罗素小盘减纳指100大于2个百分点，且上涨家数大于下跌家数。",
    "普跌：标普500小于等于-2%，且上涨家数/下跌家数小于0.5。",
    "其余为分化。",
    "距200日线、距一年高点、RSI、四本账直接取上游，页面不重算。",
)


def judge(spy, qqq, iwm, advancers, decliners):
    """Three-way market line. Rotation is checked before a broad drop."""
    if None not in (iwm, qqq, advancers, decliners) and (iwm - qqq) > ROTATION_GAP and advancers > decliners:
        return JUDGMENT_ROTATION
    if (
        None not in (spy, advancers, decliners)
        and decliners
        and spy <= BROAD_DROP
        and advancers / decliners < BREADTH_RATIO
    ):
        return JUDGMENT_BROAD
    return JUDGMENT_MIXED


def theme_average(returns):
    values = [value for value in returns if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def volume_multiple(today, prior):
    if today is None or prior is None or len(prior) < PRIOR_DAYS:
        return None
    window = prior[-PRIOR_DAYS:]
    average = sum(window) / PRIOR_DAYS
    if not average:
        return None
    return today / average


def level(price, distance_pct):
    if price is None or distance_pct is None:
        return None
    scale = 1 + distance_pct / 100
    if not scale:
        return None
    return price / scale


def take_profit(avg_cost, sell):
    if avg_cost is None or sell is None or sell.get("double_price") is None:
        return None
    return avg_cost * sell["double_price"]


def disaster_line(peak, price, sell):
    if price is None or sell is None or sell.get("disaster_peak_fraction") is None:
        return None
    if peak is None:
        return None
    return max(peak, price) * sell["disaster_peak_fraction"]


def near_disaster(price, line):
    if price is None or line is None or price <= 0:
        return False
    return (price - line) / price < DISASTER_NEAR


def valuation_view(price, neutral):
    if price is None or neutral is None:
        return {"status": MISSING, "neutral": None}
    if neutral == 0 or price == 0 or neutral / price > VALUE_FAR or price / neutral > VALUE_FAR:
        return {"status": "模型不适用", "neutral": None}
    return {"status": "可用", "neutral": neutral}


def valuation_card(range_row, pe, price):
    """Copy payload fields for display. The fair price is never included."""
    payload = {} if range_row is None else _object(range_row.get("payload"))
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    neutral = None if range_row is None else _number(range_row.get("neutral"))
    card = {
        "state": valuation_view(price, neutral)["status"],
        "pe": pe,
        "pe_p25": _number(inputs.get("pe_p25")),
        "pe_p50": _number(inputs.get("pe_p50")),
        "pe_p75": _number(inputs.get("pe_p75")),
        "implied_growth": _number(payload.get("implied_growth")),
        "rev_cagr_3y": _number(inputs.get("rev_cagr_3y")),
        "eps_growth": _number(inputs.get("eps_growth")),
        "implied_reason": None,
        "text": None,
    }
    if card["implied_growth"] is None and payload.get("implied_reason"):
        card["implied_reason"] = str(payload["implied_reason"])
    if range_row is not None and range_row.get("status") == "unvalued":
        reason = payload.get("reason")
        cause = str(reason) if isinstance(reason, str) and reason else MISSING
        card["state"] = "未估值"
        card["text"] = f"未估值（{cause}）"
        for key in ("pe", "pe_p25", "pe_p50", "pe_p75", "implied_growth", "rev_cagr_3y", "eps_growth"):
            card[key] = None
        card["implied_reason"] = None
    return card


def session_gap(start, end):
    """Trading sessions after start, through end."""
    if start is None or end is None or start >= end:
        return 0
    gap = 0
    day = start
    for _ in range(366):
        day = day + timedelta(days=1)
        if trading_day(day):
            gap += 1
        if day >= end:
            break
    return gap


def sell_params(version):
    path = PARAMS_ROOT / version / "m4.yaml"
    loaded = yaml.safe_load(path.read_text())
    return loaded["m4"]["sell"]


def params_version(plan):
    chosen = None if plan is None else plan.get("params_version")
    if chosen and (PARAMS_ROOT / chosen / "m4.yaml").is_file():
        return chosen
    names = sorted(path.name for path in PARAMS_ROOT.iterdir() if (path / "m4.yaml").is_file())
    if not names:
        raise RuntimeError("no m4.yaml parameter directory")
    return names[-1]


def _sectors():
    loaded = yaml.safe_load(UNIVERSE_PATH.read_text())
    grouped = {}
    ordered = []
    for row in loaded["stocks"]:
        grouped.setdefault(row["sector"], []).append(row["ticker"])
        if row["sector"] not in ordered:
            ordered.append(row["sector"])
    return ordered, grouped


def _catalog(connection, grouped):
    rows = _rows(connection, "SELECT basket_id, level, name, members FROM graph.baskets", ())
    items = []
    by_id = {}
    for row in rows:
        members = set(_tickers(row["members"]))
        items.append({"id": row["basket_id"], "level": row["level"], "name": row["name"], "members": members})
        by_id[row["basket_id"]] = row["name"]
    sector_of = {ticker: sector for sector, tickers in grouped.items() for ticker in tickers}
    return {"rows": items, "by_id": by_id, "sectors": grouped, "sector_of": sector_of}


def _by_session(rows, key):
    """Keep close and post apart. Page returns use close only."""
    close, post = {}, {}
    for row in rows:
        name = key(row)
        session = row.get("session")
        if session == "close":
            close[name] = row
        elif session == "post":
            post[name] = row
    return close, post


def half_up(value, digits):
    quant = Decimal("1").scaleb(-digits)
    return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)


def signed_percent(value, *, digits=2):
    """Percent points already scaled. Negative uses the mockup minus sign."""
    if value is None:
        return MISSING
    number = float(value)
    if number < 0:
        body = f"−{abs(number):.{digits}f}"
    elif number > 0:
        body = f"+{number:.{digits}f}"
    else:
        body = f"{number:.{digits}f}"
    return body + "%"


def format_fraction(value):
    if value is None:
        return MISSING
    return signed_percent(value * 100)


def format_points(value):
    if value is None:
        return MISSING
    return signed_percent(value)


def theme_sentence(average, volume, rsi_values):
    """One line for a theme. Thresholds are fractions, same units as market returns."""
    if average is None:
        return f"当日收益{MISSING}。"
    if average <= THEME_SOLD:
        text = "被集中抛售"
        if volume is not None and volume > THEME_VOLUME:
            text += "，放量"
        usable = [value for value in rsi_values if value is not None]
        if usable:
            mean = sum(usable) / len(usable)
            text += f"；RSI 均值 {int(half_up(mean, 0))}"
            if mean < THEME_RSI:
                text += "，已超卖"
        return text
    if average <= THEME_DOWN:
        return "跟随下跌"
    if average > THEME_UP:
        return "资金流入，走强"
    return "平稳"


def human_reason(text):
    """Drop rule ids. Quota and cooldown use the mockup sentences."""
    raw = "" if text is None else str(text)
    if "额度已满" in raw:
        return "该档买入额度已满，暂不加仓"
    if "冷却" in raw:
        return "卖出后冷却期，暂不加仓"
    cleaned = _RULE_ID.sub("", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：;；")
    if cleaned.startswith("待成交"):
        cleaned = cleaned[len("待成交") :].strip(" ：")
    return cleaned


def short_unvalued_text(text):
    """Brief pages show a short Chinese cause. The raw reason stays on the card payload."""
    raw = "" if text is None else str(text)
    prefix = "未估值（"
    if raw.startswith(prefix) and raw.endswith("）"):
        return f"未估值（{_short_reason(raw[len(prefix) : -1])}）"
    if not raw:
        return "未估值"
    return f"未估值（{_short_reason(raw)}）"


def _short_reason(text):
    body = text.strip()
    if not body:
        return "原因待补充"
    folded = body.lower()
    if "周期" in body and ("pe" in folded or "参数" in body):
        return "周期股行业参数缺失"
    if "亏损" in body and "增长" in body:
        return "亏损且无增长"
    if "金融" in body:
        return "金融股不适用"
    if "方法异常" in body or "三档" in body:
        return "估值方法异常"
    if "上市单位" in body:
        return "上市单位未核实"
    if "每股收益" in body or "eps" in folded or "缺少输入" in body:
        return "缺少每股收益数据"
    if ";" in body or "；" in body:
        head = re.split(r"[;；]", body, maxsplit=1)[0].strip()
        if head and head != body:
            return _short_reason(head)
    if re.search(r"[A-Za-z]", body):
        return "原因待补充"
    return body


def _cjk(text):
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def display_name(group_id, catalog):
    if group_id in INDEX_LABELS:
        return INDEX_LABELS[group_id]
    if group_id in STYLE_LABELS:
        return STYLE_LABELS[group_id]
    if group_id in ETF_LABELS:
        return f"{ETF_LABELS[group_id]} {group_id}"
    named = catalog["by_id"].get(group_id)
    if named:
        return named
    if _cjk(group_id) or group_id in catalog["sectors"]:
        return group_id
    return group_id


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _tech(score):
    if score is None:
        return {}
    tech = _object(score.get("tech"))
    return tech if isinstance(tech, dict) else {}


def _state(ledger):
    if ledger is None:
        return {}
    state = _object(ledger.get("state"))
    return state if isinstance(state, dict) else {}


def _positions(state):
    positions = state.get("positions")
    if not isinstance(positions, dict):
        return {}
    return {ticker: item for ticker, item in positions.items() if isinstance(ticker, str) and isinstance(item, dict)}


def _leaders(groups):
    usable = [row for row in groups if row.get("ret") is not None]
    usable.sort(key=lambda row: (row["ret"], row["group_id"]))
    count = 0
    if len(usable) >= 10:
        count = LEADER_COUNT[1]
    elif len(usable) >= 8:
        count = LEADER_COUNT[0]
    elif len(usable) >= 2:
        count = len(usable) // 2
    return usable[:count], list(reversed(usable[-count:])) if count else []


def _named(row, catalog):
    return {
        "id": row["group_id"],
        "kind": row["group_kind"],
        "name": display_name(row["group_id"], catalog),
        "ret": row["ret"],
    }


def _oneliner(down, up, judgment):
    def side(rows, verb):
        if not rows:
            return f"领{verb}{MISSING}"
        shown = "、".join(f"{row['name']}{format_fraction(row['ret'])}" for row in rows[:2])
        return f"{shown}领{verb}"

    return f"{side(down, '跌')}，{side(up, '涨')}，判断：{judgment}。"


def _bars(connection, day, tickers):
    if not tickers:
        return {}
    rows = _rows(
        connection,
        """
        SELECT ticker, trade_date, volume, close
        FROM ingest.bars_daily
        WHERE ticker = ANY(%s) AND trade_date <= %s
        ORDER BY ticker, trade_date
        """,
        (tickers, day),
    )
    grouped = {}
    for row in rows:
        grouped.setdefault(row["ticker"], []).append(row)
    return grouped


def _scores(connection, day):
    rows = _rows(
        connection,
        """
        SELECT ticker, tech, derived, quality, growth, valuation, timing, entry_pass, tier
        FROM trading.daily_scores
        WHERE signal_date = %s
        """,
        (day,),
    )
    return {row["ticker"]: row for row in rows}


def _ranges(connection, day, cutoff):
    rows = _rows(
        connection,
        """
        SELECT ticker, neutral, status, payload
        FROM valuation_v1.ranges
        WHERE trade_date = %s AND observed_at < %s
        """,
        (day, cutoff),
    )
    return {row["ticker"]: row for row in rows}


def _news_seen(connection, cutoff):
    row = _one(
        connection,
        """
        SELECT max(first_seen_at) AS seen
        FROM ingest.info_items
        WHERE kind = 'news' AND first_seen_at < %s
        """,
        (cutoff,),
    )
    if row is None or row["seen"] is None:
        return None
    return _parse_ts(row["seen"])


def _news_fresh(seen, day):
    if seen is None:
        return False
    return session_gap(seen.astimezone(NY).date(), day) <= NEWS_GAP


def _beijing_text(value):
    moment = value if isinstance(value, datetime) else _parse_ts(value)
    if moment is None:
        return MISSING
    return moment.astimezone(_SHANGHAI).strftime("%Y-%m-%d %H:%M")


def _day_window(day):
    start = datetime.combine(day, time(4, 0), tzinfo=NY)
    return start, start + timedelta(days=1)


def citation_stale_note(cited, trade_date):
    """More than three calendar days before the trade date, in New York."""
    moment = _parse_ts(cited)
    if moment is None or trade_date is None:
        return None
    gap = (trade_date - moment.astimezone(NY).date()).days
    if gap > STALE_NEWS_DAYS:
        return f"引用的是 {gap} 天前的新闻"
    return None


def _news_summary(source, headline):
    card = source.get("news_card") if isinstance(source, dict) else None
    said = card.get("说了什么") if isinstance(card, dict) else None
    if isinstance(said, str) and said.strip():
        return said.strip()
    if isinstance(headline, str) and headline.strip():
        return headline.strip()
    return MISSING


def _day_news(connection, day, cutoff):
    """News published in the ET session and already stored at the cutoff."""
    start, end = _day_window(day)
    rows = _rows(
        connection,
        """
        SELECT info_id, published_at, source, headline, tickers, extraction_source
        FROM ingest.info_items
        WHERE kind = 'news' AND first_seen_at <= %s AND published_at >= %s AND published_at < %s
        ORDER BY published_at DESC, info_id
        """,
        (cutoff, start, end),
    )
    items = []
    for row in rows:
        published = _parse_ts(row["published_at"])
        items.append(
            {
                "info_id": row["info_id"],
                "summary": _news_summary(_object(row["extraction_source"]), row["headline"]),
                "source": row["source"] or MISSING,
                "published_at": None if published is None else published.isoformat(),
                "published_beijing": _beijing_text(published),
                "tickers": [name for name in (row["tickers"] or []) if isinstance(name, str)],
            }
        )
    return items


def _wide_stocks(connection, day):
    """Ordinary names in the latest M1 wide set on or before this trade date."""
    rows = _rows(
        connection,
        """
        SELECT ticker
        FROM ingest.wide_universe
        WHERE trade_date = (SELECT max(trade_date) FROM ingest.wide_universe WHERE trade_date <= %s)
          AND included
          AND exclude_reason IS DISTINCT FROM 'non_common'
        """,
        (day,),
    )
    return {row["ticker"] for row in rows}


def _stock_names(pool, wide):
    return set(pool) | set(wide)


def event_has_stock(names, pool, wide):
    """A stock event has a universe name or an M1 ordinary share. ETFs and style ids do not."""
    stocks = _stock_names(pool, wide)
    return any(name in stocks for name in names)


def _move_reasons(report):
    card = report.get("move_card") if isinstance(report, dict) else None
    if not isinstance(card, dict):
        return []
    found = []
    for item in card.get("解释") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("怎么影响") or item.get("一句话")
        if not text:
            continue
        cited = item.get("发布时间")
        found.append({"text": str(text), "cited_at": None if cited is None else str(cited)})
    return found


def _daily_reasons(report):
    text = report.get("daily_text") if isinstance(report, dict) else None
    if not isinstance(text, str):
        return []
    found = []
    for line in text.splitlines():
        if "可能的原因" not in line and "可能原因" not in line:
            continue
        if "没找到" in line:
            continue
        match = _ISO_TS.search(line)
        cited = None if match is None else match.group(0)
        body = line.split("：", 1)[-1].strip() if "：" in line else line.strip()
        if cited:
            body = body.replace(cited, "").strip()
        if body:
            found.append({"text": body, "cited_at": cited})
    return found


def event_reasons(report, trade_date):
    """At most two causes, from the move card when it has any, otherwise the morning page."""
    chosen = _move_reasons(report) or _daily_reasons(report)
    reasons = []
    for item in chosen[:2]:
        reasons.append({**item, "stale_note": citation_stale_note(item.get("cited_at"), trade_date)})
    return reasons


def _session_closes(history, day):
    today = [row["close"] for row in history if row["trade_date"] == day and row["close"] is not None]
    prior = [row["close"] for row in history if row["trade_date"] < day and row["close"] is not None]
    if not today or not prior:
        return None, None
    return float(today[-1]), float(prior[-1])


def close_estimate(context, day):
    """Mark the book to that day's close. Incomplete prices stay on the ledger."""
    ledger = context["ledger"]
    cash = None if ledger is None else _number(ledger.get("cash"))
    positions = context["positions"]
    if cash is None or not positions:
        return None
    equity = cash
    pnl = 0.0
    for ticker, position in positions.items():
        shares = _number(position.get("shares"))
        close, previous = _session_closes(context["bars"].get(ticker) or [], day)
        if shares is None or close is None or previous is None:
            return None
        equity += shares * close
        pnl += shares * (close - previous)
    return {"equity": equity, "day_pnl": pnl, "label": f"按 {day.month}月{day.day}日 收盘估算"}


def _book(connection, day, cutoff):
    return _one(
        connection,
        """
        SELECT portfolio_id, cash, equity, peak_equity, state, observed_at
        FROM trading.ledger
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        (day, cutoff),
    )


def _pending(connection, day, portfolio):
    if not portfolio:
        return []
    return _rows(
        connection,
        """
        SELECT order_id, ticker, side, kind, status, reason_zh, trade_date, signal_date
        FROM trading.orders
        WHERE portfolio_id = %s AND status = 'pending' AND trade_date <= %s
        ORDER BY order_id
        """,
        (portfolio, day),
    )


def _plans(connection, day, cutoff, portfolio):
    if not portfolio:
        return []
    return _rows(
        connection,
        """
        SELECT trade_date, payload, params_version
        FROM trading.plan
        WHERE portfolio_id = %s AND trade_date <= %s AND generated_at < %s
        ORDER BY trade_date, generated_at
        """,
        (portfolio, day, cutoff),
    )


def _previous_equity(connection, day, cutoff, portfolio):
    if not portfolio:
        return None
    row = _one(
        connection,
        """
        SELECT equity
        FROM trading.ledger
        WHERE portfolio_id = %s AND trade_date < %s AND observed_at < %s AND equity IS NOT NULL
        ORDER BY trade_date DESC, observed_at DESC
        LIMIT 1
        """,
        (portfolio, day, cutoff),
    )
    return None if row is None else row["equity"]


def _previous_vix3m(connection, day):
    row = _one(
        connection,
        """
        SELECT vix3m
        FROM marketstate.market
        WHERE trade_date < %s
        ORDER BY trade_date DESC
        LIMIT 1
        """,
        (day,),
    )
    return None if row is None else row["vix3m"]


def _reports(connection, ids):
    if not ids:
        return {}
    rows = _rows(
        connection,
        "SELECT anomaly_id, report FROM perception.reports WHERE anomaly_id = ANY(%s)",
        (ids,),
    )
    return {row["anomaly_id"]: _object(row["report"]) for row in rows}


def _labels(connection, day, cutoff):
    return _rows(
        connection,
        """
        SELECT case_id, horizon, as_of, reason, labels
        FROM perception.case_labels
        WHERE as_of = %s AND written_at < %s
        ORDER BY case_id, horizon
        """,
        (day, cutoff),
    )


def _overlay_present(connection, day, cutoff):
    row = _one(
        connection,
        """
        SELECT version FROM overlay.versions
        WHERE date = %s AND generated_at < %s
        LIMIT 1
        """,
        (day, cutoff),
    )
    return row is not None


def _price(tech, bars):
    price = _number(tech.get("price"))
    if price is not None:
        return price
    if bars and bars[-1]["close"] is not None:
        return float(bars[-1]["close"])
    return None


def _derived_pe(score):
    if score is None:
        return None
    return _number(_object(score.get("derived")).get("pe"))


def _card_for(context, ticker, score, price):
    return valuation_card(context["ranges"].get(ticker), _derived_pe(score), price)


def _books(score):
    if score is None:
        return None
    return {
        "quality": score["quality"],
        "growth": score["growth"],
        "valuation": score["valuation"],
        "timing": score["timing"],
    }


def _explanation(report, trade_date):
    reasons = event_reasons(report, trade_date)
    if not reasons:
        return None, None, []
    cited = next((item["cited_at"] for item in reasons if item.get("cited_at")), None)
    return "；".join(item["text"] for item in reasons) or None, cited, reasons


def _sell_history(plans, state):
    found = []
    for plan in plans:
        payload = _object(plan["payload"])
        for order in payload.get("orders") or []:
            if isinstance(order, dict) and order.get("side") == "sell":
                found.append(
                    {
                        "ticker": order.get("ticker"),
                        "trade_date": plan["trade_date"],
                        "kind": order.get("kind"),
                        "reason_zh": order.get("reason_zh"),
                        "source": "plan",
                    }
                )
    for item in state.get("exits") or []:
        if isinstance(item, dict):
            found.append(
                {
                    "ticker": item.get("ticker"),
                    "trade_date": item.get("trade_date") or item.get("day"),
                    "kind": item.get("kind") or "exit",
                    "reason_zh": item.get("reason") or item.get("reason_zh"),
                    "source": "exits",
                }
            )
    return found


def _pending_line(order):
    label = human_reason(order.get("reason_zh")) or "订单"
    start = order.get("signal_date") or order.get("trade_date") or MISSING
    return f"待成交：{label}（{start} 起）"


def _next_step(ticker, pending, plan_payload):
    for order in pending:
        if order["ticker"] == ticker:
            return _pending_line(order)
    payload = plan_payload if isinstance(plan_payload, dict) else {}
    for order in payload.get("orders") or []:
        if isinstance(order, dict) and order.get("ticker") == ticker and order.get("reason_zh"):
            return human_reason(order.get("reason_zh")) or "继续持有"
    for skip in payload.get("skips") or []:
        if isinstance(skip, dict) and skip.get("ticker") == ticker and skip.get("reason_zh"):
            return human_reason(skip.get("reason_zh")) or "继续持有"
    return "继续持有"


def _style_only(baskets):
    names = [str(item) for item in baskets if item]
    return bool(names) and all(item in STYLE_LABELS for item in names)


def _visible_anomalies(anomalies, stocks):
    chosen = []
    for row in anomalies:
        if row["universe"] != "pool":
            continue
        if _style_only(row["baskets"] or []):
            continue
        names = _tickers(row["members"])
        if not event_has_stock(names, stocks, ()):
            continue
        chosen.append(row)
    return chosen


def _event_title(baskets, tickers, direction, catalog):
    real = [str(item) for item in baskets if item and str(item) not in STYLE_LABELS]
    count = len(tickers)
    down = direction not in {"up", "上涨"}
    if len(real) <= 1:
        name = display_name(real[0], catalog) if real else "、".join(tickers[:4])
        verb = "集体下跌" if down else "集体上涨"
        return f"{name} {count} 只{verb}"
    name = _covering_theme(tickers, catalog) or (display_name(real[0], catalog) if real else "、".join(tickers[:4]))
    verb = "同日下跌" if down else "同日上涨"
    return f"{name} {count} 只{verb}"


def _covering_theme(tickers, catalog):
    wanted = set(tickers)
    best = None
    for item in catalog["rows"]:
        covered = len(item["members"] & wanted)
        if not covered:
            continue
        level = 1 if item["level"] == "L2" else 0
        rank = (covered, level)
        if best is None or rank > best[0]:
            best = (rank, item["name"])
    for sector, members in catalog["sectors"].items():
        covered = len(set(members) & wanted)
        rank = (covered, 1)
        if covered and (best is None or rank > best[0]):
            best = (rank, sector)
    if best is None:
        return None
    return best[1]


def _event_rows(anomalies, events, reports, fresh, catalog, stocks, day):
    pool = _visible_anomalies(anomalies, stocks)
    pool.sort(key=lambda row: (-(row["max_abs_z"] or -1), row["anomaly_id"]))
    chosen = []
    for row in pool[:3]:
        view = events.get(row["anomaly_id"])
        explanation, cited, reasons = _explanation(reports.get(row["anomaly_id"]), day)
        names = _tickers(row["members"])
        baskets = list(row["baskets"] or [])
        chosen.append(
            {
                "anomaly_id": row["anomaly_id"],
                "event_id": None if view is None else view["event_id"],
                "max_abs_z": row["max_abs_z"],
                "direction": row["direction"],
                "title": _event_title(baskets, names, row["direction"], catalog),
                "members": names,
                "explanation": explanation,
                "cited_at": cited,
                "reasons": reasons,
                "untrusted": not fresh,
            }
        )
    return chosen


def _member_events(anomalies, catalog, stocks):
    membership = {}
    for row in _visible_anomalies(anomalies, stocks):
        names = _tickers(row["members"])
        title = _event_title(list(row["baskets"] or []), names, row["direction"], catalog)
        for name in names:
            membership.setdefault(name, []).append(title)
    return membership


def _statuses(fresh, vix, overlay, pending_late, plan, valuation_status):
    return [
        {"item": "新闻", "state": "新鲜" if fresh else "缺失"},
        {"item": "VIX", "state": "已有" if vix is not None else MISSING},
        {"item": "M9", "state": "已上线" if overlay else "未上线/缺失"},
        {"item": "估值", "state": valuation_status},
        {"item": "订单", "state": "警示" if pending_late else "正常"},
        {"item": "计划", "state": "已有" if plan is not None else "警示"},
    ]


def _valuation_status(scores, ranges, bars):
    states = []
    for ticker, score in scores.items():
        tech = _tech(score)
        neutral = None if ticker not in ranges else ranges[ticker]["neutral"]
        view = valuation_view(_price(tech, bars.get(ticker)), neutral)
        states.append(view["status"])
    if "模型不适用" in states:
        return "模型不适用"
    if "可用" in states and MISSING not in states:
        return "可用"
    if "可用" in states:
        return "可用"
    return MISSING


def _context(connection, day, clock):
    cutoff, closed = _open(clock, day)
    if closed is not None:
        return None, closed
    pool, _etfs = _universe()
    order, grouped = _sectors()
    daily, _daily_post = _by_session(
        _rows(
            connection,
            """
            SELECT ticker, session, ret
            FROM marketstate.daily
            WHERE trade_date = %s
            """,
            (day,),
        ),
        lambda row: row["ticker"],
    )
    rotation_close, rotation_post = _by_session(
        _rows(
            connection,
            """
            SELECT group_kind, group_id, session, ret
            FROM marketstate.rotation
            WHERE trade_date = %s AND group_kind = ANY(%s)
            """,
            (day, ["index", "style", "sector", "l3"]),
        ),
        lambda row: (row["group_kind"], row["group_id"]),
    )
    rotation = list(rotation_close.values())
    market = _one(connection, "SELECT * FROM marketstate.market WHERE trade_date = %s", (day,))
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    scores = _scores(connection, day)
    ranges = _ranges(connection, day, cutoff)
    ledger = _book(connection, day, cutoff)
    portfolio = None if ledger is None else ledger["portfolio_id"]
    state = _state(ledger)
    positions = _positions(state)
    bars = _bars(connection, day, list(dict.fromkeys([*pool, *positions])))
    plan = _plan(connection, day, cutoff)
    if portfolio is None and plan is not None:
        owner = _one(
            connection,
            """
            SELECT portfolio_id FROM trading.plan
            WHERE trade_date = %s AND generated_at < %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (day, cutoff),
        )
        portfolio = None if owner is None else owner["portfolio_id"]
    plans = _plans(connection, day, cutoff, portfolio)
    pending = _pending(connection, day, portfolio)
    context_portfolio = portfolio
    seen = _news_seen(connection, cutoff)
    fresh = _news_fresh(seen, day)
    news_items = _day_news(connection, day, cutoff)
    version = params_version(plan)
    sell = sell_params(version)
    return {
        "cutoff": cutoff,
        "pool": pool,
        "order": order,
        "grouped": grouped,
        "daily": daily,
        "rotation": rotation,
        "rotation_post": rotation_post,
        "catalog": _catalog(connection, grouped),
        "market": market,
        "anomalies": anomalies,
        "events": events,
        "scores": scores,
        "bars": bars,
        "ranges": ranges,
        "stocks": _stock_names(pool, _wide_stocks(connection, day)),
        "news_items": news_items,
        "news_seen": seen,
        "news_day_count": len(news_items),
        "ledger": ledger,
        "state": state,
        "positions": positions,
        "plans": plans,
        "plan": plan,
        "pending": pending,
        "portfolio": context_portfolio,
        "fresh": fresh,
        "version": version,
        "sell": sell,
    }, None


def _index_ret(rotation, name):
    for row in rotation:
        if row["group_kind"] == "index" and row["group_id"] == name:
            return row["ret"]
    return None


def _post_ret(context, name):
    row = context["rotation_post"].get(("index", name))
    return None if row is None else row["ret"]


def _implication(context, down_count, wide_count):
    pool = context["pool"]
    sector_of = context["catalog"]["sector_of"]
    ai_names = [ticker for ticker in pool if sector_of.get(ticker) in AI_SECTORS]
    heavy = bool(pool) and len(ai_names) >= len(pool) / 3
    lead = "我的标的池偏重 AI 链，" if heavy else ""
    base = f"{lead}今天 {len(pool)} 只里 {down_count} 只下跌、{wide_count} 只波动超过 7%"
    return f"{base}；{_holdings_clause(context, sector_of)}详见「我的标的」「纸面账户」。"


def _holdings_clause(context, sector_of):
    positions = context["positions"]
    equity = None if context["ledger"] is None else _number(context["ledger"].get("equity"))
    ai_held = [ticker for ticker in positions if sector_of.get(ticker) in AI_SECTORS]
    valued = equity not in (None, 0) and bool(ai_held)
    ai_value = 0.0
    for ticker in ai_held:
        price = _ticker_price(context, ticker)
        shares = _number(positions[ticker].get("shares"))
        if price is None or shares is None:
            valued = False
            break
        ai_value += price * shares
    if valued:
        shown = int(half_up(ai_value / equity * 100, 0))
        return f"纸面账户 AI 持仓占 {shown}%，"
    if ai_held:
        fallen = 0
        for ticker in ai_held:
            row = context["daily"].get(ticker)
            ret = None if row is None else row["ret"]
            if ret is not None and ret < 0:
                fallen += 1
        return f"纸面账户 AI 持仓有 {len(ai_held)} 只、当日下跌 {fallen} 只，"
    fallen = 0
    for ticker in positions:
        row = context["daily"].get(ticker)
        ret = None if row is None else row["ret"]
        if ret is not None and ret < 0:
            fallen += 1
    if positions:
        return f"纸面账户持仓里当日下跌 {fallen} 只，"
    return "纸面账户当日没有持仓，"


def _ticker_price(context, ticker):
    score = context["scores"].get(ticker)
    history = context["bars"].get(ticker) or []
    return _price(_tech(score), history)


def _breadth(daily):
    advancers = decliners = 0
    for row in daily.values():
        ret = row["ret"]
        if ret is None:
            continue
        if ret > 0:
            advancers += 1
        elif ret < 0:
            decliners += 1
    return advancers, decliners


def _member(ticker, day, bars, score, daily, held, events_for):
    """Volume multiple uses bars on the page day and the 20 sessions before it."""
    tech = _tech(score)
    history = bars.get(ticker) or []
    today_rows = [row for row in history if row["trade_date"] == day]
    prior_rows = [row for row in history if row["trade_date"] < day and row["volume"] is not None]
    today_volume = None if not today_rows else today_rows[-1]["volume"]
    return {
        "ticker": ticker,
        "ret": None if ticker not in daily else daily[ticker]["ret"],
        "volume_multiple": volume_multiple(today_volume, [row["volume"] for row in prior_rows]),
        "rsi": _number(tech.get("rsi")),
        "price_vs_ma200": _number(tech.get("price_vs_ma200")),
        "drawdown252": _number(tech.get("drawdown252")),
        "dev50": _number(tech.get("dev50")),
        "price": _price(tech, today_rows or history),
        "held": held,
        "entry_pass": None if score is None else bool(score["entry_pass"]),
        "tier": None if score is None else score.get("tier"),
        "events": events_for,
        "books": _books(score),
    }


def _themes(context, day):
    daily = context["daily"]
    scores = context["scores"]
    bars = context["bars"]
    positions = context["positions"]
    membership = _member_events(context["anomalies"], context["catalog"], context["stocks"])
    news_items = context["news_items"]
    themes = []
    for sector in context["order"]:
        members = []
        for ticker in context["grouped"][sector]:
            score = scores.get(ticker)
            member = _member(ticker, day, bars, score, daily, ticker in positions, membership.get(ticker, []))
            matched = [item for item in news_items if ticker in item["tickers"]]
            member["news_count"] = len(matched)
            member["news"] = matched[:3]
            member["valuation"] = _card_for(context, ticker, score, member["price"])
            members.append(member)
        average = theme_average([row["ret"] for row in members])
        themes.append(
            {
                "sector": sector,
                "average": average,
                "volume_multiple": theme_average([row["volume_multiple"] for row in members]),
                "held_count": sum(1 for row in members if row["held"]),
                "buyable_count": sum(1 for row in members if row["entry_pass"] is True and not row["held"]),
                "news_count": sum(row["news_count"] for row in members),
                "members": members,
                "line": _theme_line(sector, average, members),
            }
        )
    known = [row for row in themes if row["average"] is not None]
    missing = [row for row in themes if row["average"] is None]
    known.sort(key=lambda row: (row["average"], row["sector"]))
    ordered = known + missing
    if ordered and ordered[0]["average"] is not None:
        ordered[0]["open"] = True
    for row in ordered[1:]:
        row["open"] = False
    if ordered and ordered[0]["average"] is None:
        ordered[0]["open"] = False
    return ordered


def _theme_line(_sector, average, members):
    volume = theme_average([row["volume_multiple"] for row in members])
    return theme_sentence(average, volume, [row["rsi"] for row in members])


def _holding_row(ticker, position, stock, sell, pending, plan_payload, valuation):
    price = stock["price"]
    avg_cost = _number(position.get("avg_cost"))
    peak = _number(position.get("peak_price"))
    line = disaster_line(peak, price, sell)
    tier = position.get("tier_now") or stock.get("tier")
    days = None if sell is None or tier is None else (sell.get("below_days") or {}).get(tier)
    pnl = None if price is None or avg_cost in (None, 0) else price / avg_cost - 1
    return {
        "ticker": ticker,
        "shares": position.get("shares"),
        "avg_cost": avg_cost,
        "peak_price": peak,
        "price": price,
        "pnl": pnl,
        "take_profit": take_profit(avg_cost, sell),
        "ma200": level(price, stock["price_vs_ma200"]),
        "disaster": line,
        "below_days": days,
        "near_disaster": near_disaster(price, line),
        "next_step": _next_step(ticker, pending, plan_payload),
        "pending": [row["order_id"] for row in pending if row["ticker"] == ticker],
        "books": stock["books"],
        "valuation": valuation,
    }


def _candidate_row(stock, valuation):
    price = stock["price"]
    return {
        "ticker": stock["ticker"],
        "books": stock["books"],
        "entry_pass": stock["entry_pass"],
        "ma50": level(price, stock["dev50"]),
        "year_high": level(price, stock["drawdown252"]),
        "dev50": stock["dev50"],
        "drawdown252": stock["drawdown252"],
        "price": price,
        "valuation": valuation,
        "view": "符合买入条件，尚未持有。四本账、RSI 与偏离度取自当日打分。",
    }


def page_brief_market(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    rotation = context["rotation"]
    catalog = context["catalog"]
    spy, qqq, iwm = (_index_ret(rotation, name) for name in ("SPY", "QQQ", "IWM"))
    advancers, decliners = _breadth(context["daily"])
    judgment = judge(spy, qqq, iwm, advancers, decliners)
    groups = [row for row in rotation if row["group_kind"] in {"l3", "sector"}]
    down, up = _leaders(groups)
    down, up = [_named(row, catalog) for row in down], [_named(row, catalog) for row in up]
    styles = []
    by_style = {row["group_id"]: row for row in rotation if row["group_kind"] == "style"}
    for key, label in STYLE_LABELS.items():
        row = by_style.get(key)
        styles.append({"id": key, "name": label, "ret": None if row is None else row["ret"]})
    market = context["market"]
    vix = None if market is None else market["vix"]
    reports = _reports(connection, [row["anomaly_id"] for row in context["anomalies"]])
    events = _event_rows(
        context["anomalies"], context["events"], reports, context["fresh"], catalog, context["stocks"], day
    )
    pool_returns = [context["daily"][ticker]["ret"] for ticker in context["pool"] if ticker in context["daily"]]
    down_count = sum(1 for value in pool_returns if value is not None and value < 0)
    wide_count = sum(1 for value in pool_returns if value is not None and abs(value) >= MOVE_BAND)
    implication = _implication(context, down_count, wide_count)
    shock = False if market is None else bool(market["shock_flag"])
    if shock:
        mood = "情绪：冲击"
    elif vix is None:
        mood = "情绪：谨慎，未恐慌"
    elif vix >= 30:
        mood = "情绪：恐慌"
    else:
        mood = "情绪：谨慎，未恐慌"
    fallen = "、".join(row["name"] for row in down[:2])
    risen = "、".join(row["name"] for row in up[:2])
    funds = f"资金：{fallen}领跌，{risen}领涨"
    if not down or not up:
        funds = "资金：领跌或领涨" + MISSING
    return {
        "page": "/",
        "date": day,
        "title": "市场总览",
        "oneliner": _oneliner(down, up, judgment),
        "judgment": judgment,
        "headings": ["市场总览", funds, mood, "今天的大事"],
        "indexes": [
            {"id": "SPY", "name": INDEX_LABELS["SPY"], "ret": spy, "post": _post_ret(context, "SPY")},
            {"id": "QQQ", "name": INDEX_LABELS["QQQ"], "ret": qqq, "post": _post_ret(context, "QQQ")},
            {"id": "IWM", "name": INDEX_LABELS["IWM"], "ret": iwm, "post": _post_ret(context, "IWM")},
        ],
        "advancers": advancers,
        "decliners": decliners,
        "leaders_down": down,
        "leaders_up": up,
        "styles": styles,
        "sector_spread_z": None if market is None else market["sector_spread_z"],
        "vix": vix,
        "vix3m": None if market is None else market["vix3m"],
        "vix3m_prev": _previous_vix3m(connection, day),
        "down_share_5d_pct": None if market is None else market["down_share_5d_pct"],
        "spy_drawdown_252_pct": None if market is None else market["spy_drawdown_252_pct"],
        "events": events,
        "news_fresh": context["fresh"],
        "implication": implication,
        "pool_count": len(context["pool"]),
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }


def page_brief_stocks(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    themes = _themes(context, day)
    worst = next((row for row in themes if row["average"] is not None), None)
    if worst is None:
        sentence = f"主题收益{MISSING}。"
    else:
        sentence = f"跌幅最大的主题是{worst['sector']}，平均{format_fraction(worst['average'])}。"
    return {
        "page": "/stocks",
        "date": day,
        "title": "我的标的",
        "oneliner": sentence,
        "headings": ["我的标的", "主题一览（按今日表现排序）", "逐只明细"],
        "themes": themes,
        "pool_count": len(context["pool"]),
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }


def page_brief_account(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    themes = {row["ticker"]: row for theme in _themes(context, day) for row in theme["members"]}
    plan_payload = _object(context["plan"]["payload"]) if context["plan"] else {}
    holdings = []
    for ticker, position in sorted(context["positions"].items()):
        stock = themes.get(ticker) or _member(
            ticker, day, context["bars"], context["scores"].get(ticker), context["daily"], True, []
        )
        if "valuation" not in stock:
            stock["valuation"] = _card_for(context, ticker, context["scores"].get(ticker), stock["price"])
        holdings.append(
            _holding_row(ticker, position, stock, context["sell"], context["pending"], plan_payload, stock["valuation"])
        )
    held = set(context["positions"])
    candidates = []
    for ticker, score in sorted(context["scores"].items()):
        if ticker in held or not score["entry_pass"] or ticker not in set(context["pool"]):
            continue
        stock = themes.get(ticker) or _member(ticker, day, context["bars"], score, context["daily"], False, [])
        if "valuation" not in stock:
            stock["valuation"] = _card_for(context, ticker, score, stock["price"])
        candidates.append(_candidate_row(stock, stock["valuation"]))
    ledger = context["ledger"]
    equity = None if ledger is None else ledger["equity"]
    cash = None if ledger is None else ledger["cash"]
    peak = None if ledger is None else ledger["peak_equity"]
    previous = _previous_equity(connection, day, context["cutoff"], context["portfolio"])
    day_change = None if equity is None or previous in (None, 0) else equity / previous - 1
    drawdown = None if equity is None or peak in (None, 0) else equity / peak - 1
    estimate = close_estimate(context, day)
    near = sum(1 for row in holdings if row["near_disaster"])
    pending_rows = sum(1 for row in holdings if str(row["next_step"]).startswith("待成交"))
    sentence = f"持仓{len(holdings)}只，距灾难线过近{near}只，待成交{pending_rows}笔。"
    return {
        "page": "/account",
        "date": day,
        "title": "纸面账户",
        "oneliner": sentence,
        "headings": ["纸面账户", "持仓与关键价位", "已止盈 / 止损 / 清仓", "待选：符合买入条件但还没买的"],
        "equity": equity,
        "cash": cash,
        "peak_equity": peak,
        "day_change": day_change,
        "drawdown": drawdown,
        "close_estimate": estimate,
        "holdings": holdings,
        "closed_records": _sell_history(context["plans"], context["state"]),
        "candidates": candidates,
        "params_version": context["version"],
        "sell": {
            "double_price": context["sell"]["double_price"],
            "disaster_peak_fraction": context["sell"]["disaster_peak_fraction"],
            "below_days": dict(context["sell"]["below_days"]),
        },
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }


def page_brief_trust(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    market = context["market"]
    vix = None if market is None else market["vix"]
    late = any(session_gap(row["trade_date"], day) > PENDING_GAP for row in context["pending"])
    valuation_state = _valuation_status(context["scores"], context["ranges"], context["bars"])
    statuses = _statuses(
        context["fresh"],
        vix,
        _overlay_present(connection, day, context["cutoff"]),
        late,
        context["plan"],
        valuation_state,
    )
    labels = []
    for row in _labels(connection, day, context["cutoff"]):
        labels.append(
            {
                "case_id": row["case_id"],
                "horizon": row["horizon"],
                "as_of": row["as_of"],
                "reason": row["reason"],
                "labels": _object(row["labels"]),
            }
        )
    if any(item["state"] in {"缺失", "警示", MISSING, "未上线/缺失", "模型不适用"} for item in statuses):
        sentence = "数据状态有缺口，下面逐项是查询结果。"
    else:
        sentence = "列出的数据状态均已接通。"
    return {
        "page": "/trust",
        "date": day,
        "title": "复盘与数据",
        "oneliner": sentence,
        "headings": ["复盘与数据", "数据状态", "系统之前说的对不对（复盘）"],
        "statuses": statuses,
        "news_seen_beijing": _beijing_text(context["news_seen"]),
        "news_day_count": context["news_day_count"],
        "labels": labels,
        "review_gap": None if labels else "尚无 T+1/T+5/T+20 打标记录",
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }
