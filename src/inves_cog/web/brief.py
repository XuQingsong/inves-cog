"""Investor brief pages. Simple derived values live only in this module."""

import re
from datetime import date, datetime, time, timedelta
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
PE_EXTREME = 300
SHORT_LAG_DAYS = 60
EPS_NEAR_ZERO = 0.05
NEWS_GAP = 1
STALE_NEWS_DAYS = 3
PENDING_GAP = 2
PRIOR_DAYS = 20
# Short interest is crowded only when the share is above 10% or cover days are above 5.
SHORT_CROWD_PCT = 10
SHORT_CROWD_DAYS = 5
SHORT_STALE_DAYS = 20
OPTION_STALE_SESSIONS = 2
OPTION_WINDOW = 20
# Ingest stores CBOE headings as category codes (adapters.cboe_statistics).
# total is "SUM OF ALL PRODUCTS"; equity is "EQUITY OPTIONS". The page says the Chinese name.
OPTION_CATEGORIES = (
    ("total", "全市场"),
    ("equity", "股票期权"),
)
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
    "卖出价位按持仓类型取卖出参数：翻倍止盈和灾难止损只用于进攻层核心，不套到每一只持仓。",
    "200日线 = 现价 / (1 + 距200日线百分比/100)。",
    "50日线 = 现价 / (1 + 距50日线百分比/100)。",
    "一年高点 = 现价 / (1 + 距一年高点百分比/100)。",
    "估值展示复制打分里的市盈率与估值输入，不重算，不展示中性价。",
    "轮动：罗素小盘减纳指100大于2个百分点，且上涨家数大于下跌家数。",
    "普跌：标普500小于等于-2%，且上涨家数/下跌家数小于0.5。",
    "其余为分化。",
    "距200日线、距一年高点、RSI、四本账直接取上游，页面不重算。",
    (
        "看跌/看涨比分位 = 最近 20 个交易日（含当日）里小于等于当日值的个数 / 20 × 100；"
        "高于 80 标偏谨慎，低于 20 标偏乐观。优先全市场，否则股票期权。"
    ),
    "VIX 优先用市场状态；为空时用截点前当日宏观数值，并注明来源。",
    "期权数据超过 2 个交易日为过期。",
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


def _eps_input(inputs):
    for key in ("eps", "eps_ttm", "trailing_eps", "eps_basic"):
        if key in inputs:
            return _number(inputs.get(key))
    return None


def plain_implied_reason(text):
    """Internal solver notes stay off the page."""
    if not text:
        return None
    raw = str(text)
    if "[-50,200]" in raw or "[-50, 200]" in raw:
        return "按现价反推的增速超出可解释范围"
    return raw


def pe_extreme(pe, eps):
    if pe is not None and pe > PE_EXTREME:
        return True
    return eps is not None and abs(eps) < EPS_NEAR_ZERO


def pe_phrase(pe, eps=None):
    if pe_extreme(pe, eps):
        return "市盈率不适用（盈利过低）"
    if pe is None:
        return MISSING
    return str(half_up(pe, 1))


