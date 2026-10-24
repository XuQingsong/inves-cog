"""Investor brief pages. Simple derived values live only in this module."""

from datetime import timedelta
from pathlib import Path

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
PENDING_GAP = 2
PRIOR_DAYS = 20
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
FORMULAS = (
    "主题平均涨跌 = 该主题有收益的成员当日收益算术平均。",
    "成交量倍数 = 当日成交量 / 前20日均量。",
    "止盈线 = 成本 × m4.sell.double_price。",
    "灾难止损线 = max(峰值, 现价) × m4.sell.disaster_peak_fraction。",
    "200日线 = 现价 / (1 + price_vs_ma200/100)。",
    "50日线 = 现价 / (1 + dev50/100)。",
    "一年高点 = 现价 / (1 + drawdown252/100)。",
    "轮动：IWM减QQQ大于2个百分点，且上涨家数大于下跌家数。",
    "普跌：SPY小于等于-2%，且上涨家数/下跌家数小于0.5。",
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


def _prefer(rows, key):
    chosen = {}
    for row in rows:
        name = key(row)
        current = chosen.get(name)
        if current is None or (row.get("session") == "post" and current.get("session") != "post"):
            chosen[name] = row
    return chosen


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


def _named(row):
    return {
        "id": row["group_id"],
        "kind": row["group_kind"],
        "name": INDEX_LABELS.get(row["group_id"], STYLE_LABELS.get(row["group_id"], row["group_id"])),
        "ret": row["ret"],
    }


def _oneliner(down, up, judgment):
    def side(rows, verb):
        if not rows:
            return f"领{verb}{MISSING}"
        shown = "、".join(f"{row['name']}{row['ret'] * 100:.2f}%" for row in rows[:2])
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
        SELECT ticker, tech, quality, growth, valuation, timing, entry_pass, tier
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
        SELECT ticker, neutral, status
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
        WHERE as_of <= %s AND written_at < %s
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


def _books(score):
    if score is None:
        return None
    return {
        "quality": score["quality"],
        "growth": score["growth"],
        "valuation": score["valuation"],
        "timing": score["timing"],
    }


def _explanation(report):
    card = report.get("move_card") if isinstance(report, dict) else None
    if not isinstance(card, dict):
        return None, None
    lines = []
    cited = None
    for item in card.get("解释") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("怎么影响")
        if text:
            lines.append(str(text))
        if cited is None and item.get("发布时间"):
            cited = str(item["发布时间"])
    if not lines and cited is None:
        return None, None
    return "；".join(lines) or None, cited


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


def _next_step(ticker, pending, plan_payload):
    for order in pending:
        if order["ticker"] == ticker and order.get("reason_zh"):
            return order["reason_zh"]
    payload = plan_payload if isinstance(plan_payload, dict) else {}
    for order in payload.get("orders") or []:
        if isinstance(order, dict) and order.get("ticker") == ticker and order.get("reason_zh"):
            return order["reason_zh"]
    for skip in payload.get("skips") or []:
        if isinstance(skip, dict) and skip.get("ticker") == ticker and skip.get("reason_zh"):
            return skip["reason_zh"]
    return "继续持有"


def _event_rows(anomalies, events, reports, fresh):
    pool = [row for row in anomalies if row["universe"] == "pool"]
    pool.sort(key=lambda row: (-(row["max_abs_z"] or -1), row["anomaly_id"]))
    chosen = []
    for row in pool[:3]:
        view = events.get(row["anomaly_id"])
        explanation, cited = _explanation(reports.get(row["anomaly_id"]))
        names = _tickers(row["members"])
        baskets = list(row["baskets"] or [])
        title = (baskets[0] if baskets else "、".join(names[:4])) + f" {len(names)}只"
        chosen.append(
            {
                "anomaly_id": row["anomaly_id"],
                "event_id": None if view is None else view["event_id"],
                "max_abs_z": row["max_abs_z"],
                "direction": row["direction"],
                "title": title,
                "members": names,
                "explanation": explanation,
                "cited_at": cited,
                "untrusted": not fresh,
            }
        )
    return chosen


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
    daily = _prefer(
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
    rotation = list(
        _prefer(
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
        ).values()
    )
    market = _one(connection, "SELECT * FROM marketstate.market WHERE trade_date = %s", (day,))
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    scores = _scores(connection, day)
    bars = _bars(connection, day, pool)
    ranges = _ranges(connection, day, cutoff)
    ledger = _book(connection, day, cutoff)
    portfolio = None if ledger is None else ledger["portfolio_id"]
    state = _state(ledger)
    positions = _positions(state)
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
    version = params_version(plan)
    sell = sell_params(version)
    return {
        "cutoff": cutoff,
        "pool": pool,
        "order": order,
        "grouped": grouped,
        "daily": daily,
        "rotation": rotation,
        "market": market,
        "anomalies": anomalies,
        "events": events,
        "scores": scores,
        "bars": bars,
        "ranges": ranges,
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
    anomalies = context["anomalies"]
    membership = {}
    for anomaly in anomalies:
        if anomaly["universe"] != "pool":
            continue
        for name in _tickers(anomaly["members"]):
            membership.setdefault(name, []).append(anomaly["anomaly_id"])
    themes = []
    for sector in context["order"]:
        members = []
        for ticker in context["grouped"][sector]:
            members.append(
                _member(ticker, day, bars, scores.get(ticker), daily, ticker in positions, membership.get(ticker, []))
            )
        average = theme_average([row["ret"] for row in members])
        themes.append(
            {
                "sector": sector,
                "average": average,
                "volume_multiple": theme_average([row["volume_multiple"] for row in members]),
                "held_count": sum(1 for row in members if row["held"]),
                "buyable_count": sum(1 for row in members if row["entry_pass"] is True),
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


def _theme_line(sector, average, members):
    if average is None:
        return f"{sector}当日收益{MISSING}。"
    held = sum(1 for row in members if row["held"])
    buyable = sum(1 for row in members if row["entry_pass"] is True)
    return f"{sector}平均{average * 100:.2f}%，持有{held}，可买{buyable}。"


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
    spy, qqq, iwm = (_index_ret(rotation, name) for name in ("SPY", "QQQ", "IWM"))
    advancers, decliners = _breadth(context["daily"])
    judgment = judge(spy, qqq, iwm, advancers, decliners)
    groups = [row for row in rotation if row["group_kind"] in {"l3", "sector"}]
    down, up = _leaders(groups)
    down, up = [_named(row) for row in down], [_named(row) for row in up]
    styles = []
    by_style = {row["group_id"]: row for row in rotation if row["group_kind"] == "style"}
    for key, label in STYLE_LABELS.items():
        row = by_style.get(key)
        styles.append({"id": key, "name": label, "ret": None if row is None else row["ret"]})
    market = context["market"]
    vix = None if market is None else market["vix"]
    reports = _reports(connection, [row["anomaly_id"] for row in context["anomalies"]])
    events = _event_rows(context["anomalies"], context["events"], reports, context["fresh"])
    pool_returns = [context["daily"][ticker]["ret"] for ticker in context["pool"] if ticker in context["daily"]]
    down_count = sum(1 for value in pool_returns if value is not None and value < 0)
    wide_count = sum(1 for value in pool_returns if value is not None and abs(value) >= MOVE_BAND)
    implication = (
        f"标的池{len(context['pool'])}只里{down_count}只下跌、{wide_count}只波动超过7%。详见我的标的与纸面账户。"
    )
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
            {"id": "SPY", "name": INDEX_LABELS["SPY"], "ret": spy},
            {"id": "QQQ", "name": INDEX_LABELS["QQQ"], "ret": qqq},
            {"id": "IWM", "name": INDEX_LABELS["IWM"], "ret": iwm},
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
        sentence = f"跌幅最大的主题是{worst['sector']}，平均{worst['average'] * 100:.2f}%。"
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
        view = valuation_view(
            stock["price"],
            None if ticker not in context["ranges"] else context["ranges"][ticker]["neutral"],
        )
        holdings.append(_holding_row(ticker, position, stock, context["sell"], context["pending"], plan_payload, view))
    held = set(context["positions"])
    candidates = []
    for ticker, score in sorted(context["scores"].items()):
        if ticker in held or not score["entry_pass"] or ticker not in set(context["pool"]):
            continue
        stock = themes.get(ticker) or _member(ticker, day, context["bars"], score, context["daily"], False, [])
        view = valuation_view(
            stock["price"],
            None if ticker not in context["ranges"] else context["ranges"][ticker]["neutral"],
        )
        candidates.append(_candidate_row(stock, view))
    ledger = context["ledger"]
    equity = None if ledger is None else ledger["equity"]
    cash = None if ledger is None else ledger["cash"]
    peak = None if ledger is None else ledger["peak_equity"]
    previous = _previous_equity(connection, day, context["cutoff"], context["portfolio"])
    day_change = None if equity is None or previous in (None, 0) else equity / previous - 1
    drawdown = None if equity is None or peak in (None, 0) else equity / peak - 1
    near = sum(1 for row in holdings if row["near_disaster"])
    sentence = f"持仓{len(holdings)}只，距灾难线过近{near}只，待成交{len(context['pending'])}笔。"
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
        "labels": labels,
        "review_gap": None if labels else "尚无 T+1/T+5/T+20 打标记录",
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }
