"""Holding-risk highlights. Thresholds are constants or parameter-file values. Orders stay untouched."""

import re

import yaml

from inves_cog.trading.scoring.rules import load_rule_a
from inves_cog.web.brief import (
    MISSING,
    PARAMS_ROOT,
    _event_title,
    _number,
    _price,
    _tech,
    disaster_line,
    format_fraction,
    format_points,
    half_up,
)
from inves_cog.web.pages import _one, _rows, _tickers

# Distance to the disaster line. Ten percent is orange, twenty percent is quiet.
DISASTER_RED = 0.10
DISASTER_ORANGE = 0.20
# A holding's own close-to-close drop.
DAY_DROP = -0.05
# One sector's close market value over estimated assets.
THEME_ORANGE = 0.25
THEME_RED = 0.35
# Orange begins this many points before the parameter file's drawdown brake.
DD_APPROACH_POINTS = 2
_EVENT_TITLE = re.compile(r"^(?P<name>.+?) \d+ 只(?:集体|同日)(?P<way>下跌|上涨)$")
EMPTY = "当前没有需要关注的风险"
RISK_FORMULAS = (
    "距灾难止损线 = (现价 − 灾难线) / 现价。小于 10% 为红，达到 10% 且小于 20% 为橙，达到 20% 不提示。"
    "距离写成不带符号的 1 位小数。",
    "跌破 200 日线的连续天数取账本评分，不从日线自算。已执行过破位减仓为橙。"
    "达到门槛且持有满最短天数、非恐慌为红，并写下次减仓比例。持有不足或恐慌为橙。"
    "未达门槛时，达到减仓天数减 1 为红，否则为橙。天数和比例取卖出参数。",
    "持仓属于当日池内异常为橙；暴露为直接时为红。",
    "当日覆盖层冷静期生效为橙，并写明冷静期内不加仓。",
    "主题占比 = 该主题持仓收盘市值 / 按收盘估算的总资产。超过 25% 为橙，超过 35% 为红。正好等于不升级。",
    f"组合回撤 = 按收盘估算的总资产 / 历史峰值 − 1。比回撤刹车高 {DD_APPROACH_POINTS} 个百分点以内为橙，"
    "达到回撤刹车为红。刹车线和更深闸门取风险参数。",
    "持仓当日跌幅达到或超过 5% 为橙。",
    "页面只给风险着色和人话，不改规则 A 的订单。",
)


def disaster_level(gap):
    """Strictly inside 10 percent is red. The 10 and 20 percent edges are orange and quiet."""
    if gap is None:
        return None
    if gap < DISASTER_RED:
        return "red"
    if gap < DISASTER_ORANGE:
        return "orange"
    return None


def day_level(ret):
    if ret is None or ret > DAY_DROP:
        return None
    return "orange"


def theme_level(share):
    """Shares above 35 percent are red. Exactly 25 and exactly 35 stay at the lower rung."""
    if share is None:
        return None
    if share > THEME_RED:
        return "red"
    if share > THEME_ORANGE:
        return "orange"
    return None


def drawdown_level(drawdown, trigger):
    """Trigger is already in percent points, such as minus 8. Drawdown is a fraction."""
    if drawdown is None or trigger is None:
        return None
    points = drawdown * 100
    if points <= trigger:
        return "red"
    if points <= trigger + DD_APPROACH_POINTS:
        return "orange"
    return None


def ma_level(days, rule_days):
    if not days:
        return None
    if rule_days is not None and days >= rule_days - 1:
        return "red"
    return "orange"


def format_plain_percent(value):
    """Distances and shares. One decimal, no plus or minus."""
    if value is None:
        return MISSING
    shown = half_up(abs(float(value)) * 100, 1)
    return f"{shown:.1f}%"


def below_clause(days, rule_days, stage, held_days, minimum_age, panic, fraction):
    """Wording for a name still under the 200-day line. Days are the ledger score, not a bar count."""
    if not days or days <= 0:
        return None
    days = int(days)
    if stage == 2:
        text = f"已连续 {days} 天低于 200 日线；规则 A 已执行破位减仓，不再重复减仓"
        return "orange", text
    reached = rule_days is not None and days >= rule_days
    if reached and (panic or held_days is None or minimum_age is None or held_days < minimum_age):
        if panic:
            reason = "恐慌模式下暂停破位减仓"
        else:
            age = MISSING if minimum_age is None else str(int(minimum_age))
            reason = f"持有不足 {age} 个交易日，暂不减仓"
        return "orange", f"已连续 {days} 天低于 200 日线，{reason}"
    if reached:
        shown = format_plain_percent(fraction)
        text = f"已连续 {days} 天低于 200 日线，达到规则 A 破位减仓条件，下一次计划将减仓 {shown}"
        return "red", text
    rule = MISSING if rule_days is None else str(int(rule_days))
    level = "red" if rule_days is not None and days >= rule_days - 1 else "orange"
    return level, f"已连续 {days} 天低于 200 日线，规则 A 在第 {rule} 天触发减仓"


