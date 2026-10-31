"""Investor brief pages. Simple derived values live only in this module."""

import re
import statistics
import sys
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


def _scores(connection, day, carry=False):
    """Day's scores; with carry=True also fills missing tickers from each one's
    most recent earlier score (B-068: no today score before close)."""
    rows = _rows(
        connection,
        """
        SELECT ticker, tech, derived, quality, growth, valuation, timing, entry_pass, tier
        FROM trading.daily_scores
        WHERE signal_date = %s
        """,
        (day,),
    )
    out = {row["ticker"]: row for row in rows}
    if carry:
        older = _rows(
            connection,
            """
            SELECT DISTINCT ON (ticker) ticker, tech, derived, quality, growth, valuation, timing,
                   entry_pass, tier, signal_date
            FROM trading.daily_scores
            WHERE signal_date < %s
            ORDER BY ticker, signal_date DESC
            """,
            (day,),
        )
        for row in older:
            row["carried_from"] = row["signal_date"]
            out.setdefault(row["ticker"], row)
    return out


def _ranges(connection, day, cutoff, carry=False):
    rows = _rows(
        connection,
        """
        SELECT ticker, neutral, status, payload
        FROM valuation_v1.ranges
        WHERE trade_date = %s AND observed_at < %s
        """,
        (day, cutoff),
    )
    out = {row["ticker"]: row for row in rows}
    if carry:
        older = _rows(
            connection,
            """
            SELECT DISTINCT ON (ticker) ticker, neutral, status, payload, trade_date
            FROM valuation_v1.ranges
            WHERE trade_date < %s AND observed_at < %s
            ORDER BY ticker, trade_date DESC
            """,
            (day, cutoff),
        )
        for row in older:
            row["carried_from"] = row["trade_date"]
            out.setdefault(row["ticker"], row)
    return out


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


def _column_exists(connection, table, column):
    try:
        row = _one(
            connection,
            "SELECT 1 AS x FROM information_schema.columns"
            " WHERE table_schema=%s AND table_name=%s AND column_name=%s LIMIT 1",
            (table.split(".")[0], table.split(".")[1], column),
        )
    except Exception:
        return False
    return row is not None


def _news_events(connection, day, is_today, clock=None):
    """Events whose first_seen falls in the cause window: previous trading
    session 16:00 ET -> now (today) or that day's 20:00 ET (historical).
    Missing/empty table -> {} (the role may not have the migration yet)."""
    if not _table_exists(connection, "perception.news_events"):
        return {}
    from inves_cog.ingest.intraday import previous_session

    prev = previous_session(day)
    start = datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY)
    if is_today and clock is not None:
        end = clock.now_utc()
    else:
        end = datetime(day.year, day.month, day.day, 20, 0, tzinfo=NY)
    rows = _rows(
        connection,
        """
        SELECT e.event_id, e.subject, e.kind, e.et_date, e.first_seen_at,
               e.headline, e.facts, e.segment, e.importance,
               i.url, t.title_zh
        FROM perception.news_events e
        LEFT JOIN LATERAL (
            SELECT url, info_id FROM ingest.info_items
            WHERE info_id = ANY(e.info_ids)
            ORDER BY (headline = e.headline) DESC, first_seen_at ASC LIMIT 1
        ) i ON true
        LEFT JOIN perception.news_translations t ON t.info_id = i.info_id
        WHERE e.first_seen_at >= %s AND e.first_seen_at < %s
        """,
        (start, end),
    )
    out = {}
    for row in rows:
        out.setdefault(row["subject"], []).append(row)
    return out


def _subjects_of(item, scope):
    """Reuses the B-069 subject rule for fallback news linking."""
    from inves_cog.perception.events.events import _names_map, subjects

    return subjects(item, set(scope), _names_map())


def _event_for(events, ticker):
    """Best event for a ticker: importance desc, first_seen asc; preview
    excluded when an earnings_result/guidance exists."""
    candidates = list((events or {}).get(ticker) or [])
    if not candidates:
        return None
    strong = [e for e in candidates if e["kind"] in ("earnings_result", "guidance")]
    if strong:
        candidates = [e for e in candidates if e["kind"] != "preview"]
    candidates.sort(key=lambda e: (-e["importance"], str(e["first_seen_at"])))
    return candidates[0]


def _fmt_pct(value):
    return f"{abs(value):.1f}" if abs(value) < 1 else f"{abs(value):.0f}"


def _facts_chip(facts):
    """'EPS 不及预期 30%；营收不及预期 0.2%' / '指引低于预期 42%'."""
    if not facts:
        return ""
    parts = []
    if facts.get("eps_actual") is not None and facts.get("eps_est"):
        s = 100 * (facts["eps_actual"] - facts["eps_est"]) / abs(facts["eps_est"])
        parts.append(("EPS 超预期 " if s > 0 else "EPS 不及预期 ") + _fmt_pct(s) + "%")
    if facts.get("rev_actual") is not None and facts.get("rev_est"):
        s = 100 * (facts["rev_actual"] - facts["rev_est"]) / abs(facts["rev_est"])
        parts.append(("营收超预期 " if s > 0 else "营收不及预期 ") + _fmt_pct(s) + "%")
    g = facts.get("guide_gap_pct")
    if g is not None:
        parts.append(("指引超预期 " if g > 0 else "指引低于预期 ") + _fmt_pct(g) + "%")
    return "；".join(parts)


_KIND_CN = {
    "earnings_result": "财报",
    "guidance": "指引",
    "capex": "资本开支",
    "mna": "并购",
    "supply_shock": "供应",
    "regulatory": "监管",
    "rating": "评级",
    "preview": "预告",
    "other": "事件",
}


def _cause_label(r):
    """'INTC 指引（指引低于预期 42%）'; no facts -> 'INTC 指引'."""
    if not r.get("cause_event_id"):
        return ""
    subj = r.get("cause_subject") or ""
    kind = _KIND_CN.get(r.get("cause_kind"), "事件")
    facts = _facts_chip(r.get("cause_facts") or {})
    head = f"{subj} {kind}".strip()
    return f"{head}（{facts}）" if facts else head


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


def _day_news(connection, day, cutoff, is_today=False):
    """News published in the ET session, regardless of when it was stored.

    The rules layer needs the raw headline, url and first_seen_at; 'late'
    marks items stored after the page cutoff (事后补采). On today's page the
    window is the last 24 hours ending at the cutoff, so pre-04:00 ET items
    still show (B-066).
    """
    if is_today:
        start, end = cutoff - timedelta(hours=24), cutoff
    else:
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
    intraday = context.get("intraday") or {}
    is_today = day == context.get("day")
    equity = cash
    pnl = 0.0
    missing = 0
    for ticker, position in positions.items():
        shares = _number(position.get("shares"))
        snap = intraday.get(ticker) if is_today else None
        close, previous = _session_closes(context["bars"].get(ticker) or [], day)
        if snap is not None and snap.get("last") is not None and snap.get("prev_close"):
            if shares is None:
                return None
            equity += shares * float(snap["last"])
            pnl += shares * (float(snap["last"]) - float(snap["prev_close"]))
        elif shares is None or close is None or previous is None:
            return None
        else:
            missing += 1
            equity += shares * close
            pnl += shares * (close - previous)
    if is_today and intraday:
        label = "盘中估算，仅供看盘"
        if missing:
            label += f"；{missing} 只未取到快照按收盘计"
    else:
        label = f"按 {day.month}月{day.day}日 收盘估算"
    return {"equity": equity, "day_pnl": pnl, "label": label}


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
    scores = _scores(connection, data_day, carry=(day == clock.today_trade_date() and carry_from is not None))
    ranges = _ranges(connection, data_day, cutoff, carry=(day == clock.today_trade_date() and carry_from is not None))
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
    is_today_page = day == clock.today_trade_date()
    news_items = _day_news(connection, day, cutoff, is_today_page)
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
    intraday = _intraday(connection, day, is_today_page)
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
        "news_events": _news_events(connection, data_day, is_today_page, clock),
        "elapsed_minutes": _elapsed_regular(clock) if day == clock.today_trade_date() else None,
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


def _member(ticker, day, bars, score, daily, held, events_for, snap=None, elapsed=None):
    """Volume multiple uses bars on the page day and the 20 sessions before it."""
    tech = _tech(score)
    history = bars.get(ticker) or []
    today_rows = [row for row in history if row["trade_date"] == day]
    prior_rows = [row for row in history if row["trade_date"] < day and row["volume"] is not None]
    today_volume = None if not today_rows else today_rows[-1]["volume"]
    vol_label = None
    prior_avg = sum(r["volume"] for r in prior_rows[-20:]) / min(20, len(prior_rows)) if prior_rows else None
    # B-068: intraday multiple = cumulative vol / (avg20 x elapsed/390); before the
    # open or without same-day volume, carry the last completed session's multiple.
    if snap is not None and snap.get("day_volume") and elapsed and prior_avg:
        today_volume = int(snap["day_volume"] / (prior_avg * min(390, elapsed) / 390))
        vol_label = "按时间折算"
    elif today_volume is None and len(prior_rows) >= 2 and prior_rows[-1].get("volume"):
        # previous completed session's own multiple: its volume / avg of the
        # 20 sessions before it (volume_multiple below computes the ratio).
        today_volume = prior_rows[-1]["volume"]
        vol_label = f"沿用 {prior_rows[-1]['trade_date']:%m/%d}"
    ret = None if ticker not in daily else daily[ticker]["ret"]
    if ret is None:
        close, previous = _session_closes(history, day)
        if close is not None and previous not in (None, 0):
            ret = close / previous - 1
    snap_ret = None
    if snap is not None and snap.get("last") and snap.get("prev_close"):
        snap_ret = float(snap["last"]) / float(snap["prev_close"]) - 1
    return {
        "ticker": ticker,
        "ret": ret,
        "volume_multiple": volume_multiple(
            today_volume,
            [row["volume"] for row in (prior_rows[:-1] if vol_label and "沿用" in vol_label else prior_rows)],
        ),
        "rsi": _number(tech.get("rsi")),
        "price_vs_ma200": _number(tech.get("price_vs_ma200")),
        "drawdown252": _number(tech.get("drawdown252")),
        "dev50": _number(tech.get("dev50")),
        "price": _price(tech, today_rows or history),
        "snap_ret": snap_ret,
        "snap_price": float(snap["last"]) if snap is not None and snap.get("last") else None,
        "snap_tag": _snap_tag(snap, day),
        "vol_label": vol_label,
        "held": held,
        "entry_pass": None if score is None else bool(score["entry_pass"]),
        "tier": None if score is None else score.get("tier"),
        "carried_from": None if score is None else score.get("carried_from"),
        "events": events_for,
        "books": _books(score),
    }


