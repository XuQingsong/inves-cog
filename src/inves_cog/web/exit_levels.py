"""Rule-A exit levels for one holding. Reads parameters; does not change positions or orders."""

from inves_cog.trading.execution.state import below, clamp
from inves_cog.web.brief import MISSING, half_up, level

PRICE_RED = 0.10
PRICE_ORANGE = 0.20
SCORE_RED = 5
SCORE_ORANGE = 10
_KINDS = {"attack": "进攻层核心", "normal": "标准层核心", "defense": "防守层核心"}
_DEATH_LINES = {"现金流为负且营收下滑", "营收与EPS同时明显下滑"}


def num(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def holding_kind(position):
    """观察波段仓, or the core tier. A missing tier is not guessed."""
    if not isinstance(position, dict):
        return "类型暂缺"
    if position.get("swing_only") is True:
        return "观察波段仓"
    return _KINDS.get(position.get("tier_now"), "类型暂缺")


def price_band(gap):
    """Distance to a price trigger. Ten percent is orange; twenty percent is quiet."""
    if gap is None:
        return None
    if gap < PRICE_RED:
        return "red"
    if gap < PRICE_ORANGE:
        return "orange"
    return None


def score_band(points):
    """Points above a score floor. Five is orange; ten is quiet. Already below is zero."""
    if points is None:
        return None
    if points < SCORE_RED:
        return "red"
    if points < SCORE_ORANGE:
        return "orange"
    return None


def money(value):
    if value is None:
        return MISSING
    shown = half_up(float(value), 2)
    return f"${shown:,.2f}"


def plain_percent(value):
    if value is None:
        return MISSING
    shown = half_up(abs(float(value)) * 100, 1)
    return f"{shown:.1f}%"


def score_text(value):
    if value is None:
        return MISSING
    shown = f"{half_up(float(value), 1):.1f}"
    if shown.endswith(".0"):
        return shown[:-2]
    return shown


def merged_score(page_score, ledger_score):
    """Ledger books and tech win. The page score fills gaps. Nothing is written back."""
    page = page_score if isinstance(page_score, dict) else {}
    ledger = ledger_score if isinstance(ledger_score, dict) else {}
    books = {
        "quality": num(page.get("quality")),
        "growth": num(page.get("growth")),
        "valuation": num(page.get("valuation")),
        "timing": num(page.get("timing")),
    }
    nested = ledger.get("books") if isinstance(ledger.get("books"), dict) else {}
    for key in books:
        if nested.get(key) is not None:
            books[key] = num(nested.get(key))
    tech = {}
    page_tech = page.get("tech") if isinstance(page.get("tech"), dict) else {}
    ledger_tech = ledger.get("tech") if isinstance(ledger.get("tech"), dict) else {}
    tech.update(page_tech)
    tech.update(ledger_tech)
    merged = {key: value for key, value in ledger.items() if key not in {"books", "tech"}}
    merged["books"] = books
    merged["tech"] = tech
    return merged


def build_levels(position, score, sell, swing, *, price, index, panic):
    """Applicable exit lines for this holding type. The position and score are not modified."""
    kind = holding_kind(position)
    if kind == "类型暂缺":
        return [_blank("类型", "类型暂缺，未套用卖出规则")]
    sell = sell or {}
    swing = swing or {}
    score = score or {}
    if kind == "观察波段仓":
        return [
            _swing_target("波段止盈价", position, score, price, swing.get("take_profit")),
            _swing_stop(position, price, swing),
        ]
    rows = []
    if kind == "进攻层核心":
        rows.append(_disaster(position, score, sell, price))
        rows.append(_double(position, score, sell, price, index))
    rows.append(_breakout(position, score, sell, index, panic))
    if kind == "标准层核心":
        rows.append(_alert(position, score, sell, panic))
    rows.append(_fundamental(position, score, sell))
    shares = num(position.get("swing_shares"))
    if shares is not None and shares > 0:
        bounds = swing.get("attack_take_profit") if kind == "进攻层核心" else swing.get("take_profit")
        rows.append(_swing_target("波段部分止盈价", position, score, price, bounds))
    return rows


def _blank(name, text):
    return {
        "name": name,
        "current": None,
        "trigger": None,
        "gap": None,
        "text": text,
        "risk_level": None,
        "risk_text": None,
    }


def _distance(price, trigger, *, upward):
    if price in (None, 0) or trigger is None:
        return MISSING, None
    if upward:
        if price >= trigger:
            return "已达到触发价", 0.0
        gap = (trigger - price) / price
        return f"还需上涨 {plain_percent(gap)}", gap
    if price <= trigger:
        return "已达到触发价", 0.0
    gap = (price - trigger) / price
    return f"还需下跌 {plain_percent(gap)}", gap


def _price_level(name, price, trigger, *, upward, note=""):
    phrase, gap = _distance(price, trigger, upward=upward)
    text = f"{name}：现价 {money(price)} → 触发 {money(trigger)}，{phrase}"
    if note:
        text += f"。{note}"
    band = price_band(gap)
    risk = None
    if band is not None:
        risk = f"{name}{phrase}（{money(trigger)}）"
        if note:
            risk += f"。{note}"
    return {
        "name": name,
        "current": price,
        "trigger": trigger,
        "gap": gap,
        "text": text,
        "risk_level": band,
        "risk_text": risk,
    }


def _ma50(price, score):
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    return level(price, num(tech.get("dev50")))


def _threshold(score, bounds):
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    vol = num(tech.get("vol20"))
    if vol is None or not isinstance(bounds, (list, tuple)) or len(bounds) != 3:
        return None
    return clamp(vol, bounds)


def _swing_target(name, _position, score, price, bounds):
    threshold = _threshold(score, bounds)
    ma50 = _ma50(price, score)
    trigger = None if threshold is None or ma50 is None else ma50 * (1 + threshold / 100)
    return _price_level(name, price, trigger, upward=True)


def _swing_stop(position, price, swing):
    cost = num(position.get("avg_cost"))
    fraction = num(swing.get("stop_fraction"))
    trigger = None if cost is None or fraction is None else cost * fraction
    note = "" if fraction is None else f"触发价为成本的 {plain_percent(fraction)}"
    return _price_level("波段止损价", price, trigger, upward=False, note=note)


def _peak(position, price):
    stored = num(position.get("peak_price"))
    if stored is None:
        return None
    if price is None:
        return stored
    return max(stored, price)


def _ma200_note(score):
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    versus = num(tech.get("price_vs_ma200"))
    if versus is None:
        where = "200 日线位置暂缺"
    elif versus < 0:
        where = "当前低于 200 日线"
    else:
        where = "当前不低于 200 日线"
    return f"同时需低于 200 日线，{where}"


def _disaster(position, score, sell, price):
    fraction = num(sell.get("disaster_peak_fraction"))
    high = _peak(position, price)
    trigger = None if high is None or fraction is None else high * fraction
    return _price_level("灾难止损价", price, trigger, upward=False, note=_ma200_note(score))


def _stage(position):
    stage = num(position.get("stage"))
    if stage is None:
        return 0
    return int(stage)


def _flag(ok):
    return "满足" if ok else "未满足"


def _double(position, score, sell, price, index):
    cost = num(position.get("avg_cost"))
    multiple = num(sell.get("double_price"))
    trigger = None if cost is None or multiple is None else cost * multiple
    books = score.get("books") if isinstance(score.get("books"), dict) else {}
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    dev = num(tech.get("dev50"))
    timing = num(books.get("timing"))
    dev_limit = num(sell.get("double_dev50"))
    time_limit = num(sell.get("double_timing"))
    dev_ok = below(dev, dev_limit) if dev_limit is not None else False
    time_ok = below(timing, time_limit) if time_limit is not None else False
    either = dev_ok or time_ok
    last = num(position.get("last_sell_index"))
    gap_days = None if index is None or last is None else index - last
    interval = num(sell.get("profit_interval"))
    if gap_days is None or interval is None:
        wait_ok = False
        wait = "距上次卖出暂缺"
    else:
        wait_ok = gap_days >= interval
        wait = f"距上次卖出 {int(gap_days)} 天，至少 {int(interval)} 天，{_flag(wait_ok)}"
    stage_ok = _stage(position) == 0
    stage = "尚未减仓" if stage_ok else "已经减过仓"
    ready = either and wait_ok and stage_ok
    note = (
        f"距 50 日线当前 {score_text(dev)}，条件是低于 {score_text(dev_limit)}，{_flag(dev_ok)}；"
        f"择时分当前 {score_text(timing)}，条件是低于 {score_text(time_limit)}，{_flag(time_ok)}；"
        f"偏离或择时满足其一，当前{_flag(either)}；{wait}；{stage}，{_flag(stage_ok)}。"
        f"附加条件当前{_flag(ready)}"
    )
    row = _price_level("翻倍止盈价", price, trigger, upward=True, note=note)
    if row["risk_level"] is not None and not ready:
        row["risk_text"] += "。附加条件当前未满足"
    return row


def _tier_value(table, tier):
    if not isinstance(table, dict):
        return None
    return num(table.get(tier))


def _breakout(position, score, sell, index, panic):
    tier = position.get("tier_now")
    rule_days = _tier_value(sell.get("below_days"), tier)
    days = num(score.get("consec_below200"))
    shown = 0 if days is None or days <= 0 else int(days)
    if rule_days is None:
        head = f"破位减仓：连续 {shown} 天 → 门槛 {MISSING}"
    elif shown >= rule_days:
        head = f"破位减仓：连续 {shown} 天 → 门槛 {int(rule_days)} 天，已达到"
    else:
        head = f"破位减仓：连续 {shown} 天 → 门槛 {int(rule_days)} 天，还差 {int(rule_days) - shown} 天"
    tail = _break_gates(position, sell, index, panic) + _break_extras(position, score, sell)
    if tail:
        head += "；" + "；".join(tail)
    return _blank("破位减仓", head) | {"current": shown, "trigger": rule_days}


def _break_gates(position, sell, index, panic):
    """The same gates rule A uses before a breakout sale. The day count itself stays above."""
    if _stage(position) >= 2:
        return ["已经执行过，不再重复"]
    if panic:
        return ["恐慌模式下暂停"]
    entry = num(position.get("entry_index"))
    minimum = num(sell.get("minimum_age"))
    held = None if index is None or entry is None else index - entry
    if minimum is not None and (held is None or held < minimum):
        return [f"持有不足 {int(minimum)} 个交易日，暂不减仓"]
    return []


def _break_extras(position, score, sell):
    tier = position.get("tier_now")
    lines = score.get("red_lines") if isinstance(score.get("red_lines"), list) else []
    extras = []
    if tier == "normal" and "趋势破位" in lines:
        extras.append("趋势破位已出现")
    if tier == "normal":
        streak = num(score.get("consec_tim35")) or 0
        limit = num(sell.get("normal_timing_days"))
        if limit is not None and streak >= limit:
            extras.append(f"择时偏弱已连续 {int(streak)} 天")
    if tier == "attack":
        streak = num(score.get("consec_tim30")) or 0
        limit = num(sell.get("attack_timing_days"))
        if limit is not None and streak >= limit:
            extras.append(f"择时偏弱已连续 {int(streak)} 天")
    return extras


def _score_piece(label, value, floor):
    if value is None or floor is None:
        return f"{label}{MISSING} → 门槛 {score_text(floor)}", None
    gap = value - floor
    if gap < 0:
        return f"{label} {score_text(value)} < {score_text(floor)}", gap
    return f"{label} {score_text(value)} → 门槛 {score_text(floor)}，还差 {score_text(gap)} 分", gap


def _closest(gaps):
    known = [gap for gap in gaps if gap is not None]
    if not known:
        return None
    return min(known)


def _alert(position, score, sell, panic):
    books = score.get("books") if isinstance(score.get("books"), dict) else {}
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    quality, quality_gap = _score_piece("质量分", num(books.get("quality")), num(sell.get("normal_alert_quality")))
    growth, growth_gap = _score_piece("成长分", num(books.get("growth")), num(sell.get("normal_alert_growth")))
    dev = num(tech.get("dev50"))
    under = "距 50 日线为负" if dev is not None and dev < 0 else "距 50 日线不为负"
    fresh = _newer(score, position)
    version = "账本版本已更新" if fresh else "账本版本未更新"
    stage_ok = _stage(position) == 0
    stage = "尚未减仓" if stage_ok else "已经减过仓"
    text = f"警戒减仓：{quality}；{growth}；{under}；{version}；{stage}"
    hit = (
        fresh
        and stage_ok
        and dev is not None
        and dev < 0
        and any(gap is not None and gap < 0 for gap in (quality_gap, growth_gap))
    )
    band = None if not fresh or dev is None or dev >= 0 else score_band(_closest([quality_gap, growth_gap]))
    risk = None
    level_name = None
    if hit and panic:
        text += "。恐慌模式下暂停警戒减仓"
        risk = "恐慌模式下暂停警戒减仓"
        level_name = "orange"
    elif hit:
        text += "，已触发"
        pieces = [piece for piece, gap in ((quality, quality_gap), (growth, growth_gap)) if gap is not None and gap < 0]
        risk = "警戒减仓已触发：" + "；".join(pieces) + f"，{under}"
        level_name = "red"
    elif band is not None:
        risk = f"警戒减仓接近门槛：{quality}；{growth}；{under}"
        level_name = band
    return _blank("警戒减仓", text) | {"risk_level": level_name, "risk_text": risk}


def _newer(score, position):
    current = score.get("state_version")
    previous = position.get("entry_state")
    if current in (None, "") or previous in (None, ""):
        return False
    return str(current) > str(previous)


def _fundamental(position, score, sell):
    tier = position.get("tier_now")
    books = score.get("books") if isinstance(score.get("books"), dict) else {}
    quality, quality_gap = _score_piece(
        "质量分", num(books.get("quality")), _tier_value(sell.get("death_quality"), tier)
    )
    growth, growth_gap = _score_piece("成长分", num(books.get("growth")), _tier_value(sell.get("death_growth"), tier))
    reasons = []
    lines = score.get("red_lines") if isinstance(score.get("red_lines"), list) else []
    reasons.extend(line for line in lines if line in _DEATH_LINES)
    if score.get("fund_bad") is True:
        reasons.append("资金约束已触发")
    if tier == "attack" and below(num(score.get("rev_growth")), 0):
        reasons.append("营收增速为负")
    if tier == "attack" and "runway_ok" in score and score.get("runway_ok") is False:
        reasons.append("现金跑道不足")
    breaches = [piece for piece, gap in ((quality, quality_gap), (growth, growth_gap)) if gap is not None and gap < 0]
    text = f"基本面清仓：{quality}；{growth}"
    if reasons:
        text += "；" + "；".join(reasons)
    fired = reasons + breaches
    if fired:
        text += "，已触发"
        triggered = "基本面清仓已触发：" + "；".join(fired)
        return _blank("基本面清仓", text) | {"risk_level": "red", "risk_text": triggered}
    band = score_band(_closest([quality_gap, growth_gap]))
    risk = None
    if band is not None:
        risk = f"基本面清仓接近门槛：{quality}；{growth}"
    return _blank("基本面清仓", text) | {"risk_level": band, "risk_text": risk}