def valuation_card(range_row, pe, price):
    """Copy payload fields for display. The fair price is never included."""
    payload = {} if range_row is None else _object(range_row.get("payload"))
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    neutral = None if range_row is None else _number(range_row.get("neutral"))
    eps = _eps_input(inputs)
    card = {
        "state": valuation_view(price, neutral)["status"],
        "pe": pe,
        "eps": eps,
        "pe_text": pe_phrase(pe, eps),
        "pe_extreme": pe_extreme(pe, eps),
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
        card["implied_reason"] = plain_implied_reason(payload.get("implied_reason"))
    if card["pe_extreme"]:
        card["implied_growth"] = None
    if range_row is not None and range_row.get("status") == "unvalued":
        reason = payload.get("reason")
        cause = str(reason) if isinstance(reason, str) and reason else MISSING
        card["state"] = "未估值"
        card["text"] = f"未估值（{cause}）"
        for key in ("pe", "pe_p25", "pe_p50", "pe_p75", "implied_growth", "rev_cagr_3y", "eps_growth", "eps"):
            card[key] = None
        card["implied_reason"] = None
        card["pe_text"] = MISSING
        card["pe_extreme"] = False
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


def _metric(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return _number(value)


def _visible_cap(day, moment):
    """A page for this session cannot show a later date, nor a date after the cutoff."""
    return min(day, moment.astimezone(NY).date())


def short_crowded(pct, days):
    """Strictly above either threshold. 10% and 5 days stay uncrowded."""
    return (pct is not None and pct > SHORT_CROWD_PCT) or (days is not None and days > SHORT_CROWD_DAYS)


def settlement_label(day):
    if day is None:
        return f"结算日{MISSING}"
    return f"{day.month}/{day.day} 结算"


def _recent_sessions(day, count):
    found = []
    cursor = day
    guard = 0
    while len(found) < count and guard < 800:
        if trading_day(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
        guard += 1
    found.reverse()
    return found


def option_percentile(today, samples):
    """Inclusive rank inside the 20-session window, as a percent. A short window stays blank."""
    if today is None or len(samples) != OPTION_WINDOW or any(value is None for value in samples):
        return None
    return sum(1 for value in samples if value <= today) / OPTION_WINDOW * 100


def option_tone(percentile):
    if percentile is None:
        return None
    if percentile > 80:
        return "偏谨慎"
    if percentile < 20:
        return "偏乐观"
    return None


def option_sentence(view):
    rank = MISSING if view["percentile"] is None else f"{int(half_up(view['percentile'], 0))} 分位"
    tone = f"，{view['tone']}" if view.get("tone") else ""
    return f"{format_ratio(view['value'])}（{view['label']}），近 20 个交易日 {rank}{tone}"


def option_status(rows, day):
    """Session age. More than 2 trading days since the latest print is stale."""
    dates = [
        row["trade_date"] for row in rows if row["trade_date"] <= day and _metric(row.get("put_call_ratio")) is not None
    ]
    if not dates:
        return MISSING, None
    latest = max(dates)
    state = "过期" if session_gap(latest, day) > OPTION_STALE_SESSIONS else "新鲜"
    return state, f"最近 {latest.month}/{latest.day}"


def _change_percent(raw):
    if not isinstance(raw, dict):
        return None
    return _metric(raw.get("changePercent"))


def _load_option_rows(connection, cap):
    codes = [code for code, _label in OPTION_CATEGORIES]
    return _rows(
        connection,
        """
        SELECT trade_date, category, put_call_ratio
        FROM ingest.options_stats
        WHERE trade_date <= %s AND category = ANY(%s)
        """,
        (cap, codes),
    )


def _option_view(rows, day):
    by_category = {}
    for row in rows:
        if row["trade_date"] > day:
            continue
        ratio = _metric(row.get("put_call_ratio"))
        if ratio is None:
            continue
        by_category.setdefault(row["category"], {})[row["trade_date"]] = ratio
    chosen = label = None
    for code, name in OPTION_CATEGORIES:
        if day in (by_category.get(code) or {}):
            chosen, label = code, name
            break
    if chosen is None:
        return None
    series = by_category[chosen]
    samples = [series.get(session) for session in _recent_sessions(day, OPTION_WINDOW)]
    today = series[day]
    percentile = option_percentile(today, samples)
    view = {
        "category": chosen,
        "label": label,
        "value": today,
        "percentile": percentile,
        "tone": option_tone(percentile),
    }
    view["text"] = option_sentence(view)
    return view


VIX_SERIES = [("VIX_CBOE", "CBOE"), ("VIX_YAHOO", "Yahoo"), ("VIXCLS", "FRED")]
VIX3M_SERIES = [("VIX3M_CBOE", "CBOE"), ("VIX3M_YAHOO", "Yahoo")]


def _series_latest(connection, series, cap):
    """Latest visible observation across the series set.

    The newest observation_date wins; the series preference order only breaks
    same-date ties, so a stale high-preference series never shadows a newer one.
    """
    best = None
    for order, (series_id, label) in enumerate(series):
        row = _one(
            connection,
            """
            SELECT value, observation_date
            FROM ingest.macro_observations
            WHERE series_id = %s AND observation_date <= %s AND realtime_start <= %s
            ORDER BY observation_date DESC, realtime_start DESC
            LIMIT 1
            """,
            (series_id, cap, cap),
        )
        if row is None or row["value"] is None:
            continue
        candidate = (row["observation_date"], -order, _metric(row["value"]), label, row["observation_date"])
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None, None, None
    return best[2], best[3], best[4]


VIX_STALE_SESSIONS = 3


def _series_today(connection, series, day, cap):
    """Same-day observation in preference order."""
    for series_id, label in series:
        row = _one(
            connection,
            """
            SELECT value
            FROM ingest.macro_observations
            WHERE series_id = %s AND observation_date = %s AND realtime_start <= %s
            ORDER BY realtime_start DESC
            LIMIT 1
            """,
            (series_id, day, cap),
        )
        if row is not None and row["value"] is not None:
            return _metric(row["value"]), label, day
    return None, None, None


def _vix_resolve(connection, day, cap):
    """VIX: same-day CBOE -> Yahoo -> FRED; else latest visible with as-of + stale flag."""
    value, source, asof = _series_today(connection, VIX_SERIES, day, cap)
    if value is not None:
        return value, source, asof, False
    value, source, asof = _series_latest(connection, VIX_SERIES, cap)
    stale = asof is not None and session_gap(asof, day) > VIX_STALE_SESSIONS
    return value, source, asof, stale


def _vix3m_resolve(connection, day, cap):
    value, source, asof = _series_today(connection, VIX3M_SERIES, day, cap)
    if value is not None:
        return value, source, asof, False
    value, source, asof = _series_latest(connection, VIX3M_SERIES, cap)
    stale = asof is not None and session_gap(asof, day) > VIX_STALE_SESSIONS
    return value, source, asof, stale


def sell_params(version):
    path = PARAMS_ROOT / version / "m4.yaml"
    loaded = yaml.safe_load(path.read_text())
    return loaded["m4"]["sell"]


def swing_params(version):
    path = PARAMS_ROOT / version / "m4.yaml"
    loaded = yaml.safe_load(path.read_text())
    return loaded["m4"]["swing"]


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


def format_points_plain(value, digits):
    """Percent points already scaled, without a sign. One place for the short column."""
    if value is None:
        return MISSING
    number = half_up(value, digits)
    return f"{number:.{digits}f}%"


def format_points_signed(value, digits):
    """Percent points already scaled. Positive keeps a plus; negative uses the mockup minus."""
    if value is None:
        return MISSING
    number = half_up(value, digits)
    body = f"{abs(number):.{digits}f}%"
    if number < 0:
        return f"−{body}"
    if number > 0:
        return f"+{body}"
    return body


def format_days(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 1):.1f}"


def format_ratio(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 2):.2f}"


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
        SELECT ticker, trade_date, volume, close, adj_factor
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
    """News published in the ET session, regardless of when it was stored.

    The rules layer needs the raw headline, url and first_seen_at; 'late'
    marks items stored after the page cutoff (事后补采).
    """
    start, end = _day_window(day)
    rows = _rows(
        connection,
        """
        SELECT info_id, published_at, first_seen_at, source, headline, tickers, url, extraction_source
        FROM ingest.info_items
        WHERE kind = 'news' AND published_at >= %s AND published_at < %s
        ORDER BY published_at DESC, info_id
        """,
        (start, end),
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
                "late": seen is not None and seen > cutoff,
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
    current = _one(
        connection,
        """
        SELECT portfolio_id, trade_date, cash, equity, peak_equity, state, observed_at
        FROM trading.ledger
        WHERE trade_date = %s AND observed_at < %s
        ORDER BY observed_at DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    if current is not None:
        found = dict(current)
        found["carried_from"] = None
        return found
    prior = _one(
        connection,
        """
        SELECT portfolio_id, trade_date, cash, equity, peak_equity, state, observed_at
        FROM trading.ledger
        WHERE trade_date < %s AND observed_at < %s
        ORDER BY trade_date DESC, observed_at DESC
        LIMIT 1
        """,
        (day, cutoff),
    )
    if prior is None:
        return None
    found = dict(prior)
    found["carried_from"] = prior["trade_date"]
    return found


def _pending(connection, day, portfolio):
    if not portfolio:
        return []
    return _rows(
        connection,
        """
        SELECT order_id, ticker, side, kind, status, reason_zh, trade_date, signal_date, qty
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


def _sell_history(plans, state, fills=None):
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
                        "qty": order.get("qty"),
                        "fill_price": None,
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
                    "qty": item.get("qty") or item.get("shares"),
                    "fill_price": item.get("fill_price") or item.get("price"),
                }
            )
    by_key = {}
    for row in fills or []:
        by_key.setdefault((str(row.get("trade_date")), row.get("ticker")), []).append(row)
    for item in found:
        matches = by_key.get((str(item.get("trade_date")), item.get("ticker"))) or []
        match = matches.pop(0) if matches else None
        item["fill_state"] = ORDER_STATE.get(None if match is None else match.get("status"), "计划")
        if match is not None and match.get("status") == "filled":
            item["fill_price"] = match.get("fill_price")
            item["qty"] = match.get("qty")
            item["source"] = "filled"
    return _collapse_plans(found)


ORDER_STATE = {
    None: "计划",
    "filled": "已成交",
    "pending": "待成交",
    "expired": "过期未成交",
    "superseded": "被新计划替代",
    "canceled": "已取消",
    "blocked": "未执行",
}


def _collapse_plans(rows):
    """Same day, ticker, reason and kind is one decision: keep one line, prefer the order outcome, mark ×N."""
    grouped = []
    index = {}
    for row in rows:
        key = (str(row.get("trade_date")), row.get("ticker"), row.get("reason_zh"), row.get("kind"))
        if key not in index:
            index[key] = len(grouped)
            grouped.append({**row, "repeat": 1})
            continue
        kept = grouped[index[key]]
        kept["repeat"] += 1
        if kept.get("fill_state") == "计划" and row.get("fill_state") != "计划":
            grouped[index[key]] = {**row, "repeat": kept["repeat"]}
    return grouped


def _filled_orders(connection, portfolio, day):
    if not portfolio:
        return [], True
    try:
        rows = _rows(
            connection,
            """
            SELECT ticker, qty, fill_price, trade_date, reason_zh, status
            FROM trading.orders
            WHERE portfolio_id = %s AND trade_date <= %s
            ORDER BY trade_date, (status = 'filled') DESC, order_id
            """,
            (portfolio, day),
        )
    except Exception as exc:
        if exc.__class__.__name__ == "InsufficientPrivilege":
            return [], False
        raise
    return rows, True


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


def _statuses(fresh, vix, vix_stale, overlay, pending_late, plan, valuation_status):
    vix_state = MISSING if vix is None else ("过期" if vix_stale else "已有")
    return [
        {"item": "新闻", "state": "新鲜" if fresh else "缺失"},
        {"item": "VIX", "state": vix_state},
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
    # B-064: before today's close exists, close-derived cards carry the prior
    # trading day's snapshot; news/calendar stay on `day`.
    carry_from = None
    if day == clock.today_trade_date():
        has_close = _one(
            connection,
            "SELECT 1 AS x FROM marketstate.daily WHERE trade_date = %s AND session = 'close' LIMIT 1",
            (day,),
        )
        if has_close is None:
            prior = _one(
                connection,
                "SELECT MAX(trade_date) AS d FROM marketstate.daily WHERE trade_date < %s AND session = 'close'",
                (day,),
            )
            carry_from = None if prior is None else prior["d"]
    data_day = carry_from or day
    daily, _daily_post = _by_session(
        _rows(
            connection,
            """
            SELECT ticker, session, ret
            FROM marketstate.daily
            WHERE trade_date = %s
            """,
            (data_day,),
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
            (data_day, ["index", "style", "sector", "l3"]),
        ),
        lambda row: (row["group_kind"], row["group_id"]),
    )
    rotation = list(rotation_close.values())
    market = _one(connection, "SELECT * FROM marketstate.market WHERE trade_date = %s", (data_day,))
    anomalies = _anomalies(connection, day, cutoff)
    events = _events(connection, anomalies, cutoff)
    scores = _scores(connection, data_day)
    ranges = _ranges(connection, data_day, cutoff)
    ledger = _book(connection, data_day, cutoff)
    portfolio = None if ledger is None else ledger["portfolio_id"]
    state = _state(ledger)
    positions = _positions(state)
    bars = _bars(connection, data_day, list(dict.fromkeys([*pool, *positions])))
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
    swing = swing_params(version)
    cap = _visible_cap(day, cutoff)
    option_rows = _load_option_rows(connection, cap)
    option_state, option_detail = option_status(option_rows, day)
    resolved_vix, vix_source, vix_asof, vix_stale = _vix_resolve(connection, day, cap)
    vix3m, vix3m_source, vix3m_asof, vix3m_stale = _vix3m_resolve(connection, day, cap)
    option = _option_view(option_rows, day)
    option_latest = max((row["trade_date"] for row in option_rows if row["trade_date"] <= day), default=None)
    option_stale = option_latest is not None and session_gap(option_latest, day) > OPTION_STALE_SESSIONS
    # News rules layer: classify every item stored for this session.
    from inves_cog.perception.news.rules import rank_day

    held_set = set(positions)
    news_ranked = rank_day(
        news_items,
        set(pool) | held_set,
        held_set,
        day,
    )
    translations = _translations(connection, [n["info_id"] for n in news_ranked])
    for n in news_ranked:
        zh = translations.get(n["info_id"])
        if zh:
            n["title_zh"] = zh
    technicals = _technicals(bars, data_day)
    earnings = _earnings_calendar(connection, day)
    econ = _econ_calendar(connection, day)
    intraday = _intraday(connection, day)
    return {
        "day": day,
        "carry_from": carry_from,
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
        "swing": swing,
        "shorts": {},
        "short_future": False,
        "short_state": None,
        "short_detail": None,
        "option_rows": option_rows,
        "option": None if option_stale else option,
        "option_state": option_state,
        "option_detail": option_detail,
        "vix": resolved_vix,
        "vix_source": vix_source,
        "vix_asof": vix_asof,
        "vix_stale": vix_stale,
        "vix3m_fb": vix3m,
        "vix3m_source": vix3m_source,
        "vix3m_asof": vix3m_asof,
        "vix3m_stale": vix3m_stale,
        "news_ranked": news_ranked,
        "technicals": technicals,
        "earnings_cal": earnings,
        "econ_cal": econ,
        "intraday": intraday,
    }, None


def _index_closes(connection, day):
    history = _bars(connection, day, ["SPY", "QQQ", "IWM"])
    found = {}
    for ticker, rows in history.items():
        closes = [float(row["close"]) for row in rows if row["close"] is not None][-20:]
        if len(closes) >= 2:
            found[ticker] = closes
    return found


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
    ret = None if ticker not in daily else daily[ticker]["ret"]
    if ret is None:
        close, previous = _session_closes(history, day)
        if close is not None and previous not in (None, 0):
            ret = close / previous - 1
    return {
        "ticker": ticker,
        "ret": ret,
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
            member["tech"] = context["technicals"].get(ticker)
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


def _holding_row(ticker, position, stock, sell, pending, plan_payload, valuation, context):
    from inves_cog.web.exit_levels import build_levels, holding_kind, merged_score

    price = stock["price"]
    state = context.get("state") if isinstance(context.get("state"), dict) else {}
    ledger = state.get("scores") if isinstance(state.get("scores"), dict) else {}
    page_scores = context.get("scores") if isinstance(context.get("scores"), dict) else {}
    score = merged_score(page_scores.get(ticker), ledger.get(ticker))
    levels = build_levels(
        position,
        score,
        sell,
        context.get("swing") or {},
        price=price,
        index=_number(state.get("index")),
        panic=state.get("panic") is True,
    )
    avg_cost = _number(position.get("avg_cost"))
    pnl = None if price is None or avg_cost in (None, 0) else price / avg_cost - 1
    kind = holding_kind(position)
    tech = score.get("tech") if isinstance(score.get("tech"), dict) else {}
    distance = stock.get("price_vs_ma200")
    if distance is None:
        distance = _number(tech.get("price_vs_ma200"))
    ma200 = None if kind == "观察波段仓" else level(price, distance)
    levels = _mark_pending(levels, [row for row in pending if row["ticker"] == ticker])
    return {
        "ticker": ticker,
        "kind_label": kind,
        "shares": position.get("shares"),
        "avg_cost": avg_cost,
        "price": price,
        "pnl": pnl,
        "day": stock.get("ret"),
        "ma200": ma200,
        "levels": levels,
        "ruler": _ruler_inputs(kind, price, avg_cost, levels, ma200),
        "next_step": _next_step(ticker, pending, plan_payload),
        "pending": [row["order_id"] for row in pending if row["ticker"] == ticker],
        "books": stock["books"],
        "valuation": valuation,
    }


def _mark_pending(levels, orders):
    """An order already in the book means the rule fired; the card says it waits for the fill."""
    if not orders:
        return levels
    marked = []
    for row in levels:
        name = str(row.get("name") or "").removesuffix("价")
        hit = next((order for order in orders if name and name in str(order.get("reason_zh") or "")), None)
        if hit is not None and row.get("status") in (None, "none"):
            since = hit.get("signal_date") or hit.get("trade_date")
            since_text = since.isoformat() if hasattr(since, "isoformat") else str(since)
            row = {**row, "status": "pending", "pending_note": f"已触发；订单 {since_text} 起待成交，不等于已成交"}
        marked.append(row)
    return marked


def _ruler_inputs(kind, price, cost, levels, ma200):
    stop = None
    targets = []
    for row in levels:
        trigger = row.get("trigger")
        if trigger is None:
            continue
        name = row.get("name") or ""
        if name in {"灾难止损价", "波段止损价"} and stop is None:
            stop = {"n": name.removesuffix("价"), "p": trigger}
        if name in {"翻倍止盈价", "波段止盈价", "波段部分止盈价"}:
            targets.append({"n": name.removesuffix("价"), "p": trigger, "reached": row.get("gap") == 0})
    return {
        "type": kind,
        "px": price,
        "cost": cost,
        "ma200": None if kind == "观察波段仓" else ma200,
        "stop": stop,
        "tp": targets,
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
    vix = context["vix"]
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
    _wmovers = _wide_movers(connection, day)
    _wm = {"up": _wmovers[:5], "down": sorted(_wmovers, key=lambda r: r["ret"])[:5]}
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
        "vix_source": context["vix_source"],
        "put_call": context["option"],
        "put_call_text": MISSING if context["option"] is None else context["option"]["text"],
        "vix3m": context["vix3m_fb"],
        "vix3m_prev": _previous_vix3m(connection, day),
        "down_share_5d_pct": None if market is None else market["down_share_5d_pct"],
        "spy_drawdown_252_pct": None if market is None else market["spy_drawdown_252_pct"],
        "index_closes": _index_closes(connection, day),
        "member_rets": {
            ticker: context["daily"][ticker]["ret"]
            for row in events
            for ticker in row.get("members") or []
            if ticker in context["daily"]
        },
        "held_tickers": sorted(context["positions"]),
        "events": events,
        "news_fresh": context["fresh"],
        "carry_from": context["carry_from"],
        "is_today": context["day"] == clock.today_trade_date(),
        "intraday": context["intraday"],
        "news_modules": _news_views(context),
        "wide_movers_up": _wm["up"],
        "wide_movers_down": _wm["down"],
        "earnings": _earnings_modules(
            context["earnings_cal"], day, context["pool"], set(context["positions"]), context["news_ranked"]
        ),
        "econ": _econ_module(context["econ_cal"]),
        "vix_asof": context["vix_asof"],
        "vix_stale": context["vix_stale"],
        "vix3m_source": context["vix3m_source"],
        "vix3m_asof": context["vix3m_asof"],
        "vix3m_stale": context["vix3m_stale"],
        "implication": implication,
        "pool_count": len(context["pool"]),
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    } | _risk_fields(connection, day, context)


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
            _holding_row(
                ticker,
                position,
                stock,
                context["sell"],
                context["pending"],
                plan_payload,
                stock["valuation"],
                context,
            )
        )
    held = set(context["positions"])
    candidates = []
    for ticker, score in sorted(context["scores"].items()):
        if ticker in held or not score["entry_pass"] or ticker not in set(context["pool"]):
            continue
        stock = themes.get(ticker) or _member(ticker, day, context["bars"], score, context["daily"], False, [])
        if "valuation" not in stock:
            stock["valuation"] = _card_for(context, ticker, score, stock["price"])
        row = _candidate_row(stock, stock["valuation"])
        row["sector"] = context["catalog"]["sector_of"].get(ticker)
        row["ret"] = stock.get("ret")
        candidates.append(row)
    ledger = context["ledger"]
    equity = None if ledger is None else ledger["equity"]
    cash = None if ledger is None else ledger["cash"]
    peak = None if ledger is None else ledger["peak_equity"]
    previous = _previous_equity(connection, day, context["cutoff"], context["portfolio"])
    day_change = None if equity is None or previous in (None, 0) else equity / previous - 1
    estimate = close_estimate(context, day)
    if isinstance(estimate, dict):
        marked, pnl = _number(estimate.get("equity")), _number(estimate.get("day_pnl"))
        base = None if marked is None or pnl is None else marked - pnl
        day_change = None if base in (None, 0) else pnl / base
    pending_rows = sum(1 for row in holdings if str(row["next_step"]).startswith("待成交"))
    sentence = f"持仓{len(holdings)}只，待成交{pending_rows}笔。"
    fills, fills_readable = _filled_orders(connection, context["portfolio"], day)
    carried = None if ledger is None else ledger.get("carried_from")
    packed = _risk_fields(connection, day, context, holdings)
    marked = packed["risk_card"].get("drawdown")
    return {
        "page": "/account",
        "date": day,
        "title": "纸面账户",
        "oneliner": sentence,
        "headings": ["今天先看这些", "组合边界", "持仓与关键价位", "待成交", "处置记录", "待选股票"],
        "equity": equity,
        "cash": cash,
        "peak_equity": peak,
        "day_change": day_change,
        "drawdown": marked,
        "close_estimate": estimate,
        "plan_missing": carried is not None,
        "carried_from": None if carried is None else carried.isoformat(),
        "holdings": holdings,
        "pending_orders": [
            {
                "ticker": row["ticker"],
                "side": row.get("side"),
                "reason": row.get("reason_zh"),
                "since": row.get("signal_date") or row.get("trade_date"),
                "trade_date": row.get("trade_date"),
                "qty": row.get("qty"),
            }
            for row in context["pending"]
        ],
        "closed_records": _sell_history(context["plans"], context["state"], fills if fills_readable else None),
        "fills_readable": fills_readable,
        "candidates": candidates,
        "params_version": context["version"],
        "sell": {
            "double_price": context["sell"]["double_price"],
            "disaster_peak_fraction": context["sell"]["disaster_peak_fraction"],
            "below_days": dict(context["sell"]["below_days"]),
        },
        "earnings_near": _account_earnings_near(context, day),
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    } | packed


def _account_earnings_near(context, day):
    mods = _earnings_modules(
        context["earnings_cal"], day, context["pool"], set(context["positions"]), context["news_ranked"]
    )
    return [] if mods is None else mods["near"]


def _risk_fields(connection, day, context, holdings=None):
    from inves_cog.web.risk_brief import RISK_FORMULAS, portfolio_view

    view = portfolio_view(connection, day, context)
    if holdings is not None:
        for row in holdings:
            found = view["by_ticker"].get(row["ticker"])
            row["risk_level"] = None if found is None else found["level"]
    return {
        "risk_lines": view["lines"],
        "take_profits": view["take_profits"],
        "down_red": view["down_red"],
        "down_orange": view["down_orange"],
        "risk_note": view["note"],
        "risk_card": view["card"],
        "formulas": [*FORMULAS, *RISK_FORMULAS],
    }


def _anomalies_found(context):
    items = []
    future = context.get("short_future") or []
    if future:
        shown = "、".join(f"{row['ticker']} {row['settlement'].isoformat()}" for row in future)
        items.append(
            {
                "title": f"空头结算日晚于页面日期：{shown}",
                "detail": "这些记录没有写入页面上的空头占比。",
            }
        )
    lagging = sorted(
        (ticker, view["settlement"])
        for ticker, view in (context.get("shorts") or {}).items()
        if isinstance(view.get("settlement"), date) and (context["day"] - view["settlement"]).days > SHORT_LAG_DAYS
    )
    if lagging:
        shown = "、".join(f"{ticker} {when.isoformat()}" for ticker, when in lagging)
        items.append(
            {
                "title": f"空头数据停更：{shown}",
                "detail": f"最近一期结算距页面日期超过 {SHORT_LAG_DAYS} 天，页面标为过期，不判断空头拥挤。",
            }
        )
    for ticker, score in sorted(context["scores"].items()):
        card = _card_for(context, ticker, score, _ticker_price(context, ticker))
        if card.get("pe_extreme"):
            items.append(
                {
                    "title": f"{ticker} 市盈率不适用（盈利过低）",
                    "detail": "盈利过低或市盈率超过 300，页面不显示该倍数。",
                }
            )
        if card.get("implied_reason") == "按现价反推的增速超出可解释范围":
            items.append(
                {
                    "title": f"{ticker} 隐含增速超出可解释范围",
                    "detail": card["implied_reason"],
                }
            )
    for row in _sell_history(context["plans"], context["state"]):
        if row.get("repeat", 1) > 1:
            items.append(
                {
                    "title": f"{row.get('ticker')} {row.get('trade_date')} 有 {row['repeat']} 条相同计划",
                    "detail": "同一天、同一代码、同一原因已合并，次数标在记录上。",
                }
            )
    return items


def page_brief_trust(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    vix = context["vix"]
    late = any(session_gap(row["trade_date"], day) > PENDING_GAP for row in context["pending"])
    valuation_state = _valuation_status(context["scores"], context["ranges"], context["bars"])
    statuses = _statuses(
        context["fresh"],
        vix,
        context["vix_stale"],
        _overlay_present(connection, day, context["cutoff"]),
        late,
        context["plan"],
        valuation_state,
    )
    statuses.append({"item": "期权数据", "state": context["option_state"], "detail": context["option_detail"]})
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
    gap_states = {"缺失", "警示", "过期", MISSING, "未上线/缺失", "模型不适用"}
    if any(item["state"] in gap_states for item in statuses):
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
        "anomalies": _anomalies_found(context),
        "formulas": list(FORMULAS),
        "label": PAPER_LABEL,
    }


def _technicals(bars, day):
    """Perception technicals per ticker on adjusted closes up to `day`."""
    from inves_cog.perception.technical import technicals

    found = {}
    for ticker, rows in bars.items():
        history = [row for row in rows if row["trade_date"] <= day and row["close"] is not None]
        closes = [float(row["close"]) * (float(row["adj_factor"]) if row.get("adj_factor") else 1.0) for row in history]
        volumes = [float(row["volume"]) if row["volume"] is not None else 0.0 for row in history]
        found[ticker] = technicals(closes, volumes)
    return found


def _table_exists(connection, name):
    row = _one(connection, "SELECT to_regclass(%s) AS t", (name,))
    return row is not None and row["t"] is not None


def _earnings_calendar(connection, day):
    if not _table_exists(connection, "ingest.earnings_calendar"):
        return None
    rows = _rows(
        connection,
        """
        SELECT ticker, report_date, time, eps_forecast, n_estimates, market_cap, company
        FROM ingest.earnings_calendar
        WHERE report_date > %s AND report_date <= %s + 14
        ORDER BY report_date, ticker
        """,
        (day, day),
    )
    return rows


def _econ_calendar(connection, day):
    if not _table_exists(connection, "ingest.econ_calendar"):
        return None
    rows = _rows(
        connection,
        """
        SELECT event_date, event_time_et, country, name, actual, consensus, previous
        FROM ingest.econ_calendar
        WHERE event_date > %s AND event_date <= %s + 14
        ORDER BY event_date, event_time_et
        """,
        (day, day),
    )
    return rows


def _intraday(connection, day):
    """Latest intraday snapshot per ticker for `day` (A-024 contract)."""
    if not _table_exists(connection, "ingest.intraday_snapshots"):
        return {}
    start, end = _day_window(day)
    rows = _rows(
        connection,
        """
        SELECT DISTINCT ON (ticker) ticker, as_of, session, last, prev_close, delay_minutes
        FROM ingest.intraday_snapshots
        WHERE as_of >= %s AND as_of < %s
        ORDER BY ticker, as_of DESC
        """,
        (start, end),
    )
    return {row["ticker"]: dict(row) for row in rows}


def _translations(connection, info_ids):
    if not info_ids or not _table_exists(connection, "perception.news_translations"):
        return {}
    rows = _rows(
        connection,
        "SELECT info_id, title_zh FROM perception.news_translations WHERE info_id = ANY(%s)",
        (info_ids,),
    )
    return {row["info_id"]: row["title_zh"] for row in rows}


WARRANT_SUFFIX = re.compile(r"^[A-Z]+[WUR]$")


def _wide_movers(connection, day):
    """Whole-market movers: price >= $5, ADV20 >= $20M, no warrants/units."""
    rows = _rows(
        connection,
        """
        WITH t AS (SELECT ticker, close, adj_factor FROM ingest.bars_daily WHERE trade_date = %(day)s),
        p AS (SELECT DISTINCT ON (ticker) ticker, close, adj_factor FROM ingest.bars_daily
              WHERE trade_date < %(day)s AND trade_date >= %(day)s - 10 ORDER BY ticker, trade_date DESC),
        u AS (SELECT ticker, mktcap, adv20 FROM ingest.wide_universe WHERE trade_date = %(day)s AND included)
        SELECT t.ticker, t.close, p.close AS prev_close, t.close / p.close - 1 AS ret, u.mktcap, u.adv20
        FROM t JOIN p USING (ticker) JOIN u USING (ticker)
        WHERE t.close >= 5 AND u.adv20 >= 20000000 AND t.adj_factor IS NOT DISTINCT FROM p.adj_factor
        ORDER BY ret DESC
        """,
        {"day": day},
    )
    names = {row["ticker"] for row in rows}
    clean = [row for row in rows if not (WARRANT_SUFFIX.match(row["ticker"]) and row["ticker"][:-1] in names)]
    return clean


def _money_cap(value):
    return None if value is None else float(value)


def _earnings_modules(earnings, day, pool, held, ranked):
    """Prototype calendar rules: dedupe same company (keep alphabetically-last
    symbol), week = top 10 by market cap (then sort by date), mine = pool/held
    within the next 10 calendar days, previews attach by primary ticker."""
    if earnings is None:
        return None
    from inves_cog.perception.news.rules import ECON_KEY  # noqa: F401  (kept for parity)

    seen = {}
    for row in earnings:
        symbol = row["ticker"]
        name = row.get("company") or symbol
        key = (name, row["report_date"])
        if key in seen and (symbol or "") <= (seen[key]["ticker"] or ""):
            continue
        seen[key] = row
    items = list(seen.values())
    week_pool = sorted(
        (r for r in items if day < r["report_date"] <= day + timedelta(days=8)),
        key=lambda r: -(_money_cap(r.get("market_cap")) or 0),
    )[:10]
    week = sorted(week_pool, key=lambda r: (r["report_date"], -(_money_cap(r.get("market_cap")) or 0)))
    universe = set(pool) | set(held)
    mine = []
    for r in sorted(items, key=lambda x: x["report_date"]):
        if r["ticker"] not in universe or not (day < r["report_date"] <= day + timedelta(days=10)):
            continue
        previews = [n for n in ranked if "财报前瞻" in n["rule"].tags and r["ticker"] in n["rule"].primary_tickers][:3]
        mine.append({**r, "held": r["ticker"] in held, "previews": previews})
    return {"week": week, "mine": mine, "near": _earnings_near(items, day, held)}


def _earnings_near(items, day, held):
    return sorted(
        (r for r in items if r["ticker"] in held and 0 < session_gap(day, r["report_date"]) <= 3),
        key=lambda r: r["report_date"],
    )


def _econ_module(econ):
    if econ is None:
        return None
    from inves_cog.perception.news.rules import ECON_KEY

    out, seen = [], set()
    for row in econ:
        if row.get("country") != "United States" or not ECON_KEY.search(row.get("name") or ""):
            continue
        key = (row["event_date"], row.get("name"), row.get("event_time_et"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    out.sort(key=lambda r: (r["event_date"], str(r.get("event_time_et") or "")))
    return out[:8]


def _news_views(context):
    """Market-page news modules from the ranked rules layer."""
    ranked = context["news_ranked"]
    tech = context["technicals"]
    grouped = context["grouped"]
    theme_map = {t: sector for sector in grouped for t in grouped[sector]}
    held = set(context["positions"])
    members = {}
    for sector in grouped:
        for t in grouped[sector]:
            ret = context["daily"].get(t, {}).get("ret")
            member = {"ticker": t, "theme": sector, "ret": ret, "vol": None, "held": t in held, "tech": tech.get(t)}
            members[t] = member
    # volume multiples from bars
    for t, m in members.items():
        history = context["bars"].get(t) or []
        today_rows = [r for r in history if r["trade_date"] == context["day"]]
        prior = [r["volume"] for r in history if r["trade_date"] < context["day"] and r["volume"] is not None]
        today_volume = today_rows[-1]["volume"] if today_rows else None
        m["vol"] = volume_multiple(today_volume, prior)
        if m["ret"] is None:
            close, prev = _session_closes(history, context["day"])
            if close is not None and prev not in (None, 0):
                m["ret"] = close / prev - 1
    top8 = sorted((m for m in members.values() if m["ret"] is not None), key=lambda m: -abs(m["ret"]))[:8]
    for m in top8:
        own = sorted(
            (n for n in ranked if m["ticker"] in n["rule"].primary_tickers),
            key=lambda n: (-n["rule"].importance, n["published"]),
        )
        m["news"] = own[:1]
        m["has_news"] = bool(own)
    # hot themes
    by_theme = {}
    for n in ranked:
        if n["rule"].weak_rating_only:
            continue
        theme = _news_theme(n, theme_map, held)
        if theme:
            by_theme.setdefault(theme, []).append(n)
    pick = []
    for theme, items in sorted(by_theme.items(), key=lambda kv: (-max(i["rule"].importance for i in kv[1]), kv[0])):
        items.sort(key=lambda n: (-n["rule"].importance, n["published"]))
        pick.extend({"theme": theme, **n} for n in items[:1])
    pick.sort(
        key=lambda n: (-n["rule"].held, -n["rule"].importance, -(n["published"].timestamp() if n["published"] else 0))
    )
    from inves_cog.perception.news.rules import feed_keep, group_weak_ratings

    feed = group_weak_ratings([n for n in ranked if feed_keep(n["rule"], held)])[:40]
    movers_down = sorted((m for m in members.values() if m["ret"] is not None), key=lambda m: m["ret"])
    return {
        "movers": top8,
        "theme_news": pick[:8],
        "feed": feed,
        "pool_leaders_down": movers_down[:5],
        "pool_leaders_up": movers_down[-5:][::-1],
    }


def _news_theme(item, theme_map, held):
    from inves_cog.perception.news.rules import theme_of

    return theme_of(item, theme_map, held)
