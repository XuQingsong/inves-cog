"""Move card and the daily page. This path does not call anomaly candidates."""

from datetime import datetime

MOVE_QUESTION = "这些新闻里哪几条可能解释这次波动？每条写编号、一句话说怎么影响、强中弱。都不像就说没有。"
UNCLEAR = "同一天，发布钟点不清楚"
SEEN = "提前看到"
UNTAGGED = "入库了但没标到"
MISSED = "没采到"
NONE = "查过没有消息"
_LIMIT = 40


def _parse(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    if "T" not in value and ":" not in value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _clock_clear(card):
    if "钟点清楚" in card:
        return bool(card["钟点清楚"])
    text = str(card.get("发布时间") or "")
    return "T" in text or ":" in text


def _view(card):
    companies = []
    for company in [*(card.get("名单内") or []), *(card.get("名单外") or [])]:
        if isinstance(company, dict):
            companies.append(
                {
                    "代码": company.get("代码", ""),
                    "名称": company.get("名称", ""),
                    "理由": company.get("理由", ""),
                    "方向": company.get("方向", ""),
                }
            )
    if not companies:
        companies = list(card.get("公司和理由") or [])
    return {
        "编号": card.get("编号"),
        "发布时间": card.get("发布时间"),
        "标题": card.get("标题"),
        "说了什么": card.get("说了什么", ""),
        "公司和理由": companies,
    }


def _resolve(cited, sent_ids):
    if not isinstance(cited, str) or not cited:
        return None
    matches = [item_id for item_id in sent_ids if item_id == cited or item_id.endswith(cited)]
    if len(matches) == 1:
        return matches[0]
    return None


def _already(card, start):
    if start is None:
        return False
    if not _clock_clear(card):
        published = str(card.get("发布时间") or "")[:10]
        return bool(published) and published < start.date().isoformat()
    published_at = _parse(card.get("发布时间"))
    return published_at is not None and published_at <= start


def classify(move, cards):
    """Program label. A same-day item with no clock is never 提前看到."""
    start = _parse(move.get("开始"))
    day = str(move.get("日期") or (start.date().isoformat() if start else ""))[:10]
    unclear = tagged = untagged = False
    for card in cards:
        if not _clock_clear(card):
            published = str(card.get("发布时间") or "")[:10]
            if published and day and published < day:
                if card.get("当时标到"):
                    tagged = True
                else:
                    untagged = True
            elif published and published == day:
                unclear = True
            continue
        published_at = _parse(card.get("发布时间"))
        if start is not None and published_at is not None and published_at > start:
            continue
        if card.get("当时标到"):
            tagged = True
        else:
            untagged = True
    if unclear and not tagged:
        return UNCLEAR
    if tagged:
        return SEEN
    if untagged:
        return UNTAGGED
    if move.get("补查到"):
        return MISSED
    return NONE


def _explanations(reply, sent, move):
    if not isinstance(reply, dict):
        return [], 0
    raw = reply.get("解释", reply.get("条目"))
    if raw in (None, "没有") or reply.get("没有") is True:
        return [], 0
    if not isinstance(raw, list):
        return [], 0
    by_id = {card.get("编号"): card for card in sent}
    sent_ids = [card.get("编号") for card in sent if isinstance(card.get("编号"), str)]
    start = _parse(move.get("开始"))
    kept, dropped = [], 0
    for entry in raw:
        if not isinstance(entry, dict):
            dropped += 1
            continue
        full = _resolve(entry.get("编号"), sent_ids)
        if full is None:
            dropped += 1
            continue
        card = by_id.get(full, {})
        sentence = entry.get("怎么影响") or entry.get("一句话") or ""
        kept.append(
            {
                "编号": full,
                "怎么影响": sentence,
                "强弱": entry.get("强弱") or entry.get("强中弱") or "",
                "新闻卡原句": card.get("说了什么", ""),
                "波动卡原句": sentence,
                "当时已经知道": _already(card, start),
            }
        )
    return kept, dropped


def move_card(move, cards, client):
    """Ask once which of the recalled cards might explain this move."""
    sent = list(cards)[:_LIMIT]
    payload = {
        "波动": {
            "股票": move.get("股票"),
            "方向": move.get("方向"),
            "幅度": move.get("幅度"),
            "日期": move.get("日期"),
            "开始": move.get("开始"),
        },
        "新闻": [_view(card) for card in sent],
        "问法": MOVE_QUESTION,
    }
    reply = client.call("move_card", payload)
    explanations, dropped = _explanations(reply, sent, move)
    return {"解释": explanations, "丢掉": dropped, "归类": classify(move, sent), "问法": MOVE_QUESTION}


def _level(company):
    return company.get("重要程度") or company.get("高中低") or ""


def _fold(card):
    companies = list(card.get("名单内") or [])
    high = [company for company in companies if _level(company) == "高"]
    mid = [company for company in companies if _level(company) == "中"]
    marked = len(high) + len(mid)
    if marked > 8:
        lines = [f"标了名单里的一大片（{marked} 家）"]
        if high:
            lines.extend(company.get("名称") or company.get("代码") or "" for company in high)
        else:
            shown = mid[:3]
            lines.extend(company.get("名称") or "" for company in shown)
            lines.append(f"其余 {marked - len(shown)} 家")
        return lines
    return [company.get("名称") or company.get("代码") or "" for company in high]


def _move_line(move):
    names = move.get("股票") or move.get("篮子") or []
    label = "、".join(str(name) for name in names)
    return f"{label} {move.get('方向', '')} {move.get('幅度', '')}".strip()


def _number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return "" if value is None else str(value)


def _scoped(value, trade_date):
    if not isinstance(value, list) or not value:
        return None
    rows = []
    for row in value:
        if not isinstance(row, dict):
            continue
        row_day = str(row.get("trade_date") or "")[:10]
        if trade_date and row_day and row_day != trade_date:
            continue
        rows.append(row)
    return rows


def _valuation_lines(valuation, trade_date):
    rows = _scoped(valuation, trade_date)
    if not rows:
        return ["估值没有拿到"]
    lines = []
    for row in rows:
        ticker = row.get("ticker") or ""
        status = row.get("status")
        if status == "ok":
            bear = _number(row.get("bear"))
            neutral = _number(row.get("neutral"))
            bull = _number(row.get("bull"))
            lines.append(f"{ticker} {bear} / {neutral} / {bull}")
        elif status in {"unvalued", "failed"}:
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            lines.append(f"{ticker} 不估：{payload.get('reason') or ''}")
    return lines or ["估值没有拿到"]


def _amount(order):
    for key in ("qty", "fraction", "value"):
        if order.get(key) is not None:
            return _number(order[key])
    return ""


def _plan_lines(plan, trade_date):
    rows = _scoped(plan, trade_date)
    if not rows:
        return ["计划没有拿到"]
    orders = []
    for row in rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        found = payload.get("orders") if isinstance(payload.get("orders"), list) else row.get("orders")
        if isinstance(found, list):
            orders.extend(order for order in found if isinstance(order, dict))
    if not orders:
        return ["今天没有计划单"]
    lines = []
    for order in orders:
        text = f"{order.get('ticker') or ''} {order.get('action') or ''} {_amount(order)}".strip()
        if text:
            lines.append(text)
    return lines or ["今天没有计划单"]


_MACRO_WORDS = ("宏观", "利率", "通胀", "cpi", "非农", "就业", "美联储", "关税", "指数", "大盘", "衰退", "fed")


def _marked(card):
    high = mid = 0
    for company in card.get("名单内") or []:
        if not isinstance(company, dict):
            continue
        level = _level(company)
        if level == "高":
            high += 1
        elif level == "中":
            mid += 1
    return high, mid


def _in_scope(card):
    high, mid = _marked(card)
    return high > 0 or high + mid > 8


def _high_codes(card):
    found = []
    for company in card.get("名单内") or []:
        if not isinstance(company, dict) or _level(company) != "高":
            continue
        code = company.get("代码") or company.get("名称") or ""
        if code and code not in found:
            found.append(code)
    return found


def _industry_sentence(card):
    raw = card.get("行业")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return " ".join(item for item in raw if isinstance(item, str))
    return ""


def _macro(card):
    text = f"{card.get('说了什么') or ''} {_industry_sentence(card)}".casefold()
    return any(word in text for word in _MACRO_WORDS)


def _wide(card):
    high, mid = _marked(card)
    return len(_high_codes(card)) >= 3 or high + mid > 8


def _held_names(plan, trade_date):
    """Share counts above zero. Missing positions are not the same as an empty book."""
    rows = _scoped(plan, trade_date)
    if not rows:
        return None
    saw = False
    names = []
    for row in rows:
        source = row.get("positions") if isinstance(row.get("positions"), dict) else None
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if source is None and isinstance(payload.get("positions"), dict):
            source = payload["positions"]
        if source is None:
            continue
        saw = True
        for ticker, shares in source.items():
            if isinstance(shares, bool) or not isinstance(shares, (int, float)):
                continue
            if shares > 0 and ticker not in names:
                names.append(ticker)
    if not saw or not names:
        return None
    return names


def _move_names(moves):
    names = []
    for move in moves or []:
        for name in move.get("股票") or []:
            if name and name not in names:
                names.append(name)
    return names


def _position_hit(card, held):
    if not held:
        return []
    return [code for code in _high_codes(card) if code in held]


def _first_shown(scoped):
    """Macro and wide names, at most five. That cap is not a holding count."""
    first = [card for card in scoped if _macro(card) or _wide(card)]
    first.sort(key=lambda card: (0 if _macro(card) else 1, -len(_high_codes(card)), str(card.get("编号") or "")))
    return first[:5]


def _hits_move(card, move_names):
    return bool(set(_high_codes(card)) & set(move_names))


def _cards_for(scoped, ticker):
    return [card for card in scoped if ticker in _high_codes(card)]


def _holding_lines(cards, move_names):
    """One line for this holding. Other high cards on the same name are counted, not repeated."""
    chosen = min(
        cards,
        key=lambda card: (0 if _hits_move(card, move_names) else 1, str(card.get("编号") or "")),
    )
    lines = []
    said = str(chosen.get("说了什么") or chosen.get("标题") or "")
    if _hits_move(chosen, move_names):
        said = f"{said} 碰上不寻常波动".strip()
    if said:
        lines.append(said)
    lines.extend(_fold(chosen))
    extra = len(cards) - 1
    if extra:
        lines.append(f"这只还有 {extra} 条")
    return lines


def _ranked_lines(cards, held, move_names, tier):
    lines = []
    for card in cards:
        said = str(card.get("说了什么") or card.get("标题") or "")
        flags = []
        hit = _position_hit(card, held)
        if tier == 1 and hit:
            flags.append("含持仓")
        if set(hit) & set(move_names):
            flags.append("碰上不寻常波动")
        if said:
            lines.append(f"{said} {' '.join(flags)}".strip())
        lines.extend(_fold(card))
    return lines


def _morning_news_lines(cards, moves, plan, trade_date):
    scoped = [card for card in cards or [] if isinstance(card, dict) and _in_scope(card)]
    held = _held_names(plan, trade_date)
    move_names = _move_names(moves)
    first = _first_shown(scoped)
    lines = ["先看：宏观和影响面广的"]
    lines.extend(_ranked_lines(first, held, move_names, 1) or ["这档没有"])
    lines.append("再看：持仓上影响大的")
    accounted = {id(card) for card in first}
    if held:
        lines.extend(_holding_section(scoped, held, move_names, accounted))
    else:
        lines.append("没有持仓快照")
    rest = sum(1 for card in scoped if id(card) not in accounted)
    if rest:
        lines.append(f"还有 {rest} 条标了高，这里不展开")
    return lines


def _holding_section(scoped, held, move_names, accounted):
    """Every positive holding, move names first. Unexpanded cards on that name are not counted again."""
    lines = []
    quiet = []
    moved = set(move_names)
    order = sorted(enumerate(held), key=lambda item: (item[1] not in moved, item[0]))
    for _, ticker in order:
        owned = _cards_for(scoped, ticker)
        if not owned:
            quiet.append(ticker)
            continue
        lines.extend(_holding_lines(owned, move_names))
        accounted.update(id(card) for card in owned)
    if quiet:
        lines.append("今天没有标成高的：" + "、".join(sorted(quiet)))
    return lines


def daily_text(*, moves, news_cards, valuation, plan, trade_date=None):
    """One page of text. News and moves do not change valuation or the plan."""
    lines = ["哪些股票或篮子波动不寻常"]
    if not moves:
        lines.append("没有不寻常波动")
    lines.extend(_move_line(move) for move in moves)
    lines.append("哪几条新闻可能解释")
    for move in moves:
        explanations = move.get("解释") or []
        if explanations:
            for item in explanations:
                lines.append(f"{item.get('编号')} {item.get('怎么影响')} {item.get('强弱')}")
        else:
            lines.append("入库新闻里没有对得上的")
        for extra in move.get("补查") or []:
            if not isinstance(extra, dict):
                continue
            suffix = " 波动后才公开" if extra.get("波动后才公开") else ""
            lines.append(f"{extra.get('编号')} {extra.get('说了什么')}{suffix}".strip())
    lines.append("归类")
    lines.extend(str(move.get("归类", "")) for move in moves)
    lines.extend(_morning_news_lines(news_cards, moves, plan, trade_date))
    lines.append("估值和纸面计划")
    lines.extend(_valuation_lines(valuation, trade_date))
    lines.extend(_plan_lines(plan, trade_date))
    lines.append("新闻和波动不改估值，不改计划")
    return "\n".join(line for line in lines if line != "")