def risk_params(version):
    path = PARAMS_ROOT / version / "m4.yaml"
    loaded = yaml.safe_load(path.read_text())
    return loaded["m4"]["risk"]


def price_text(value):
    if value is None:
        return MISSING
    number = float(value)
    if abs(number) >= 100:
        shown = f"{int(half_up(number, 0)):,}"
    else:
        shown = f"{half_up(number, 2):,}"
    return f"${shown}"


def portfolio_view(connection, day, context):
    """Every triggered line for the account page, plus the counts the market page appends."""
    book = _book(context, day)
    cooling = _cooling(connection, day, context["cutoff"])
    events = _pool_events(connection, context)
    sell = context["sell"] or {}
    below_days = sell.get("below_days") or {}
    risk = risk_params(context["version"])
    lines = []
    by_ticker = {}
    for ticker, position in sorted(context["positions"].items()):
        built = _stock_line(ticker, position, day, context, sell, below_days, cooling, events)
        if built is None:
            continue
        lines.append(built)
        by_ticker[ticker] = built
    lines.extend(_theme_lines(book))
    drawdown = _drawdown_line(book, risk)
    if drawdown is not None:
        lines.append(drawdown)
    lines.sort(key=_line_key)
    reds = [row for row in lines if row["level"] == "red"]
    oranges = [row for row in lines if row["level"] == "orange"]
    note = f"红色 {len(reds)} 项，橙色 {len(oranges)} 项。"
    note += f"第一条红色：{reds[0]['text']}" if reds else "没有红色项。"
    return {"lines": lines, "by_ticker": by_ticker, "note": note, "card": _card(book, risk), "empty": EMPTY}


def _line_key(row):
    return (0 if row["level"] == "red" else 1, 0 if row.get("ticker") else 1, row.get("ticker") or "")


def _book(context, day):
    ledger = context["ledger"] or {}
    cash = _number(ledger.get("cash"))
    peak = _number(ledger.get("peak_equity"))
    sector_of = context["catalog"]["sector_of"]
    values = {}
    complete = cash is not None
    for ticker, position in context["positions"].items():
        shares = _number(position.get("shares"))
        close = _close(context, ticker, day)
        if shares is None or close is None:
            complete = False
            continue
        values[ticker] = {"shares": shares, "close": close, "sector": sector_of.get(ticker) or "未分组"}
    equity = None
    if complete and values:
        equity = cash + sum(item["shares"] * item["close"] for item in values.values())
    drawdown = None if equity in (None, 0) or peak in (None, 0) else equity / peak - 1
    return {
        "cash": cash,
        "peak": peak,
        "equity": equity,
        "drawdown": drawdown,
        "values": values,
        "holdings": len(context["positions"]),
    }


def _close(context, ticker, day):
    rows = [row for row in context["bars"].get(ticker) or [] if row["trade_date"] <= day and row["close"] is not None]
    if not rows or rows[-1]["trade_date"] != day:
        return None
    return float(rows[-1]["close"])


def _marked(context, ticker, day):
    history = context["bars"].get(ticker) or []
    today = [row for row in history if row["trade_date"] == day]
    return _price(_tech(context["scores"].get(ticker)), today or history)