def _elapsed_regular(clock):
    """Minutes into today's regular session (ET 09:30-16:00), or None."""
    et = clock.now_utc().astimezone(NY)
    if et.time() >= __import__("datetime").time(16, 0):
        return 390
    start = et.replace(hour=9, minute=30, second=0, microsecond=0)
    return max(1, int((et - start).total_seconds() // 60)) if et > start else None


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
            snap = (context.get("intraday") or {}).get(ticker) if day == context["day"] else None
            member = _member(
                ticker,
                day,
                bars,
                score,
                daily,
                ticker in positions,
                membership.get(ticker, []),
                snap=snap,
                elapsed=context.get("elapsed_minutes"),
            )
            matched = [item for item in news_items if ticker in item["tickers"]]
            member["news_count"] = len(matched)
            member["news"] = matched[:3]
            member["valuation"] = _card_for(context, ticker, score, member["price"])
            member["tech"] = context["technicals"].get(ticker)
            members.append(member)
        average = theme_average([row["snap_ret"] if row.get("snap_ret") is not None else row["ret"] for row in members])
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


# ---- B-074 §2/§3/§8 homepage: market state, tape, 3-column block ----

_TAPE = [
    ("ES=F", "标普期货"),
    ("NQ=F", "纳指期货"),
    ("YM=F", "道指期货"),
    ("RTY=F", "罗素期货"),
    ("^VIX", "VIX"),
    ("^FVX", "5年期"),
    ("^TNX", "10年期"),
    ("^TYX", "30年期"),
    ("DX-Y.NYB", "美元指数"),
    ("CL=F", "WTI"),
    ("BZ=F", "布油"),
    ("GC=F", "黄金"),
    ("BTC-USD", "比特币"),
    ("SMH", "半导体"),
    ("SOXX", "半导体 ETF"),
    ("XLB", "材料"),
    ("XLC", "通信"),
    ("XLE", "能源"),
    ("XLF", "金融"),
    ("XLI", "工业"),
    ("XLK", "科技"),
    ("XLP", "必需消费"),
    ("XLRE", "地产"),
    ("XLU", "公用"),
    ("XLV", "医疗"),
    ("XLY", "可选消费"),
]
_MARKET3 = {
    "美股指数": [("SPY", "标普 500 ETF"), ("QQQ", "纳指 100 ETF"), ("IWM", "罗素 2000 ETF"), ("DIA", "道指 ETF")],
    "期货": [("ES=F", "ES 标普期货"), ("NQ=F", "NQ 纳指期货"), ("YM=F", "YM 道指期货"), ("RTY=F", "RTY 罗素期货")],
    "利率": [("^FVX", "5年期"), ("^TNX", "10年期"), ("^TYX", "30年期")],
    "大宗与加密": [
        ("CL=F", "WTI"),
        ("BZ=F", "布油"),
        ("GC=F", "黄金"),
        ("BTC-USD", "比特币"),
        ("DX-Y.NYB", "美元指数"),
    ],
    "行业": [
        ("XLB", "材料"),
        ("XLC", "通信"),
        ("XLE", "能源"),
        ("XLF", "金融"),
        ("XLI", "工业"),
        ("XLK", "科技"),
        ("XLP", "必需消费"),
        ("XLRE", "地产"),
        ("XLU", "公用"),
        ("XLV", "医疗"),
        ("XLY", "可选消费"),
        ("SMH", "半导体"),
        ("SOXX", "半导体 ETF"),
    ],
}
_YIELDS = {"^FVX", "^TNX", "^TYX"}


def _close_series(connection, ticker, day, n=22):
    """Daily closes up to `day`: bars_daily when the ticker has bars (plus a
    same-day snapshot while the day's bar is not written yet), otherwise the
    last intraday snapshot of each ET date."""
    rows = (
        connection.execute(
            "SELECT trade_date AS d, close AS c FROM ingest.bars_daily "
            "WHERE ticker=%s AND trade_date<=%s ORDER BY trade_date DESC LIMIT %s",
            (ticker, day, n),
        ).fetchall()
        if _table_exists(connection, "ingest.bars_daily")
        else []
    )
    series = [(r["d"], float(r["c"])) for r in reversed(rows) if r["c"] is not None]
    if not _table_exists(connection, "ingest.intraday_snapshots"):
        return series[-n:]
    snaps = connection.execute(
        "SELECT DISTINCT ON (d) d, last FROM ("
        " SELECT (as_of AT TIME ZONE 'America/New_York')::date AS d, as_of, last"
        " FROM ingest.intraday_snapshots WHERE ticker=%s"
        " AND as_of < (%s::date + 1)::timestamp AT TIME ZONE 'America/New_York'"
        " AND as_of >= (%s::date - 40)::timestamp AT TIME ZONE 'America/New_York') x"
        " WHERE last IS NOT NULL ORDER BY d DESC, as_of DESC",
        (ticker, day, day),
    ).fetchall()
    snap_series = [(r["d"], float(r["last"])) for r in reversed(snaps)]
    if series:
        if series[-1][0] < day and snap_series and snap_series[-1][0] == day:
            series.append(snap_series[-1])
        return series[-n:]
    return snap_series[-n:]


def _quote(connection, ticker, day):
    """Latest value for `day`, change vs the previous session, and the size of
    that change relative to the prior 20 sessions (σ multiple)."""
    series = _close_series(connection, ticker, day)
    if len(series) < 2:
        return None
    (d1, last), (_, prev) = series[-1], series[-2]
    values = [v for _, v in series]
    if ticker in _YIELDS:
        diffs = [(values[i] - values[i - 1]) * 100 for i in range(1, len(values) - 1)]
        chg = (last - prev) * 100
        sig = statistics.stdev(diffs) if len(diffs) >= 10 else None
        return {
            "px": last,
            "ret": None,
            "chg_bp": chg,
            "sig": sig,
            "mult": abs(chg) / sig if sig else abs(chg) / 7,
            "as_of": str(d1),
            "fallback": sig is None,
        }
    rets = [values[i] / values[i - 1] - 1 for i in range(1, len(values) - 1)]
    ret = last / prev - 1
    sig = statistics.stdev(rets) if len(rets) >= 10 else None
    return {
        "px": last,
        "ret": ret,
        "sig": sig,
        "mult": abs(ret) / sig if sig else abs(ret) / 0.01,
        "as_of": str(d1),
        "fallback": sig is None,
    }


def _safe_call(fn, fallback):
    try:
        return fn()
    except Exception:
        import logging

        logging.getLogger(__name__).warning("homepage optional block failed: %r", sys.exc_info()[1])
        return fallback


def _tape_rows(connection, day):
    out = []
    for ticker, name in _TAPE:
        q = _quote(connection, ticker, day)
        if q is not None:
            out.append({"sym": ticker, "name": name, **q})
    return out


def _market_state(connection, day, payload, live):
    """§2: band by SPY/QQQ day return vs own prior-20-session σ; direction from
    sign, breadth and the SPY/QQQ gap; cause only from linked market/basket anomalies."""
    quotes = {t: _quote(connection, t, day) for t in ("SPY", "QQQ")}
    spy, qqq = quotes["SPY"] or {}, quotes["QQQ"] or {}
    mults = [q["mult"] for q in (spy, qqq) if q.get("sig")]
    max_mult = max(mults) if mults else 0
    band = "平静" if max_mult < 1 else "明显波动" if max_mult < 2 else "剧烈"
    up, dn = payload.get("advancers"), payload.get("decliners")
    s_ret, q_ret = spy.get("ret"), qqq.get("ret")
    if band == "平静":
        direction = "窄幅整理"
    elif s_ret is not None and s_ret < 0:
        direction = "科技股领跌" if q_ret is not None and q_ret < s_ret - 0.005 else "普跌"
    elif s_ret is not None:
        direction = "科技股领涨" if q_ret is not None and q_ret > s_ret + 0.005 else "普涨"
    else:
        direction = "方向暂缺"
    if up is not None and dn is not None and band != "平静":
        if s_ret is not None and s_ret < 0 and up > dn:
            direction += "，但多数股上涨"
        elif s_ret is not None and s_ret > 0 and dn > up:
            direction += "，但多数股下跌"

    def part(label, q):
        if q.get("ret") is None or not q.get("sig"):
            return f"{label}数据暂缺"
        return f"{label} {q['ret'] * 100:+.1f}%（约平时 {q['mult']:.1f} 倍）"

    causes = []
    for r in live:
        if r["scope"] in ("market", "basket") and r.get("cause_event_id") and r.get("cause_label"):
            head = r["cause_label"]
            if head not in causes:
                causes.append(head)
        if len(causes) == 2:
            break
    lead = payload.get("leaders_down") or []
    lag = payload.get("leaders_up") or []
    focus = ""
    if band != "平静" and s_ret is not None:
        names = lead if s_ret < 0 else lag
        other = lag if s_ret < 0 else lead
        if names:
            focus += f"；{'跌' if s_ret < 0 else '涨'}幅集中在{'、'.join(n['name'] for n in names[:2])}"
        if other:
            focus += f"；{'、'.join(n['name'] for n in other[:2])}逆势{'上涨' if s_ret < 0 else '下跌'}"
    cause_txt = ""
    if band != "平静":
        cause_txt = "；主要来自 " + "；".join(c[:60] for c in causes) if causes else "；原因未明"
    detail = f"{part('纳指', qqq)}，{part('标普', spy)}{focus}{cause_txt}"
    return {
        "band": band,
        "direction": direction,
        "title": f"{band} · {direction}",
        "detail": detail,
        "sentence": f"{band} · {direction}：{detail}",
        "spy_sig": spy.get("sig"),
        "qqq_sig": qqq.get("sig"),
        "spy_ret": s_ret,
        "qqq_ret": q_ret,
    }


def _hl_grouped(live, positions):
    """§2 highlights: one card per cause (cause_event_id, else subject); the card
    ranks by its most important member scope (market > holdings > basket > stock);
    active before faded; max 4."""
    groups = {}
    for r in live:
        key = r.get("cause_event_id") or f"subj:{r['subject']}"
        groups.setdefault(key, []).append(r)
    held = set(positions or [])
    scope_order = {"market": 0, "basket": 1, "stock": 2}
    items = []
    for rows in groups.values():
        rows.sort(key=lambda r: (scope_order.get(r["scope"], 3), -abs(r.get("peak_z") or 0)))
        top = rows[0]
        touches_held = any(r["subject"] in held or any(m in held for m in (r.get("members") or {})) for r in rows)
        active = any(r.get("status") == "active" for r in rows)
        best_scope = min(scope_order.get(r["scope"], 3) for r in rows)
        if best_scope == 0:
            why = "大盘层面异常"
        elif touches_held:
            why = "涉及持仓"
        elif best_scope == 1:
            why = "核心链条板块"
        else:
            why = "单股异常"
        lead = max(rows, key=lambda r: abs(r.get("peak_z") or 0))
        items.append(
            {
                "scope": lead["scope"],
                "subject": lead["subject"],
                "basket_name": lead.get("basket_name"),
                "ret": lead.get("peak_ret"),
                "last_px": lead.get("last_px"),
                "why": why,
                "cause": top.get("cause_headline"),
                "kind": top.get("cause_kind"),
                "peak_z": lead.get("peak_z"),
                "members": sorted(rows, key=lambda r: -abs(r.get("peak_z") or 0)),
                "rank": (
                    0 if active else 1,
                    best_scope if best_scope == 0 else (1 if touches_held else 1 + best_scope),
                    -abs(lead.get("peak_z") or 0),
                ),
            }
        )
    items.sort(key=lambda x: x["rank"])
    return items[:4]


def _market3(connection, day, index_quotes=None, index_closes=None):
    """§8 3-column block: tabbed quotes + embedded daily/intraday series.
    index_quotes/index_closes: payload fallbacks so fixture/no-snapshot days
    still show index rows and chartable daily closes."""
    groups = {}
    for tab, rows in _MARKET3.items():
        items = []
        for t, name in rows:
            q = _quote(connection, t, day)
            if q is not None:
                items.append({"sym": t, "name": name, **q})
        have = {i["sym"] for i in items}
        for q in index_quotes or []:
            if tab == "美股指数" and q["id"] not in have and q.get("ret") is not None:
                cs = (index_closes or {}).get(q["id"]) or []
                items.append(
                    {"sym": q["id"], "name": f"{q['id']} {q['name']}", "px": cs[-1] if cs else None, "ret": q["ret"]}
                )
        if items:
            groups[tab] = items
    daily, intraday = {}, {}
    for t in [t for rows in _MARKET3.values() for t, _ in rows]:
        rows = (
            connection.execute(
                "SELECT * FROM ingest.bars_daily WHERE ticker=%s AND trade_date<=%s ORDER BY trade_date DESC LIMIT 260",
                (t, day),
            ).fetchall()
            if _table_exists(connection, "ingest.bars_daily")
            else []
        )
        if rows:
            daily[t] = [
                {
                    "d": str(r["trade_date"]),
                    "o": float(r["open"] or r["close"]),
                    "h": float(r["high"] or r["close"]),
                    "l": float(r["low"] or r["close"]),
                    "c": float(r["close"]),
                    "v": int(r["volume"] or 0),
                }
                for r in reversed(rows)
                if r["close"] is not None
            ]
        else:
            daily[t] = [
                {"d": str(d), "o": v, "h": v, "l": v, "c": v, "v": 0} for d, v in _close_series(connection, t, day, 260)
            ]
        srows = (
            connection.execute(
                "SELECT as_of, last FROM ingest.intraday_snapshots WHERE ticker=%s"
                " AND as_of >= %s::timestamp AT TIME ZONE 'America/New_York'"
                " AND as_of < (%s::date + 1)::timestamp AT TIME ZONE 'America/New_York' ORDER BY as_of",
                (t, day, day),
            ).fetchall()
            if _table_exists(connection, "ingest.intraday_snapshots")
            else []
        )
        if len(srows) > 1:
            intraday[t] = [{"t": r["as_of"].isoformat(), "p": float(r["last"])} for r in srows if r["last"] is not None]
    return {"groups": groups, "daily": daily, "intraday": intraday}


def page_brief_market(connection, day, clock):
    context, closed = _context(connection, day, clock)
    if closed is not None:
        return closed
    rotation = context["rotation"]
    catalog = context["catalog"]
    spy, qqq, iwm = (_index_ret(rotation, name) for name in ("SPY", "QQQ", "IWM"))
    is_today_page = day == clock.today_trade_date()
    wide = _wide_snapshot_breadth(connection, day) if is_today_page else None
    advancers, decliners = wide if wide is not None else _breadth(context["daily"])
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
    is_today = day == clock.today_trade_date()
    _wmovers, wide_asof = _wide_movers(connection, day, is_today)
    _wm = {"up": _wmovers[:5], "down": sorted(_wmovers, key=lambda r: r["ret"])[:5]}
    fallen = "、".join(row["name"] for row in down[:2])
    risen = "、".join(row["name"] for row in up[:2])
    funds = f"资金：{fallen}领跌，{risen}领涨"
    if not down or not up:
        funds = "资金：领跌或领涨" + MISSING
    live_rows = _live_anomalies(connection, day, is_today_page)
    _state_payload = {
        "advancers": advancers,
        "decliners": decliners,
        "leaders_down": down,
        "leaders_up": up,
        "indexes": [
            {"id": "SPY", "name": INDEX_LABELS["SPY"], "ret": spy},
            {"id": "QQQ", "name": INDEX_LABELS["QQQ"], "ret": qqq},
        ],
    }
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
        "ticker_scope": sorted(set(context["pool"]) | set(context["positions"])),
        "events": events,
        "news_fresh": context["fresh"],
        "carry_from": context["carry_from"],
        "freshness": _freshness(context, clock),
        "et_now": clock.now_utc().astimezone(NY).strftime("%H:%M"),
        "trading_day": trading_day(day),
        "today": clock.today_trade_date().isoformat(),
        "is_today": context["day"] == clock.today_trade_date(),
        "intraday": context["intraday"],
        "mstrip": _market_strip(connection, context, day),
        "sector_strip": _sector_strip(context, _themes(context, day)),
        "news_modules": {
            **(_news_views_today(context) if is_today_page else _news_views(context)),
            "live": live_rows,
            "earnings_cards": _earnings_cards(connection, day),
        },
        "tape": _safe_call(lambda: _tape_rows(connection, day), []),
        "state": _safe_call(lambda: _market_state(connection, day, _state_payload, live_rows), {}),
        "hl_groups": _safe_call(lambda: _hl_grouped(live_rows, context["positions"]), []),
        "market3": _safe_call(
            lambda: _market3(
                connection,
                day,
                index_quotes=[
                    {"id": "SPY", "name": INDEX_LABELS["SPY"], "ret": spy},
                    {"id": "QQQ", "name": INDEX_LABELS["QQQ"], "ret": qqq},
                    {"id": "IWM", "name": INDEX_LABELS["IWM"], "ret": iwm},
                ],
                index_closes=_index_closes(connection, day),
            ),
            {},
        ),
        "wide_movers_up": _wm["up"],
        "wide_movers_down": _wm["down"],
        "wide_asof": wide_asof,
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
        "is_today": day == clock.today_trade_date(),
        "freshness": _freshness(context, clock) if day == clock.today_trade_date() else None,
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
        "is_today": day == clock.today_trade_date(),
        "freshness": _freshness(context, clock) if day == clock.today_trade_date() else None,
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


def _intraday(connection, day, is_today=False):
    """Latest intraday snapshot per ticker (A-024 contract).

    For today's page the latest row within the last 3 calendar days wins —
    after-hours/overnight rows carry over into the next morning (B-066).
    Historical dates stay on the same-day window.
    """
    if not _table_exists(connection, "ingest.intraday_snapshots"):
        return {}
    start, end = _day_window(day)
    if is_today:
        start -= timedelta(days=3)
    vol_col = (
        "day_volume" if _column_exists(connection, "ingest.intraday_snapshots", "day_volume") else "NULL AS day_volume"
    )
    rows = _rows(
        connection,
        f"""
        SELECT DISTINCT ON (ticker, source) ticker, as_of, session, last, prev_close, delay_minutes, source, {vol_col}
        FROM ingest.intraday_snapshots
        WHERE as_of >= %s AND as_of < %s
        ORDER BY ticker, source, as_of DESC
        """,
        (start, end),
    )
    # B-067: per ticker pick latest IEX vs latest SIP/other; IEX wins when newer.
    out = {}
    for row in rows:
        row = dict(row)
        is_iex = (row.get("source") or "") == "Alpaca:iex"
        cur = out.get(row["ticker"])
        if cur is None:
            out[row["ticker"]] = {"main": row, "alt": None}
            continue
        newest_is_iex = (cur["main"].get("source") or "") == "Alpaca:iex"
        if is_iex and not newest_is_iex and row["as_of"] > cur["main"]["as_of"]:
            cur["alt"], cur["main"] = cur["main"], row
        elif not is_iex and (newest_is_iex or row["as_of"] > cur["main"]["as_of"]):
            if newest_is_iex:
                cur["alt"], cur["main"] = cur["main"], row
            else:
                cur["main"], cur["alt"] = row, cur["main"] if cur["alt"] is None else cur["alt"]
        elif is_iex and cur["alt"] is None:
            cur["alt"] = row
    return {t: {**entry["main"], "alt": entry["alt"]} for t, entry in out.items()}


STRIP_ITEMS = [
    ("ES=F", "标普期货", "fut"),
    ("NQ=F", "纳指期货", "fut"),
    ("RTY=F", "罗素期货", "fut"),
    ("YM=F", "道指期货", "fut"),
    ("SPY", "标普", "etf"),
    ("QQQ", "纳指", "etf"),
    ("IWM", "罗素", "etf"),
    ("DGS2", "美债 2 年", "yield"),
    ("^FVX", "美债 5 年", "yield"),
    ("^TNX", "美债 10 年", "yield"),
    ("^TYX", "美债 30 年", "yield"),
    ("CL=F", "WTI", "cmd"),
    ("BZ=F", "布伦特", "cmd"),
    ("GC=F", "黄金", "cmd"),
    ("DX-Y.NYB", "美元指数", "cmd"),
    ("BTC-USD", "比特币", "cmd"),
    ("^VIX", "VIX", "fut"),
]

SECTOR_ORDER = [
    "AI 网络与光通信",
    "存储",
    "半导体设备",
    "AI 算力芯片",
    "AI 服务器与算力云",
    "数据中心电力与散热",
    "网络安全",
    "软件与平台",
    "互联网",
]

SECTOR_ETFS = ["SMH", "SOXX", "IGV", "XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLI", "XLU", "XLC", "XLRE", "XLB"]


def _snap_tag(snap, day=None):
    """'IEX 12:11:50' / '延迟 15 分 11:56' / session label (B-067 sources).

    A snapshot from a previous ET date shows the date and session instead of a
    bare time, so an old post-session quote can't read as today's price."""
    if snap is None or not snap.get("as_of"):
        return None
    as_of = snap["as_of"].astimezone(NY)
    src = snap.get("source") or ""
    sess = {"pre": "盘前", "regular": "盘中", "post": "盘后", "overnight": "隔夜"}.get(snap.get("session"), "")
    if day is not None and as_of.date() != day:
        if src == "Alpaca:iex":
            return f"IEX {as_of:%m/%d %H:%M:%S}"
        return f"{sess} {as_of:%m/%d %H:%M}".strip()
    if src == "Alpaca:iex":
        return f"IEX {as_of:%H:%M:%S}"
    if src == "Alpaca:delayed_sip":
        return f"延迟 15 分 {as_of:%H:%M}"
    return f"{sess} {as_of:%H:%M}".strip()


def _snap_ret(snap):
    if snap is None or snap.get("last") is None or not snap.get("prev_close"):
        return None
    return float(snap["last"]) / float(snap["prev_close"]) - 1


def _strip_item(ticker, label, kind, snap, close_ret, day, dgs2=None):
    """One ticker-strip cell: value + signed change (bp for yields)."""
    if ticker == "DGS2" and dgs2 is not None:
        d = dgs2["observation_date"]
        return {
            "label": label,
            "value": f"{float(dgs2['value']):.2f}%",
            "chg": f"收盘 {d:%m/%d}",
            "dir": 0,
            "title": f"收盘 {d}",
        }
    if snap is not None:
        ret = _snap_ret(snap)
        if ret is None:
            return {"label": label, "value": "—", "chg": None, "dir": 0, "title": "暂缺"}
        asof = snap["as_of"].astimezone(NY)
        bj = snap["as_of"].astimezone(_SHANGHAI)
        sess = {"pre": "盘前", "regular": "盘中", "post": "盘后", "overnight": "隔夜"}.get(snap.get("session"), "")
        src = snap.get("source") or ""
        src_label = {
            "Alpaca:iex": "Alpaca IEX",
            "Alpaca:delayed_sip": "Alpaca 延迟 SIP",
            "Yahoo": "Yahoo",
            "FRED": "FRED",
        }.get(src, src or "snapshot")
        if src == "Alpaca:iex":
            when = f"IEX 实时 {asof:%H:%M:%S}"
        elif src == "Alpaca:delayed_sip":
            when = f"延迟 15 分 {asof:%H:%M}"
        else:
            when = f"{sess} {asof:%m/%d %H:%M}" if asof.date() != day else f"{sess} {asof:%H:%M}"
        alt = snap.get("alt")
        alt_text = ""
        if alt is not None:
            a_src = {
                "Alpaca:iex": "Alpaca IEX",
                "Alpaca:delayed_sip": "Alpaca 延迟 SIP",
                "Yahoo": "Yahoo",
                "FRED": "FRED",
            }.get(alt.get("source") or "", alt.get("source") or "snapshot")
            a_asof = alt["as_of"].astimezone(NY)
            alt_text = f" · {a_src} {float(alt['last']):.2f} 于 {a_asof:%H:%M}"
        title = f"北京 {bj:%m-%d %H:%M} · 延迟约 {snap.get('delay_minutes', 0)} 分钟 · {src_label}{alt_text}"
        if kind == "yield":
            bp = (float(snap["last"]) - float(snap["prev_close"])) * 100
            # yield up = risk-off (red for stocks), down = green
            return {
                "label": label,
                "value": f"{float(snap['last']):.2f}%",
                "chg": f"{'+' if bp >= 0 else ''}{bp:.1f} 基点",
                "dir": -1 if bp > 0 else (1 if bp < 0 else 0),
                "tag": when,
                "title": title + " · 收益率上升对股市偏空，显示为红",
            }
        return {
            "label": label,
            "value": f"{float(snap['last']):,.2f}",
            "chg": f"{'+' if ret >= 0 else ''}{ret * 100:.2f}%",
            "dir": 1 if ret > 0 else (-1 if ret < 0 else 0),
            "tag": when,
            "title": title,
        }
    if close_ret is not None:
        return {
            "label": label,
            "value": f"{'+' if close_ret >= 0 else ''}{close_ret * 100:.2f}%",
            "chg": "收盘",
            "dir": 1 if close_ret > 0 else (-1 if close_ret < 0 else 0),
            "tag": "收盘",
            "title": "当日收盘",
        }
    return {"label": label, "value": "—", "chg": None, "dir": 0, "title": "暂缺"}


def _market_strip(connection, context, day):
    intraday = context.get("intraday") or {}
    close_idx = {row["group_id"]: row["ret"] for row in context.get("rotation") or [] if row["group_kind"] == "index"}
    dgs2 = None
    if _table_exists(connection, "ingest.macro_observations"):
        row = _one(
            connection,
            "SELECT value, observation_date FROM ingest.macro_observations"
            " WHERE series_id = 'DGS2' AND observation_date <= %s ORDER BY observation_date DESC LIMIT 1",
            (day,),
        )
        dgs2 = row
    items = []
    last_asof = None
    last_session = None
    for ticker, label, kind in STRIP_ITEMS:
        snap = intraday.get(ticker)
        if snap and snap.get("as_of"):
            asof = snap["as_of"].astimezone(NY)
            if last_asof is None or asof > last_asof:
                last_asof, last_session = asof, snap.get("session")
        items.append(_strip_item(ticker, label, kind, snap, close_idx.get(ticker), day, dgs2))
    etf_row = [_strip_item(t, t, "etf", intraday.get(t), close_idx.get(t), day) for t in SECTOR_ETFS]
    tail = None
    if last_asof is not None:
        label = {"pre": "盘前", "regular": "盘中", "post": "盘后"}.get(last_session, "")
        tail = f"{label} · 截至 {last_asof:%H:%M} 美东"
    return {"items": items, "etfs": etf_row, "tail": tail or "收盘"}


def _sector_strip(context, themes):
    intraday = context.get("intraday") or {}
    by_name = {t["sector"]: t for t in themes or []}
    ordered = [s for s in SECTOR_ORDER if s in by_name] + [s for s in by_name if s not in SECTOR_ORDER]
    cards = []
    for sector in ordered:
        theme = by_name[sector]
        members = theme.get("members") or []
        rets = []
        for m in members:
            ret = _snap_ret(intraday.get(m["ticker"]))
            if ret is None:
                ret = m.get("ret")
            if ret is not None:
                rets.append((m["ticker"], ret))
        average = sum(r for _, r in rets) / len(rets) if rets else None
        leader = max(rets, key=lambda x: x[1]) if rets else None
        laggard = min(rets, key=lambda x: x[1]) if rets else None
        cards.append(
            {
                "sector": sector,
                "slug": f"theme-{_slug(sector)}",
                "average": average,
                "leader": leader,
                "laggard": laggard,
                "held": theme.get("held_count") or 0,
            }
        )
    return cards


def _slug(sector):
    return sector.replace(" ", "-").replace("/", "-")


def _freshness(context, clock):
    """'数据更新至 北京 HH:MM（美东 HH:MM）' from the newest snapshot used;
    include the date when the snapshot is not on today's ET date."""
    intraday = context.get("intraday") or {}
    latest = max((r["as_of"] for r in intraday.values() if r.get("as_of")), default=None)
    if latest is None:
        return None
    bj = latest.astimezone(_SHANGHAI)
    et = latest.astimezone(NY)
    today = clock.today_trade_date() if clock is not None else et.date()
    if et.date() != today:
        return f"数据更新至 北京 {bj:%m-%d %H:%M}（美东 {et:%m-%d %H:%M}）"
    return f"数据更新至 北京 {bj:%H:%M}（美东 {et:%H:%M}）"


def _news_views_today(context):
    """Today's movers ranked by latest snapshot change over ALL members.

    Snapshot ret wins, close ret as fallback; members without either are not
    candidates. Snapshot metadata is attached for the header chip."""
    intraday = context.get("intraday") or {}

    def mover_key(member):
        snap = intraday.get(member["ticker"])
        if snap is not None and _snap_ret(snap) is not None:
            return abs(_snap_ret(snap))
        return abs(member["ret"]) if member["ret"] is not None else None

    mods = _news_views(context, mover_key)
    elapsed = context.get("elapsed_minutes")
    bars = context.get("bars") or {}
    for m in mods["movers"]:
        snap = intraday.get(m["ticker"])
        if snap is not None and _snap_ret(snap) is not None:
            m["snap_ret"] = _snap_ret(snap)
            m["snap_asof"] = snap["as_of"].astimezone(NY).strftime("%H:%M")
            m["snap_delay"] = snap.get("delay_minutes")
            m["snap_session"] = snap.get("session")
        # B-068: same time-scaled multiple as the stocks table
        rows = [r for r in (bars.get(m["ticker"]) or []) if r["trade_date"] < context["day"] and r["volume"]]
        prior = [r["volume"] for r in rows]
        if snap is not None and snap.get("day_volume") and elapsed and prior:
            m["vol"] = volume_multiple(int(snap["day_volume"] / (min(390, elapsed) / 390)), prior)
            m["vol_label"] = "按时间折算"
        elif m.get("vol") is None and len(prior) >= 2:
            m["vol"] = volume_multiple(prior[-1], prior[:-1])
            m["vol_label"] = f"沿用 {rows[-1]['trade_date']:%m/%d}"
    return mods


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


def _wide_snapshot_breadth(connection, day):
    """Advance/decline counts from today's ingest.wide_snapshots, or None."""
    if not _table_exists(connection, "ingest.wide_snapshots"):
        return None
    rows = _rows(
        connection,
        """
        SELECT DISTINCT ON (ticker) ticker, last / prev_close - 1 AS ret
        FROM ingest.wide_snapshots
        WHERE as_of >= %s AND prev_close > 0
        ORDER BY ticker, as_of DESC
        """,
        (_day_window(day)[0],),
    )
    if not rows:
        return None
    return (
        sum(1 for r in rows if r["ret"] is not None and float(r["ret"]) > 0),
        sum(1 for r in rows if r["ret"] is not None and float(r["ret"]) < 0),
    )


def _wide_movers(connection, day, is_today=False):
    """Whole-market movers: price >= $5, ADV20 >= $20M, no warrants/units.

    On today's page prefer ingest.wide_snapshots (A-025) latest rows when
    present — returns (rows, as_of); falls back to close data with as_of=None.
    """
    if is_today and _table_exists(connection, "ingest.wide_snapshots"):
        rows = _rows(
            connection,
            """
            SELECT DISTINCT ON (ticker) ticker, last AS close, prev_close,
                   last / prev_close - 1 AS ret, as_of
            FROM ingest.wide_snapshots
            WHERE as_of >= %s AND prev_close > 0
            ORDER BY ticker, as_of DESC
            """,
            (_day_window(day)[0],),
        )
        if rows:
            as_of = max(r["as_of"] for r in rows)
            adv = {}
            if _table_exists(connection, "ingest.wide_universe"):
                for row in _rows(
                    connection,
                    """
                    SELECT DISTINCT ON (ticker) ticker, adv20
                    FROM ingest.wide_universe
                    WHERE trade_date < %s AND included
                    ORDER BY ticker, trade_date DESC
                    """,
                    (day,),
                ):
                    adv[row["ticker"]] = row["adv20"]
            names = {r["ticker"] for r in rows}
            clean = [
                row
                for row in rows
                if row["close"] is not None
                and float(row["close"]) >= 5
                and (row["ticker"] not in adv or (adv[row["ticker"]] or 0) >= 20000000)
                and not (WARRANT_SUFFIX.match(row["ticker"]) and row["ticker"][:-1] in names)
            ]
            clean.sort(key=lambda r: r["ret"], reverse=True)
            return clean, as_of
    return _wide_movers_close(connection, day), None


def _wide_movers_close(connection, day):
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


def _news_views(context, mover_key=None):
    """Market-page news modules from the ranked rules layer.

    mover_key(member) -> sortable change magnitude for the movers block;
    defaults to abs(close ret)."""
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
    if mover_key is None:

        def mover_key(m):
            return abs(m["ret"]) if m["ret"] is not None else None

    top8 = sorted((m for m in members.values() if mover_key(m) is not None), key=lambda m: -mover_key(m))[:8]
    events_map = context.get("news_events") or {}
    for m in top8:
        ev = _event_for(events_map, m["ticker"])
        m["event"] = ev
        m["event_chip"] = _facts_chip((ev or {}).get("facts") or {})
        own = sorted(
            (
                n
                for n in ranked
                if m["ticker"] in n["rule"].primary_tickers
                and m["ticker"]
                in _subjects_of(
                    {"tickers": n.get("tickers") or [], "headline": n.get("title") or n.get("headline") or ""},
                    held | set(members),
                )
            ),
            key=lambda n: (-n["rule"].importance, n["published"]),
        )
        m["news"] = [] if ev is not None else own[:1]
        m["has_news"] = bool(own) or ev is not None
        m["news_unconfirmed"] = ev is None and bool(own)
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
    core = set()
    try:
        from inves_cog.perception.core_companies import core_companies

        core = set(core_companies())
    except Exception:
        pass
    events_map = context.get("news_events") or {}

    def _theme_event_score(n):
        tickers = n["rule"].primary_tickers or n["tickers"] or []
        best = max(
            (_event_for(events_map, t) for t in tickers), key=lambda e: e["importance"] if e else -1, default=None
        )
        return (best["importance"], 1 if best and best["subject"] in core else 0) if best else (-1, 0)

    scores = {id(n): _theme_event_score(n) for n in pick}
    pick.sort(
        key=lambda n: (
            -scores[id(n)][1],
            -scores[id(n)][0],
            -n["rule"].held,
            -n["rule"].importance,
            -(n["published"].timestamp() if n["published"] else 0),
        )
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


def _live_anomalies(connection, day, is_today):
    """B-070 §4: live_anomalies for the page. Active rows today; all rows
    (incl. faded) for historical days. Missing table -> []."""
    if connection is None:
        return []
    exists = connection.execute("SELECT to_regclass('perception.live_anomalies') AS t").fetchone()
    if not exists or not exists["t"]:
        return []
    status = "" if not is_today else "AND a.status='active'"
    rows = connection.execute(
        f"""SELECT a.*, b.name AS basket_name, e.headline AS cause_headline,
                   e.first_seen_at AS cause_first_seen,
                   e.facts AS cause_facts, e.subject AS cause_subject, e.kind AS cause_kind
            FROM perception.live_anomalies a
            LEFT JOIN graph.baskets b ON b.basket_id = a.subject AND a.scope='basket'
            LEFT JOIN perception.news_events e ON e.event_id = a.cause_event_id
            WHERE a.trade_date=%s {status}
            ORDER BY abs(COALESCE(a.peak_z,0)) DESC LIMIT 10""",
        (day,),
    ).fetchall()
    try:
        tickers = [r["subject"] for r in rows if r["scope"] == "stock"]
        if tickers:
            px = {
                r["ticker"]: r["last"]
                for r in connection.execute(
                    "SELECT DISTINCT ON (ticker) ticker, last FROM ingest.intraday_snapshots "
                    "WHERE ticker = ANY(%s) ORDER BY ticker, as_of DESC",
                    (tickers,),
                ).fetchall()
            }
            for r in rows:
                r["last_px"] = float(px[r["subject"]]) if r["subject"] in px and px[r["subject"]] else None
    except Exception:
        pass
    for r in rows:
        r["cause_label"] = _cause_label(r)
    return rows


def _news_theme(item, theme_map, held):
    from inves_cog.perception.news.rules import theme_of

    return theme_of(item, theme_map, held)


def _earnings_cards(connection, day):
    """B-072: perception.earnings_cards for the homepage/stock page; empty on
    missing table (degrade)."""
    try:
        rows = connection.execute(
            "SELECT ticker, report_date, report_time, stage, card, missing "
            "FROM perception.earnings_cards ORDER BY report_date"
        ).fetchall()
    except Exception:
        return []
    return [{**dict(r), "report_date": str(r["report_date"])} for r in rows]


def page_search(connection, day, clock, q):
    """B-073: /search — exact code or unique name redirects; else a list."""
    context, closed = _context(connection, day, clock)
    query = (q or "").strip()
    cands = {}
    try:
        rows = connection.execute(
            "SELECT DISTINCT ON (ticker) ticker, company FROM ingest.earnings_calendar"
        ).fetchall()
        for r in rows:
            cands[r["ticker"]] = r["company"] or ""
    except Exception:
        pass
    names = context.get("stocks") or set(context["pool"])
    for t in sorted(set(context["pool"]) | set(context["positions"]) | names):
        cands.setdefault(t, "")
    from inves_cog.perception.core_companies import core_companies

    for t in core_companies():
        cands.setdefault(t, "")
    ql = query.upper()
    if ql in cands:
        return {"page": "/search", "redirect": f"/s/{ql}", "date": day, "label": PAPER_LABEL}
    hits = [
        t
        for t, n in cands.items()
        if query and (query.casefold() in t.casefold() or query.casefold() in str(n).casefold())
    ]
    if len(hits) == 1:
        return {"page": "/search", "redirect": f"/s/{hits[0]}", "date": day, "label": PAPER_LABEL}
    return {
        "page": "/search",
        "date": day,
        "q": query,
        "results": [{"ticker": t, "name": cands[t]} for t in hits[:20]],
        "label": PAPER_LABEL,
    }
