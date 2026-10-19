"""Move card and the daily page. This path does not call anomaly candidates."""

import re
from datetime import datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

MOVE_QUESTION = "这些新闻里哪几条可能解释这次波动？每条写编号、一句话说怎么影响、强中弱。都不像就说没有。"
UNCLEAR = "同一天，发布钟点不清楚"
SEEN = "提前看到"
UNTAGGED = "入库了但没标到"
MISSED = "没采到"
NONE = "查过没有消息"
_LIMIT = 40
_SHANGHAI = ZoneInfo("Asia/Shanghai")


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
                "发布时间": card.get("发布时间") or "",
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


def _as_decimal(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _cents(value):
    number = _as_decimal(value)
    if number is None:
        return ""
    return f"{number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _row_price(row):
    price = row.get("price")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    if price is None:
        price = payload.get("price")
    return _as_decimal(price)


def _value_line(ticker, row):
    status = row.get("status")
    if status in {"unvalued", "failed"}:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        reason = str(payload.get("reason") or "")
        if "金融" in reason:
            return f"{ticker} 暂不估值：金融类公司，缺所需财务数据"
        if "亏损" in reason:
            return f"{ticker} 暂不估值：亏损且没有增长，按规则不估"
        return f"{ticker} 暂不估值：所需财务数据不全"
    price = _row_price(row)
    bear = _as_decimal(row.get("bear"))
    neutral = _as_decimal(row.get("neutral"))
    bull = _as_decimal(row.get("bull"))
    if price is None or bear is None or neutral is None or bull is None:
        return f"{ticker} 估值待复核"
    if neutral < price / Decimal(3) or neutral > price * Decimal(3):
        return f"{ticker} 现价 {_cents(price)}｜估值待复核"
    return f"{ticker} 现价 {_cents(price)}｜偏低 {_cents(bear)}｜中间 {_cents(neutral)}｜偏高 {_cents(bull)}"


def _order_rows(plan, trade_date):
    if not isinstance(plan, list):
        return []
    orders = []
    for row in _scoped(plan, trade_date) or []:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        found = payload.get("orders") if isinstance(payload.get("orders"), list) else row.get("orders")
        if isinstance(found, list):
            orders.extend(order for order in found if isinstance(order, dict))
    return orders


def _relevant_names(held, moves, plan, trade_date):
    names = set(held or [])
    names.update(_move_names(moves))
    for order in _order_rows(plan, trade_date):
        ticker = order.get("ticker")
        if ticker:
            names.add(ticker)
    return names


def _valuation_lines(valuation, trade_date, shown):
    if not isinstance(valuation, list) or not valuation:
        return ["今天没有拿到估值"]
    by_ticker = {}
    for row in _scoped(valuation, trade_date) or []:
        ticker = row.get("ticker")
        if ticker:
            by_ticker.setdefault(ticker, row)
    lines = [_value_line(ticker, by_ticker[ticker]) for ticker in sorted(shown) if ticker in by_ticker]
    hidden = [ticker for ticker in by_ticker if ticker not in shown]
    if hidden:
        lines.append(f"其余 {len(hidden)} 只不在这一页")
    return lines or ["今天没有拿到估值"]


def _plan_lines(plan, trade_date):
    if not isinstance(plan, list):
        return ["今天没有拿到计划"]
    orders = _order_rows(plan, trade_date)
    if not orders:
        return ["今天没有计划单"]
    lines = []
    for order in orders:
        bits = [part for part in (str(order.get("ticker") or ""), str(order.get("action") or "")) if part]
        amount = _cents(order.get("value"))
        if amount:
            bits.append(f"约 {amount} 美元")
        line = " ".join(bits)
        qty = _as_decimal(order.get("qty"))
        if qty is not None:
            shares = int(qty) if qty == qty.to_integral_value() else _cents(qty)
            line += f"，{shares} 股"
        if line:
            lines.append(line)
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


def _first_shown(scoped):
    """Macro and wide names, at most five. That cap is not a holding count."""
    first = [card for card in scoped if _macro(card) or _wide(card)]
    first.sort(key=lambda card: (0 if _macro(card) else 1, -len(_high_codes(card)), str(card.get("编号") or "")))
    return first[:5]


def _hits_move(card, move_names):
    return bool(set(_high_codes(card)) & set(move_names))


def _cards_for(scoped, ticker):
    return [card for card in scoped if ticker in _high_codes(card)]


def _percent_number(raw):
    match = re.search(r"-?\d+(?:\.\d+)?", str(raw or ""))
    if match is None:
        return None
    return abs(Decimal(match.group()))


def _percent_text(number):
    if number is None:
        return ""
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return text


def _source_label(identifier):
    text = str(identifier or "")
    if text.startswith("sec_8k"):
        return "SEC 8-K"
    parts = text.split(":")
    if len(parts) < 2 or not parts[1]:
        return ""
    word = parts[1]
    if word.isascii() and word.isalpha():
        return word[:1].upper() + word[1:]
    return word


def _beijing(value):
    stamp = _parse(value)
    if stamp is None or stamp.tzinfo is None:
        return ""
    local = stamp.astimezone(_SHANGHAI)
    return f"{local.month}月{local.day}日 {local:%H:%M}"


def _legacy_move(move):
    """A caller that already supplied a Chinese word and a magnitude keeps that line."""
    return str(move.get("方向") or "") in {"涨", "跌"} and move.get("幅度") not in (None, "")


def _move_names_line(move):
    return [str(name) for name in (move.get("股票") or []) if name]


def _move_headline(move, index):
    if _legacy_move(move):
        return _legacy_headline(move, index)
    return _raw_headline(move, index)


def _legacy_headline(move, index):
    names = _move_names_line(move)
    direction = str(move.get("方向") or "")
    number = _percent_text(_percent_number(move.get("幅度")))
    percent = f" {number}%" if number else ""
    if len(names) > 1:
        body = f"{len(names)} 只一起{direction}，平均{direction}{percent}：{'、'.join(names)}"
    else:
        body = f"{names[0] if names else ''} {direction}{percent}".strip()
    return f"{index}. {body}"


def _numeric_returns(move):
    numbers = []
    for value in move.get("收益") or []:
        if isinstance(value, bool) or value is None or value == "":
            continue
        try:
            numbers.append(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            continue
    return numbers


def _peer_clause(direction):
    if direction == "down":
        return "，明显弱于同类股票"
    if direction == "up":
        return "，明显强于同类股票"
    return ""


def _raw_headline(move, index):
    names = _move_names_line(move)
    direction = str(move.get("方向") or "")
    word = {"up": "涨", "down": "跌"}.get(direction, direction if direction in {"涨", "跌"} else "")
    post = (move.get("时段") or "") == "post"
    codes = "、".join(names)
    numbers = _numeric_returns(move)
    if not numbers:
        return f"{index}. {_unnamed_move(names, word, post, codes)}"
    average = sum(numbers) / Decimal(len(numbers)) * Decimal(100)
    rounded = average.quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        return f"{index}. {_flat_move(names, post, _peer_clause(direction), codes)}"
    price = "跌" if average < 0 else "涨"
    opposite = (price == "涨" and direction == "down") or (price == "跌" and direction == "up")
    peer = _peer_clause(direction) if opposite else ""
    shown = f"{abs(rounded):.1f}"
    if len(names) > 1:
        where = "盘后一起" if post else "一起"
        body = f"{len(names)} 只{where}{price}，平均{price} {shown}%{peer}：{codes}"
    else:
        where = "盘后" if post else ""
        body = f"{names[0] if names else ''} {where}{price} {shown}%{peer}".replace("  ", " ").strip()
    return f"{index}. {body}"


def _unnamed_move(names, word, post, codes):
    if len(names) > 1:
        where = "盘后一起" if post else "一起"
        return f"{len(names)} 只{where}{word}：{codes}"
    where = "盘后" if post else ""
    return f"{names[0] if names else ''} {where}{word}".replace("  ", " ").strip()


def _flat_move(names, post, peer, codes):
    if len(names) > 1:
        where = "盘后" if post else ""
        return f"{len(names)} 只{where}基本没动{peer}：{codes}"
    where = "盘后" if post else ""
    return f"{names[0] if names else ''} {where}基本没动{peer}".replace("  ", " ").strip()


def _reason_lines(move):
    explanations = [item for item in move.get("解释") or [] if isinstance(item, dict)]
    kept = []
    for item in explanations:
        sentence = str(item.get("怎么影响") or item.get("一句话") or "")
        if not sentence:
            continue
        tail = " ".join(
            part
            for part in (str(item.get("强弱") or ""), _source_label(item.get("编号")), _beijing(item.get("发布时间")))
            if part
        )
        kept.append(f"可能的原因：{sentence} {tail}".strip())
    return kept or ["可能的原因：没找到能解释这次波动的新闻"]


_SEEN_LINES = {
    "入库了但没标到": "收到了新闻，但没认出和这只股票有关",
    "没采到": "当时没收到这条新闻，事后才找到",
    "查过没有消息": "没找到相关新闻",
    "同一天，发布钟点不清楚": "新闻和波动是同一天，分不清先后",
}


def _seen_line(move):
    explanations = [item for item in move.get("解释") or [] if isinstance(item, dict)]
    if any(item.get("当时已经知道") is True for item in explanations):
        return "波动前已经看到这条新闻"
    label = str(move.get("归类") or "")
    if label == "提前看到":
        return "有相关新闻，但没认出是原因"
    return _SEEN_LINES.get(label, "")


def _later_lines(move):
    extras = [item for item in move.get("补查") or [] if isinstance(item, dict)]
    if not extras:
        return []
    lines = ["事后找到、当时还没收到的："]
    for item in extras[:3]:
        sentence = str(item.get("说了什么") or "")
        tail = " ".join(part for part in (_source_label(item.get("编号")), _beijing(item.get("发布时间"))) if part)
        suffix = "（波动开始后才发布）" if item.get("波动后才公开") else ""
        lines.append(f"{sentence} {tail}".strip() + suffix)
    extra = len(extras) - 3
    if extra > 0:
        lines.append(f"另有 {extra} 条")
    return lines


def _move_block(move, index):
    lines = [_move_headline(move, index)]
    lines.extend(_reason_lines(move))
    seen = _seen_line(move)
    if seen:
        lines.append(f"我们当时看到了吗：{seen}")
    lines.extend(_later_lines(move))
    return lines


def _impact_count(card):
    high, mid = _marked(card)
    if high + mid > 8:
        return high + mid
    codes = _high_codes(card)
    return len(codes) if codes else high + mid


def _macro_line(card, held):
    said = str(card.get("说了什么") or card.get("标题") or "")
    line = f"{said} 影响 {_impact_count(card)} 家".strip()
    hit = [code for code in _high_codes(card) if held and code in held]
    if hit:
        line += "，含你的持仓 " + "、".join(hit)
    return line


def _direction_word(card, ticker):
    for company in card.get("名单内") or []:
        if not isinstance(company, dict):
            continue
        if (company.get("代码") or company.get("名称")) != ticker:
            continue
        word = company.get("方向") or ""
        if word in {"利好", "利空", "不确定"}:
            return word
    return "不确定"


def _holding_line(ticker, cards, move_names):
    chosen = min(
        cards,
        key=lambda card: (0 if _hits_move(card, move_names) else 1, str(card.get("编号") or "")),
    )
    said = str(chosen.get("说了什么") or chosen.get("标题") or "")
    line = f"{ticker}：{said} {_direction_word(chosen, ticker)}".strip()
    extra = len(cards) - 1
    if extra:
        line += f"。另有 {extra} 条"
    if ticker in set(move_names):
        line += "（今天也有不寻常波动）"
    return line


def _position_lines(scoped, held, move_names, accounted):
    lines = []
    quiet = []
    moved = set(move_names)
    order = sorted(enumerate(held), key=lambda item: (item[1] not in moved, item[0]))
    for _, ticker in order:
        owned = _cards_for(scoped, ticker)
        if not owned:
            quiet.append(ticker)
            continue
        lines.append(_holding_line(ticker, owned, move_names))
        accounted.update(id(card) for card in owned)
    if quiet:
        lines.append("今天没有重要新闻：" + "、".join(sorted(quiet)))
    return lines


def _news_sections(cards, moves, plan, trade_date, received, held=None):
    if held is None:
        held = _held_names(plan, trade_date)
    if received is False:
        macro = ["今天一条新闻都没收到"]
        if held:
            positions = ["今天一条新闻都没收到，没法判断这些持仓有没有消息：" + "、".join(sorted(held))]
        else:
            positions = ["今天没有拿到持仓"]
        return macro, positions
    scoped = [card for card in cards or [] if isinstance(card, dict) and _in_scope(card)]
    move_names = _move_names(moves)
    first = _first_shown(scoped)
    macro = [_macro_line(card, held) for card in first] or ["今天没有"]
    accounted = {id(card) for card in first}
    if held:
        positions = _position_lines(scoped, held, move_names, accounted)
    else:
        positions = ["今天没有拿到持仓"]
    rest = sum(1 for card in scoped if id(card) not in accounted)
    if rest:
        positions.append(f"另有 {rest} 条较重要的新闻没有列出")
    return macro, positions


def daily_text(*, moves, news_cards, valuation, plan, trade_date=None, received=None, holdings=None):
    """One page of text. News and moves do not change valuation or the plan."""
    lines = [f"{trade_date} 收盘后"] if trade_date else []
    lines.append("一、昨天不寻常的波动")
    if not moves:
        lines.append("昨天没有不寻常的波动")
    for index, move in enumerate(moves or [], start=1):
        lines.extend(_move_block(move, index))
    held = _held_names(plan, trade_date) if holdings is None else (list(holdings) or None)
    macro, positions = _news_sections(news_cards, moves, plan, trade_date, received, held)
    lines.append("二、影响大盘和多个行业的新闻（最多 5 条）")
    lines.extend(macro)
    lines.append("三、你的持仓")
    lines.extend(positions)
    lines.append("四、值多少（美元）")
    lines.extend(_valuation_lines(valuation, trade_date, _relevant_names(held, moves, plan, trade_date)))
    lines.append("五、今天的纸面计划（规则 A，不是真实交易）")
    lines.extend(_plan_lines(plan, trade_date))
    lines.append("新闻和波动的解释，不会改变估值和计划。")
    return "\n".join(line for line in lines if line != "")