def _cooling(connection, day, cutoff):
    row = _one(
        connection,
        """
        SELECT payload FROM overlay.versions
        WHERE date = %s AND generated_at < %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    payload = {} if row is None or not isinstance(row["payload"], dict) else row["payload"]
    tickers = payload.get("tickers") if isinstance(payload.get("tickers"), dict) else {}
    return {ticker for ticker, item in tickers.items() if isinstance(item, dict) and item.get("cooling_off") is True}


def _pool_events(connection, context):
    chosen = [row for row in context["anomalies"] if row.get("universe") == "pool"]
    exposures = _exposures(connection, [row["anomaly_id"] for row in chosen])
    prepared = []
    for row in chosen:
        names = _tickers(row.get("members"))
        title = _event_title(list(row.get("baskets") or []), names, row.get("direction"), context["catalog"])
        prepared.append({**row, "names": set(names), "title": title, "exposure": exposures.get(row["anomaly_id"], {})})
    return prepared


def _exposures(connection, anomaly_ids):
    if not anomaly_ids:
        return {}
    rows = _rows(
        connection,
        """
        SELECT anomaly_id, ticker, exposure
        FROM perception.ticker_status
        WHERE anomaly_id = ANY(%s)
        """,
        (list(anomaly_ids),),
    )
    found = {}
    for row in rows:
        found.setdefault(row["anomaly_id"], {})[row["ticker"]] = row["exposure"]
    return found


def _score_days(context, ticker):
    state = context.get("state") if isinstance(context.get("state"), dict) else {}
    scores = state.get("scores") if isinstance(state.get("scores"), dict) else {}
    score = scores.get(ticker)
    if not isinstance(score, dict):
        return 0
    days = _number(score.get("consec_below200"))
    if days is None or days <= 0:
        return 0
    return int(days)


def _stage(position):
    stage = _number(position.get("stage"))
    if stage is None:
        return 0
    return int(stage)


def _held_days(context, position):
    state = context.get("state") if isinstance(context.get("state"), dict) else {}
    index = _number(state.get("index"))
    entry = _number(position.get("entry_index"))
    if index is None or entry is None:
        return None
    return index - entry


def _stock_line(ticker, position, day, context, sell, below_days, cooling, events):
    price = _marked(context, ticker, day)
    line = disaster_line(_number(position.get("peak_price")), price, sell)
    gap = None if price in (None, 0) or line is None else (price - line) / price
    parts = []
    levels = []
    disaster = disaster_level(gap)
    if disaster is not None:
        levels.append(disaster)
        parts.append(f"距灾难止损线 {format_plain_percent(gap)}（{price_text(line)}）")
    ret = None if ticker not in context["daily"] else context["daily"][ticker].get("ret")
    if day_level(ret) is not None:
        levels.append("orange")
        parts.append(f"今日 {format_fraction(ret)}")
    event = _event_for(ticker, events)
    if event is not None:
        levels.append(event[0])
        parts.append(event[1])
    tier = position.get("tier_now")
    rule_days = below_days.get(tier)
    fraction = (sell.get("broken_fraction") or {}).get(tier)
    clause = below_clause(
        _score_days(context, ticker),
        rule_days,
        _stage(position),
        _held_days(context, position),
        sell.get("minimum_age"),
        context.get("state", {}).get("panic") is True,
        fraction,
    )
    if clause is not None:
        levels.append(clause[0])
        parts.append(clause[1])
    if ticker in cooling:
        levels.append("orange")
        parts.append("冷静期内不加仓")
    if not parts:
        return None
    level = "red" if "red" in levels else "orange"
    return {"level": level, "ticker": ticker, "text": f"{ticker} " + "，".join(parts) + "。"}


def _event_for(ticker, events):
    matching = [row for row in events if ticker in row["names"]]
    if not matching:
        return None
    direct = [row for row in matching if row["exposure"].get(ticker) == "直接"]
    picked = sorted(direct or matching, key=lambda row: row["anomaly_id"])[0]
    match = _EVENT_TITLE.match(picked["title"] or "")
    if match:
        clause = f"卷入 {match.group('name')}{match.group('way')}"
    else:
        way = "上涨" if picked.get("direction") in {"up", "上涨"} else "下跌"
        clause = f"卷入 {picked['title']}{way}"
    return ("red" if picked["exposure"].get(ticker) == "直接" else "orange", clause)


def _theme_lines(book):
    if book["equity"] in (None, 0):
        return []
    totals = {}
    for item in book["values"].values():
        totals[item["sector"]] = totals.get(item["sector"], 0.0) + item["shares"] * item["close"]
    lines = []
    for sector, value in sorted(totals.items()):
        share = value / book["equity"]
        level = theme_level(share)
        if level is None:
            continue
        text = f"{sector}占 {format_plain_percent(share)}，单一主题集中。"
        lines.append({"level": level, "ticker": None, "text": text})
    return lines


def _drawdown_line(book, risk):
    trigger = None if risk is None else risk.get("dd8_trigger")
    level = drawdown_level(book["drawdown"], trigger)
    if level is None:
        return None
    text = (
        f"组合距峰值 {format_fraction(book['drawdown'])}，"
        f"回撤刹车 {format_points(risk.get('dd8_trigger'))}，"
        f"更深闸门 {format_points(risk.get('dd12_trigger'))}"
    )
    if level == "red":
        text += f"，已触发回撤刹车，进攻层减仓 {format_plain_percent(risk.get('dd8_sell_fraction'))}"
        text += "，到了更深闸门就暂停非防守层新开仓"
    else:
        text += "，接近回撤刹车"
    return {"level": level, "ticker": None, "text": text + "。"}


def _card(book, risk):
    themes = []
    if book["equity"] not in (None, 0):
        totals = {}
        for item in book["values"].values():
            totals[item["sector"]] = totals.get(item["sector"], 0.0) + item["shares"] * item["close"]
        ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:3]
        themes = [{"sector": sector, "share": value / book["equity"]} for sector, value in ranked]
    gaps = gate_gaps(book["drawdown"], risk)
    cash_ratio = None if book["equity"] in (None, 0) or book["cash"] is None else book["cash"] / book["equity"]
    return {
        "themes": themes,
        "drawdown": book["drawdown"],
        "dd8_gap": gaps["dd8"],
        "dd12_gap": gaps["dd12"],
        "holdings": book["holdings"],
        "slots": load_rule_a()["max_positions"],
        "cash_ratio": cash_ratio,
    }


def gate_gaps(drawdown, risk):
    return {
        "dd8": _gate_gap(drawdown, None if risk is None else risk.get("dd8_trigger")),
        "dd12": _gate_gap(drawdown, None if risk is None else risk.get("dd12_trigger")),
    }


def _gate_gap(drawdown, trigger):
    if drawdown is None or trigger is None:
        return MISSING
    gap = drawdown * 100 - trigger
    shown = f"{half_up(abs(gap), 2):.2f}"
    if gap >= 0:
        return f"还有 {shown} 个百分点"
    return f"已超过 {shown} 个百分点"
