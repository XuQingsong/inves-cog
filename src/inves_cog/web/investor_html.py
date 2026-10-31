"""Investor pages. Structure follows the final prototype; numbers come from the brief payload."""

import json
import re
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import NY, next_trading_day, trading_day
from inves_cog.web.brief import (
    MISSING,
    PAPER_LABEL,
    format_fraction,
    half_up,
    human_reason,
    short_unvalued_text,
)
from inves_cog.web.exit_levels import money
from inves_cog.web.pages import CLOSED
from inves_cog.web.risk_brief import format_plain_percent, risk_params
from inves_cog.web.ruler import ruler

SH = ZoneInfo("Asia/Shanghai")

NAV = (
    ("/", "市场总览", "大环境怎么样"),
    ("/stocks", "我的标的", "59 只各自怎样"),
    ("/account", "纸面账户", "仓位怎么处理"),
    ("/trust", "复盘与数据", "系统靠不靠谱"),
)
DETAILS = (
    ("/log", "系统日志"),
    ("/market", "市场"),
    ("/graph", "图谱"),
    ("/settings/data", "数据健康"),
    ("/paper/plan", "盘前计划"),
    ("/paper/portfolio", "纸面明细"),
    ("/paper/universe", "标的池"),
    ("/paper/health", "数据质量"),
    ("/paper/ledger", "纸面流水"),
    ("/review", "复盘"),
)
_WEEK = "一二三四五六日"
_RULE_STATE = {
    "none": "未到门槛",
    "pending": "已到门槛 · 待执行",
    "hold": "已到门槛 · 暂不执行",
    "done": "已执行 · 不再重复",
}
_KIND = {"exit": "全部卖出", "reduce": "减仓", "sell": "卖出"}
_SIDE = {"buy": "买入", "sell": "卖出", "减仓": "减仓", "买入": "买入"}
_MOVE = 0.07
_SHORT_STALE = 20
_RULE_KEYS = (
    "持仓",
    "波段",
    "进攻层",
    "标准层",
    "破位",
    "价格距离",
    "主题占比",
    "组合回撤",
    "跌幅",
    "参数",
    "冷静期",
    "异常",
)
_STYLE = Path(__file__).with_name("investor.css").read_text(encoding="utf-8")
_EXTRA = """
body:not(.intra) #intra-banner{display:none}
.hrow[hidden],.detail[hidden]{display:none}
"""


def render_brief(payload):
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("message") == CLOSED:
        return _document("非交易日", _header(payload) + '<main><div class="empty">非交易日</div></main>')
    page = payload.get("page")
    if page == "/stocks":
        main = _stocks(payload)
    elif page == "/account":
        main = _account(payload)
    elif page == "/trust":
        main = _trust(payload)
    elif isinstance(page, str) and page.startswith("/s/"):
        main = _stock(payload)
    elif page == "/search":
        main = _search_page(payload)
    else:
        main = _market(payload)
    title = payload.get("title") or "每日页面"
    body = _header(payload) + "<main>" + main + _foot(payload) + "</main>"
    return _document(title, body, refresh=bool(payload.get("is_today")))


# ---------- shared pieces ----------


def _pct(value, digits=2):
    """Fraction to a coloured percent. Colour only on the number itself."""
    if value is None:
        return '<span class="muted">暂缺</span>'
    return f'<span class="num {_tone(value)}">{_text(_signed(float(value) * 100, digits))}</span>'


def _pts(value, digits=1):
    """Percent points to a coloured percent."""
    if value is None:
        return '<span class="muted">暂缺</span>'
    return f'<span class="num {_tone(value)}">{_text(_signed(float(value), digits))}</span>'


def _signed(points, digits):
    number = half_up(points, digits)
    body = f"{abs(number):.{digits}f}%"
    if number < 0:
        return f"−{body}"
    if number > 0:
        return f"+{body}"
    return body


def _miss(text=MISSING):
    return f'<span class="chip miss">{_text(text)}</span>'


def _crumb(text):
    return f'<div class="crumb">{text}</div>'


def _valuation(view, full=False):
    """One line in the prototype format; missing parts are left out instead of printed as 暂缺."""
    if not isinstance(view, dict):
        return "估值暂缺"
    if view.get("state") == "未估值":
        short = short_unvalued_text(view.get("text") or "未估值")
        inner = short[len("未估值（") : -1] if short.startswith("未估值（") and short.endswith("）") else ""
        return f"未估值：{inner}" if inner else "未估值"
    bits = []
    if view.get("pe_extreme"):
        bits.append("市盈率不适用（盈利过低）")
    elif view.get("pe") is not None:
        bits.append(f"市盈率 {half_up(float(view['pe']), 1):.1f}")
    low, mid, high = view.get("pe_p25"), view.get("pe_p50"), view.get("pe_p75")
    if low is not None and low == mid == high:
        bits.append("历史样本不足")
    elif None not in (low, mid, high):
        bits.append(f"历史 25/50/75 分位 {_whole(low)}/{_whole(mid)}/{_whole(high)}")
    if view.get("implied_growth") is not None:
        bits.append(f"隐含增速 {half_up(float(view['implied_growth']), 1):.1f}%")
    elif view.get("implied_reason"):
        bits.append(str(view["implied_reason"]))
    if full:
        if view.get("rev_cagr_3y") is not None:
            bits.append(f"过去三年营收 {_signed(float(view['rev_cagr_3y']), 1)}")
        if view.get("eps_growth") is not None:
            bits.append(f"EPS 增速 {_signed(float(view['eps_growth']), 1)}")
    if view.get("state") == "模型不适用":
        bits.append("模型不适用")
    return " · ".join(bits) if bits else "估值暂缺"


def _settle_text(value, day):
    when = _as_date(value)
    if when is None:
        return None
    if day is not None and when.year != day.year:
        return when.isoformat()
    return f"{when.month}/{when.day}"


def _as_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# ---------- market ----------


def _market(payload):
    headings = payload.get("headings") or ["市场总览", "资金", "情绪：谨慎，未恐慌", "今天的大事"]
    judgment = payload.get("judgment") or MISSING
    closes = payload.get("index_closes") if isinstance(payload.get("index_closes"), dict) else {}
    cards = []
    for row in payload.get("indexes") or []:
        series = closes.get(row.get("id")) or []
        spark = (
            _spark(series) if len(series) >= 2 else '<div class="gap" style="margin-top:8px">近 20 日走势：待接入</div>'
        )
        ret = row.get("ret")
        big = MISSING if ret is None else _signed(float(ret) * 100, 2)
        intra = _intra_line((payload.get("intraday") or {}).get(row.get("id")))
        cards.append(
            f'<div class="card kpi"><div class="l">{_text(row.get("name"))}{_carry_tag(payload)}</div>'
            f'<div class="v {_tone(ret)}">{_text(big)}</div>'
            f'{intra}<div class="ft">盘后 {_pct(row.get("post"))}</div>{spark}</div>'
        )
    up, down = payload.get("advancers"), payload.get("decliners")
    total = (up or 0) + (down or 0)
    share = 0 if not total else (up or 0) / total * 100
    if up is None or down is None:
        breadth_note = "涨跌家数暂缺"
    else:
        lean = "多数股上涨" if up > down else "多数股下跌" if up < down else "涨跌各半"
        breadth_note = f"上涨占 {share:.0f}%，{lean}"
    cards.append(
        '<div class="card kpi"><div class="l">涨 / 跌家数</div>'
        f'<div class="v"><span class="up">{_count(up)}</span> / <span class="down">{_count(down)}</span></div>'
        f'<div class="bar" style="height:8px;background:#F1D4D0"><i style="width:{share:.0f}%;background:#A9D2BA">'
        "</i></div>"
        f'<div class="ft" style="margin-top:6px">{_text(breadth_note)}</div></div>'
    )
    red, orange, takes = (
        int(payload.get("down_red") or 0),
        int(payload.get("down_orange") or 0),
        len(payload.get("take_profits") or []),
    )
    implication = (
        str(payload.get("implication") or MISSING).replace("详见「我的标的」「纸面账户」。", "").rstrip("，；")
    )
    account = f"/account{_query(payload)}"
    risk = (
        f'账户下行风险 <a href="{account}"><span class="chip hi">! 重点 {red}</span> '
        f'<span class="chip mid">▲ 关注 {orange}</span></a>，止盈提示 {takes} 项。'
    )
    spread = payload.get("sector_spread_z")
    styles = "".join(
        f'<span class="chip ok">{_text(row.get("name"))} {_pct(row.get("ret"))}</span>'
        for row in payload.get("styles") or []
    )
    if spread is not None:
        styles += f'<span class="chip ok">板块分化 <span class="num">{float(spread):.1f}σ</span></span>'
    return (
        _crumb(f"市场总览 / {_text(payload.get('date'))}")
        + f"<h1>判断：{_text(judgment)}</h1>"
        + f'<p class="sub">{_text(_lead(payload))}</p>'
        + _carry_banner(payload)
        + _highlights_module(payload)
        + '<div class="card sec" style="border-left:4px solid var(--brand)"><h3>对我意味着什么</h3>'
        + f'<p style="margin:0">{_text(implication)}。{risk}</p></div>'
        + _live_module(payload)
        + _earnings_cards_module(payload)
        + _movers_module(payload)
        + _ticker_strip(payload)
        + _sector_strip(payload)
        + f'<div class="grid g4 sec">{"".join(cards)}</div>'
        + _theme_news_module(payload)
        + '<details class="fold sec"><summary>滚动新闻与日历</summary><div class="grid g2">'
        + _feed_module(payload)
        + _calendar_module(payload)
        + "</div></details>"
        + '<details class="fold"><summary>涨跌排行</summary>'
        + _leaderboards_module(payload)
        + "</details>"
        + '<div class="grid g-main sec"><div class="card">'
        + f"<h2>{_text(headings[1])}</h2>"
        + '<div class="grid g2" style="gap:24px">'
        + f'<div><div class="small muted">领跌</div>{_bars(payload.get("leaders_down") or [])}</div>'
        + f'<div><div class="small muted">领涨</div>{_bars(payload.get("leaders_up") or [])}</div></div>'
        + f'<div class="filters" style="margin-top:12px">{styles}</div>'
        + '<div class="gap" style="margin-top:12px">没有真实资金流，这里用板块相对强弱近似。</div>'
        + "</div>"
        + _mood(payload, headings[2])
        + "</div>"
        + f'<div class="card sec"><h2>{_text(headings[3])}</h2>{_events(payload)}</div>'
    )


def _lead(payload):
    text = str(payload.get("oneliner") or "")
    cut = text.find("，判断：")
    return text[:cut] if cut > 0 else text


def _spark(series):
    values = [float(item) for item in series[-20:]]
    low, high = min(values), max(values)
    span = high - low or 1
    last = len(values) - 1
    points = " ".join(
        f"{index / last * 200:.1f},{4 + (high - value) / span * 28:.1f}" for index, value in enumerate(values)
    )
    color = "var(--up)" if values[-1] >= values[0] else "var(--down)"
    change = _signed((values[-1] / values[0] - 1) * 100, 1) if values[0] else MISSING
    return (
        '<div style="margin-top:8px"><svg width="100%" height="36" viewBox="0 0 200 36" preserveAspectRatio="none" '
        f'role="img"><polyline fill="none" stroke="{color}" stroke-width="1.5" points="{points}"/></svg>'
        f'<div class="ft">近 20 日 <span class="num">{_text(change)}</span></div></div>'
    )


def _bars(rows, scale=10.0):
    if not rows:
        return f'<div class="small">{_miss()}</div>'
    lines = []
    for row in rows:
        value = row.get("ret")
        points = 0.0 if value is None else float(value) * 100
        width = min(50.0, abs(points) / scale * 50)
        side = (
            f"right:50%;width:{width:.1f}%;background:#E8B4AE"
            if points < 0
            else f"left:50%;width:{width:.1f}%;background:#A9D2BA"
        )
        lines.append(
            '<div style="display:grid;grid-template-columns:150px 1fr 64px;gap:10px;align-items:center;margin:6px 0">'
            f'<span class="small">{_text(row.get("name"))}</span>'
            '<div style="position:relative;height:14px"><div style="position:absolute;left:50%;top:0;bottom:0;'
            'border-left:1px solid var(--line)"></div>'
            f'<div style="position:absolute;top:2px;height:10px;border-radius:3px;{side}"></div></div>'
            f'<span class="r" style="text-align:right">{_pct(value)}</span></div>'
        )
    return "".join(lines)


def _mood(payload, heading):
    vix = payload.get("vix")
    pin = None if vix is None else max(0.0, min(100.0, (float(vix) - 10) / 30 * 100))
    gauge = (
        '<div class="gauge">'
        + (
            ""
            if pin is None
            else (
                f'<div class="pin" style="left:{pin:.1f}%"></div>'
                f'<div class="pl" style="left:{pin:.1f}%">{float(vix):.2f}</div>'
            )
        )
        + '<span class="zl" style="left:8%">乐观</span><span class="zl" style="left:35%">谨慎</span>'
        '<span class="zl" style="left:68%">紧张</span><span class="zl" style="left:92%">恐慌</span></div>'
    )
    vsrc = payload.get("vix_source")
    source = "（来源 " + str(vsrc) + "）" if vsrc else ""
    asof = payload.get("vix_asof")
    _pd = payload.get("date")
    if asof and _pd and str(asof)[:10] < str(_pd)[:10]:
        source += "（截至 " + str(asof)[5:10].replace("-", "/") + "）"

    vix3m, prev3m = payload.get("vix3m"), payload.get("vix3m_prev")
    if vix3m is None:
        term = _miss()
    else:
        term = f'<span class="num">{float(vix3m):.2f}</span>'
        if prev3m is not None:
            term += f' <span class="small muted">前日 {float(prev3m):.2f}</span>'
        if vix is not None:
            term += (
                ' <span class="small muted">· 期限结构' + ("正常" if float(vix3m) >= float(vix) else "倒挂") + "</span>"
            )
    put_call = payload.get("put_call_text")
    if put_call and put_call != MISSING:
        pc_html = _text(put_call)
    else:
        pc_html = _miss()
    down5 = payload.get("down_share_5d_pct")
    down5_html = _miss() if down5 is None else f'<span class="num">{half_up(float(down5), 1):.1f}%</span>'
    vix_html = _miss() if vix is None else f'<span class="num">{float(vix):.2f}</span>'
    return (
        f'<div class="card"><h2>{_text(heading)}</h2>'
        f'<div class="small muted">VIX{_text(source)}'
        + (' <span class="chip stale">过期</span>' if payload.get("vix_stale") else "")
        + f"</div>{gauge}"
        '<div class="kv">'
        f'<span class="k">VIX</span><span>{vix_html}</span>'
        f'<span class="k">3 个月 VIX</span><span>{term}</span>'
        f'<span class="k">期权看跌/看涨比</span><span>{pc_html}</span>'
        f'<span class="k">近 5 日下跌股占比</span><span>{down5_html}</span>'
        f'<span class="k">标普距一年高点</span><span>{_pts(payload.get("spy_drawdown_252_pct"), 2)}</span>'
        "</div></div>"
    )


def _events(payload):
    rows = payload.get("events") or []
    held = set(payload.get("held_tickers") or [])
    rets = payload.get("member_rets") if isinstance(payload.get("member_rets"), dict) else {}
    banner = ""
    if not payload.get("news_fresh"):
        banner = (
            '<div class="banner warn" style="margin:0 0 6px"><b>原因暂不可信</b>'
            "<span>当日新闻缺失，下列“可能原因”引用的是旧闻，只作参考。</span></div>"
        )
    blocks = []
    for index, row in enumerate(rows):
        z = MISSING if row.get("max_abs_z") is None else f"{float(row['max_abs_z']):.1f}σ"
        members = row.get("members") or []
        ticks = []
        for ticker in members:
            mark = " held" if ticker in held else ""
            ret = rets.get(ticker)
            move = "" if ret is None else " " + _signed(float(ret) * 100, 1)
            ticks.append(
                f'<a class="tick{mark}" href="{_symbol_href(payload, ticker)}">{_text(ticker)}{_text(move)}</a>'
            )
        items = row.get("reasons") or []
        reasons = [_reason_li(item) for item in items]
        if reasons:
            label = "可能原因 · 含旧闻" if any(item.get("stale_note") for item in items) else "可能原因"
            why = (
                f'<div style="margin-top:10px"><div class="small muted">{label}'
                f'</div><ul class="news">{"".join(reasons)}</ul></div>'
            )
        elif not payload.get("news_fresh"):
            why = '<div class="small muted" style="margin-top:8px">当日新闻缺失，原因解释不可用。</div>'
        else:
            why = '<div class="small muted" style="margin-top:8px">暂无可引用的解释。</div>'
        held_count = sum(1 for ticker in members if ticker in held)
        opened = " open" if index == 0 else ""
        blocks.append(
            f'<div class="event{opened}"><div class="h" data-ev>'
            '<div style="display:flex;gap:12px;align-items:baseline">'
            f'<span class="sig">{_text(z)}</span>{_event_title(row)}'
            f'<span class="small ink2">涉及持仓 {held_count} 只</span></div>'
            '<span class="small muted">展开 / 收起</span></div>'
            f'<div class="body"><div>{"".join(ticks)}</div>{why}</div></div>'
        )
    return banner + ("".join(blocks) or '<div class="empty">今天没有达到阈值的大事</div>')


def _event_title(row):
    title = f"<b>{_text(row.get('title'))}</b>"
    if row.get("event_id"):
        return f'<a href="/linkage/{_text(row["event_id"])}">{title}</a>'
    return title


def _reason_li(item):
    raw = item.get("cited_at")
    when = _utc_short(raw)
    stale = item.get("stale_note")
    chip = (
        f'<span class="chip stale" title="{_text(raw)}">{_text(stale)} · {_text(when)}</span>'
        if stale
        else f'<span class="small muted" title="{_text(raw)}">{_text(when)}</span>'
    )
    return f"<li>{_text(item.get('text') or MISSING)} {chip}</li>"


def _utc_short(value):
    text = "" if value is None else str(value)
    if len(text) >= 16 and text[4] == "-":
        return f"{text[5:10]} {text[11:16]} UTC"
    return text or MISSING


# ---------- stocks ----------


def _stocks(payload):
    themes = payload.get("themes") or []
    day = _day(payload)
    theme_rows = []
    flat = []
    for theme in themes:
        sector = theme.get("sector") or MISSING
        ticks = []
        for row in theme.get("members") or []:
            row = dict(row)
            row["sector"] = sector
            flat.append(row)
            mark = " held" if row.get("held") else ""
            ret = row.get("ret")
            move = "" if ret is None else " " + _signed(float(ret) * 100, 1)
            ticks.append(
                f'<a class="tick{mark}" '
                f'href="{_symbol_href(payload, row.get("ticker"))}">{_text(row.get("ticker"))}{_text(move)}</a>'
            )
        vol = theme.get("volume_multiple")
        held = int(theme.get("held_count") or 0)
        held_html = f'<span class="chip held">{held}</span>' if held else "0"
        avg = theme.get("average")
        points = 0.0 if avg is None else float(avg) * 100
        width = min(50.0, abs(points) / 12 * 50)
        side = (
            f"right:50%;width:{width:.1f}%;background:#E8B4AE"
            if points < 0
            else f"left:50%;width:{width:.1f}%;background:#A9D2BA"
        )
        theme_rows.append(
            f'<tr class="click" id="theme-{_text(str(sector).replace(" ", "-").replace("/", "-"))}" '
            f'data-th="{_text(sector)}"><td><b>{_text(sector)}</b></td>'
            '<td><div style="display:grid;grid-template-columns:1fr 70px;gap:8px;align-items:center">'
            '<div style="position:relative;height:12px"><div style="position:absolute;left:50%;top:-2px;bottom:-2px;'
            'border-left:1px solid var(--line)"></div>'
            f'<div style="position:absolute;top:1px;height:10px;border-radius:3px;{side}"></div></div>{_pct(avg)}'
            "</div></td>"
            f'<td class="r num {"" if vol is not None and vol >= 1.5 else "muted"}">{_text(_times(vol))}</td>'
            f'<td class="r num">{held_html} / {_count(theme.get("buyable_count"))}</td>'
            f'<td class="small">{_text(theme.get("line"))}</td></tr>'
            f'<tr class="members"{"" if theme.get("open") else " hidden"}><td colspan="5" style="background:#FAFCFB">'
            f"{''.join(ticks)}"
            f'<a href="#stable" class="small" data-only="{_text(sector)}" style="margin-left:8px">在下表只看这个主题 ↓'
            "</a>"
            "</td></tr>"
        )
    carried = max((row["carried_from"] for row in flat if row.get("carried_from")), default=None)
    carry_th = _carry_chip({"carried_from": carried})
    head = "".join(
        f'<th class="s{" r" if right else ""}" data-sc="{key}">{label}{carry_th if key == "rsi" else ""}</th>'
        for key, label, right in (
            ("t", "代码", False),
            ("theme", "主题", False),
            ("px", "现价", True),
            ("chg", "当日", True),
            ("vol", "量比", True),
            ("rsi", "RSI", True),
            ("d200", "距 200 日线", True),
            ("dhigh", "距一年高点", True),
            ("tech", "形态", True),
            ("st", "状态", False),
            ("event", "事件", False),
        )
    )
    rows = [_stock_row(payload, row, day) for row in flat]
    counts = {
        "all": len(flat),
        "held": sum(1 for row in flat if row.get("held")),
        "buy": sum(1 for row in flat if row.get("entry_pass") is True and not row.get("held")),
        "move": sum(1 for row in flat if _is_move(row)),
        "crowd": sum(1 for row in flat if isinstance(row.get("tech"), dict) and row["tech"].get("rsi_state") == "超买"),
    }
    filters = "".join(
        f'<button class="f{" on" if key == "all" else ""}" data-sf="{key}">{label}<span class="c">{counts[key]}'
        "</span></button>"
        for key, label in (("all", "全部"), ("held", "持仓"), ("buy", "可买"), ("move", "异动"), ("crowd", "超买"))
    )
    filters += (
        '<select class="f" id="sth"><option value="">全部主题</option>'
        + "".join(f"<option>{_text(theme.get('sector'))}</option>" for theme in themes)
        + '</select><input class="f" id="sq" placeholder="搜索代码" style="width:110px">'
    )
    total = len(flat)
    falling = sum(1 for row in flat if row.get("ret") is not None and row["ret"] < 0)
    strong = [theme.get("sector") for theme in themes if (theme.get("average") or 0) > 0.01][-3:]
    sub = f"{total} 只里 {falling} 只下跌"
    if strong:
        sub += f"；{'、'.join(strong)}逆势走强"
    return (
        _crumb(f"我的标的 / {_text(payload.get('date'))}")
        + f"<h1>{_text(payload.get('oneliner') or MISSING)}</h1>"
        + f'<p class="sub">{_text(sub)}。</p>'
        + '<div class="card sec"><div style="display:flex;justify-content:space-between"><h2>主题强弱</h2>'
        + '<span class="small muted">点击主题展开成员</span></div>'
        + '<table><thead><tr><th>主题</th><th style="width:30%">平均涨跌</th><th class="r">量比</th>'
        + '<th class="r">持有 / 可买</th><th>一句话</th></tr></thead>'
        + f'<tbody id="ttable">{"".join(theme_rows)}</tbody></table></div>'
        + '<div class="card sec">'
        + '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">'
        + f'<div class="hd"><h2>逐只明细</h2> <span class="num muted" id="scount">{total} / {total}</span></div>'
        + f'<div class="filters" id="sfilters">{filters}</div></div>'
        + f'<div style="overflow-x:auto"><table style="margin-top:10px"><thead><tr id="shead">{head}</tr></thead>'
        + f'<tbody id="stable">{"".join(rows)}</tbody></table></div>'
        + '<div class="small muted" style="margin-top:8px">点击表头排序；点击代码打开个股页。'
        + "异动 = 当日涨跌超过 ±7% 或量比 ≥ 2 倍；"
        + "超买 = RSI(14) ≥ 70（技术参考，不触发交易）。</div></div>"
    )


def _times(value):
    return MISSING if value is None else f"{half_up(float(value), 1):.1f}×"


def _is_move(row):
    ret, vol = row.get("ret"), row.get("volume_multiple")
    return (ret is not None and abs(float(ret)) >= _MOVE) or (vol is not None and float(vol) >= 2)


def _overbought(row):
    tech = row.get("tech")
    return isinstance(tech, dict) and tech.get("rsi_state") == "超买"


def _px_cell(row):
    price = row.get("snap_price")
    tag = row.get("snap_tag")
    if price is None:
        price = row.get("price")
        return f"{float(price):,.2f}" if price else '<span class="muted">暂缺</span>'
    small = f'<small class="muted">{_text(tag)}</small>' if tag else ""
    return f"{float(price):,.2f}{small}"


def _carry_chip(row):
    d = row.get("carried_from") or (row.get("score") or {}).get("carried_from")
    return f' <small class="chip stale">沿用 {str(d)[5:].replace("-", "/")} 收盘</small>' if d else ""


def _bj_tz():
    from zoneinfo import ZoneInfo

    return ZoneInfo("Asia/Shanghai")


def _bj_hhmm(moment):
    return (
        moment.astimezone(_bj_tz()).strftime("%H:%M 北京") if hasattr(moment, "astimezone") else str(moment or "")[:16]
    )


def _stock_row(payload, row, day):
    ticker = row.get("ticker") or ""
    ret = row.get("ret")
    shown_ret = row.get("snap_ret") if (payload.get("is_today") and row.get("snap_ret") is not None) else ret
    vol = row.get("volume_multiple")
    held = bool(row.get("held"))
    buy = row.get("entry_pass") is True and not held
    if held:
        status = '<span class="chip held">持有</span>'
    elif buy:
        status = '<span class="chip buy">可买</span>'
    else:
        status = '<span class="small muted">不可买</span>'
    rsi = row.get("rsi")
    if rsi is None:
        rsi_html = '<span class="muted">暂缺</span>'
    else:
        shown = int(half_up(rsi, 0))
        note = " 超卖" if shown < 30 else " 超买" if shown > 70 else ""
        rsi_html = f"{shown}" + (f'<span class="small muted">{note}</span>' if note else "")
    events = [re.sub(r"\s*(同日|集体)(下跌|上涨)$", "", str(item)) for item in row.get("events") or []]
    attrs = " ".join(
        [
            f'data-ticker="{_text(ticker)}"',
            f'data-theme="{_text(row.get("sector") or "")}"',
            f'data-held="{1 if held else 0}"',
            f'data-buy="{1 if buy else 0}"',
            f'data-move="{1 if _is_move(row) else 0}"',
            f'data-crowd="{1 if _overbought(row) else 0}"',
            f'data-chg="{_num_attr(shown_ret)}"',
            f'data-vol="{_num_attr(vol)}"',
            f'data-rsi="{_num_attr(rsi)}"',
            f'data-d200="{_num_attr(row.get("price_vs_ma200"))}"',
            f'data-dhigh="{_num_attr(row.get("drawdown252"))}"',
            f'data-tech="{_num_attr((row.get("tech") or {}).get("rsi"))}"',
            f'data-st="{0 if held else 1 if buy else 2}"',
            f'data-t="{_text(ticker)}"',
            f'data-event="{_text("、".join(events))}"',
        ]
    )
    return (
        f"<tr {attrs}>"
        f'<td><a class="mono" href="{_symbol_href(payload, ticker)}"><b>{_text(ticker)}</b></a></td>'
        f'<td class="small">{_text(row.get("sector"))}</td>'
        f'<td class="r">{_px_cell(row)}</td>'
        f'<td class="r">{_pct(shown_ret)}</td>'
        f'<td class="r num {"" if vol is not None and vol >= 2 else "muted"}">{_text(_times(vol))}</td>'
        f'<td class="r num">{rsi_html}</td>'
        f'<td class="r">{_pts(row.get("price_vs_ma200"))}</td>'
        f'<td class="r">{_pts(row.get("drawdown252"))}</td>'
        f'<td class="r small">{_tech_cell(row.get("tech"))}</td>'
        f"<td>{status}</td>"
        f'<td class="small ink2">{_text("、".join(events) or "—")}</td></tr>'
    )


# ---------- account ----------


_PENDING_RE = re.compile(r"待成交[：:]\s*([^（(]+)[（(]?([^）)]*)")
_EVENT_RE = re.compile(r"卷入[^，。；]+")
_CLAUSE_RE = re.compile(r"下一次计划将减仓 [\d.]+%|持有不足 \d+ 个交易日，暂不减仓|恐慌模式下暂停[^，。；]*")
_GAP_RE = re.compile(r"(质量分|成长分) ([\d.]+) → 门槛 ([\d.]+)，还差 ([\d.]+) 分")


def _account(payload):
    red = int(payload.get("down_red") or 0)
    orange = int(payload.get("down_orange") or 0)
    takes = payload.get("take_profits") or []
    pending = payload.get("pending_orders") or []
    holdings = payload.get("holdings") or []
    title = f"{red} 项重点下行风险"
    if pending:
        title += f"，{_text(pending[0].get('ticker'))} {_text(_side(pending[0]))}单待成交"
    banner = ""
    if payload.get("plan_missing"):
        carried = payload.get("carried_from") or MISSING
        banner = (
            '<div class="banner warn"><b>计划缺失</b><span>'
            f"{_text(payload.get('date'))} 计划缺失，以下沿用 {_text(carried)} 日持仓，不代表空仓；"
            "价位与条件按当日收盘重新计算。原因见「复盘与数据」。</span></div>"
        )
    estimate = payload.get("close_estimate") if isinstance(payload.get("close_estimate"), dict) else {}
    label = estimate.get("label") or ""
    equity = estimate.get("equity") if estimate else payload.get("equity")
    pnl = estimate.get("day_pnl") if estimate else None
    change = payload.get("day_change")
    pnl_text = MISSING if pnl is None else ("−" if pnl < 0 else "+" if pnl > 0 else "") + money(abs(pnl))
    change_text = MISSING if change is None else _signed(float(change) * 100, 2)
    card = payload.get("risk_card") if isinstance(payload.get("risk_card"), dict) else {}
    cash_ratio = card.get("cash_ratio")
    kpis = (
        f'<div class="card kpi"><div class="l">总资产</div><div class="v">{money(equity)}</div>'
        f'<div class="ft">{_text(label)}</div></div>'
        f'<div class="card kpi"><div class="l">当日损益</div><div class="v {_tone(pnl)}">{_text(pnl_text)}</div>'
        f'<div class="ft">{_text(change_text)} · {_text(label or "按收盘估算")}</div></div>'
        '<div class="card kpi"><div class="l">距历史高点</div>'
        f'<div class="v">{_text(format_fraction(payload.get("drawdown")))}</div>'
        '<div class="ft">与回撤刹车同一口径</div></div>'
        f'<div class="card kpi"><div class="l">现金</div><div class="v">{money(payload.get("cash"))}</div>'
        f'<div class="ft">占总资产 {_text(format_plain_percent(cash_ratio))}</div></div>'
    )
    return (
        banner
        + _crumb("纸面账户 / 每日持仓检查")
        + '<div style="display:flex;justify-content:space-between;align-items:flex-end;gap:20px">'
        + f'<div><h1>{title}</h1><p class="sub">{len(holdings)} 只持仓 · 下行风险：重点 {red} / 关注 {orange} · '
        + f"止盈提示 {len(takes)} 项（不计入风险）</p></div>"
        + f'<div class="small muted" style="text-align:right">{_text(PAPER_LABEL)}</div></div>'
        + f'<div class="grid g4 sec">{kpis}</div>'
        + '<div class="grid g-main sec"><div class="card">'
        + '<div style="display:flex;justify-content:space-between;align-items:center">'
        + '<div class="hd"><h2>今天先看这些</h2></div>'
        + '<span class="legend"><span>'
        + '<span class="ico hi" style="width:16px;height:16px;font-size:10px">!</span> 重点下行</span>'
        + '<span><span class="ico mid" style="width:16px;height:16px;font-size:10px">▲'
        + "</span> 下行关注</span></span></div>"
        + _risk_groups(payload)
        + _earnings_chips(payload)
        + '</div><div class="card"><h2>组合边界</h2>'
        + _bounds(payload)
        + "</div></div>"
        + _holdings_card(payload)
        + '<div class="grid g2 sec"><div class="card">'
        + f'<div class="hd"><h2>待成交</h2> <span class="num muted">{len(pending)}</span></div>'
        + _pending(payload)
        + "</div>"
        + '<div class="card"><div class="hd"><h2>处置记录</h2> <span class="small muted">近 10 个交易日</span></div>'
        + _closed(payload)
        + "</div></div>"
        + _candidates(payload)
        + _rule_notes(payload)
    )


def _rule_notes(payload):
    lines = [line for line in payload.get("formulas") or [] if any(key in str(line) for key in _RULE_KEYS)]
    if not lines:
        return ""
    body = "".join(f"<p>{_text(_formula(line))}</p>" for line in lines)
    return f'<details class="method"><summary>规则 A 卖出规则说明</summary><div>{body}</div></details>'


def _side(order):
    reason = human_reason(order.get("reason")) or ""
    if "减仓" in reason:
        return "减仓"
    return _SIDE.get(order.get("side"), "卖出")


def _holding_map(payload):
    return {row.get("ticker"): row for row in payload.get("holdings") or []}


def _risk_brief(payload, line):
    """One-line conclusion plus one supporting line, built from the holding's own rule states."""
    ticker = line.get("ticker")
    row = _holding_map(payload).get(ticker) or {}
    text = str(line.get("text") or "")
    phrases = []
    details = []
    pending = [order for order in payload.get("pending_orders") or [] if order.get("ticker") == ticker]
    for order in pending:
        reason = human_reason(order.get("reason")) or "订单"
        phrases.append((0, f"{reason}单待成交"))
    levels = row.get("levels") or []
    for level in levels:
        name = str(level.get("name") or "")
        body = str(level.get("text") or "")
        if name == "基本面清仓":
            gaps = [(float(m.group(4)), m.group(1), m.group(2), m.group(3)) for m in _GAP_RE.finditer(body)]
            if gaps:
                gap, which, now, need = min(gaps)
                if gap < 10:
                    phrases.append((1, f"{which[:2]}分离清仓门槛只差 {gap:g} 分"))
                    details.append(f"{which[:2]} {now} → 清仓门槛 {need}")
        elif name == "破位减仓":
            now, need = level.get("current"), level.get("trigger")
            if level.get("status") == "done":
                details.append("破位减仓已执行")
            elif isinstance(now, (int, float)) and isinstance(need, (int, float)) and 0 < now < need:
                left = int(need - now)
                phrases.append((2, f"再有 {left} 天低于 200 日线就触发破位减仓"))
                details.append(f"连续 {int(now)} / {int(need)} 天")
            elif isinstance(now, (int, float)) and isinstance(need, (int, float)) and now >= need > 0:
                phrases.append((2, "已达破位减仓门槛"))
                details.append(f"连续 {int(now)} / {int(need)} 天")
        elif name in ("灾难止损价", "波段止损价"):
            gap = level.get("gap")
            if isinstance(gap, (int, float)) and gap < 0.20:
                short = name.removesuffix("价")
                phrases.append((3, f"离{short}还需下跌 {half_up(gap * 100, 1):.1f}%"))
                details.append(money(level.get("trigger")))
                for cond in level.get("conds") or []:
                    if "200" in str(cond.get("text")):
                        details.append("已低于 200 日线" if cond.get("ok") else "尚高于 200 日线")
                if name == "波段止损价":
                    details.append("成本 × 82%")
    details.extend(_CLAUSE_RE.findall(text))
    day = row.get("day")
    if isinstance(day, (int, float)) and day <= -0.05:
        phrases.append((4, f"今日 {_signed(day * 100, 1)}"))
    event = _EVENT_RE.search(text)
    if event:
        phrases.append((5, event.group(0)))
    ma200, price = row.get("ma200"), row.get("price")
    if (
        isinstance(ma200, (int, float))
        and isinstance(price, (int, float))
        and ma200
        and not any("200 日线" in item for item in details)
    ):
        gap = price / ma200 - 1
        details.append(
            ("已低于" if gap < 0 else "高于") + f" 200 日线 {half_up(abs(gap) * 100, 1):.1f}%（{money(ma200)}）"
        )
    phrases.sort(key=lambda item: item[0])
    words = [item[1] for item in phrases]
    if not words:
        return text.removeprefix(f"{ticker} ").rstrip("。"), ""
    head = words[0]
    rest = words[1:]
    if rest and len(head) + len(rest[0]) <= 26:
        head = f"{head}；{rest[0]}"
        rest = rest[1:]
    return head, " · ".join([*rest, *details])


def _take_brief(payload, line):
    ticker = line.get("ticker")
    row = _holding_map(payload).get(ticker) or {}
    for level in row.get("levels") or []:
        name = str(level.get("name") or "")
        if "止盈" not in name:
            continue
        gap = level.get("gap")
        short = name.removesuffix("价")
        if gap == 0 and level.get("status") == "hold":
            failing = [str(cond.get("text")) for cond in level.get("conds") or [] if not cond.get("ok")]
            sub = f"{money(level.get('trigger'))} 已越过" + ("" if not failing else " · 未满足：" + "；".join(failing))
            return f"{short.removesuffix('价')}价已到，附加条件未齐暂不执行", sub
        if level.get("risk_level") and isinstance(gap, (int, float)):
            return f"{short}还需上涨 {half_up(gap * 100, 1):.1f}%", f"止盈价 {money(level.get('trigger'))}"
    return str(line.get("text") or "").removeprefix(f"{ticker} ").rstrip("。"), ""


def _risk_item(ticker, icon, cls, head, sub, go="定位 →"):
    return (
        f'<div class="ritem" data-go="{_text(ticker)}"><span class="ico {cls}">{icon}</span>'
        f'<div><div class="t"><span class="mono">{_text(ticker)}</span> · {_text(head)}</div>'
        + (f'<div class="s">{_text(sub)}</div>' if sub else "")
        + f'</div><span class="go">{go}</span></div>'
    )


def _risk_groups(payload):
    downs = [row for row in payload.get("risk_lines") or [] if row.get("ticker")]
    takes = payload.get("take_profits") or []
    items = []
    for row in downs:
        head, sub = _risk_brief(payload, row)
        red = row.get("level") == "red"
        items.append(_risk_item(row.get("ticker"), "!" if red else "▲", "hi" if red else "mid", head, sub))
    shown, extra = items[:5], items[5:]
    more = ""
    if extra:
        names = " · ".join(_text(row.get("ticker")) for row in downs[5:])
        more = (
            f'<div class="rlist" id="rmore-list" hidden>{"".join(extra)}</div>'
            f'<span class="more" data-more>展开其余 {len(extra)} 项关注：{names} ↓</span>'
        )
    down_html = "".join(shown) or '<div class="empty">当前没有需要关注的下行风险</div>'
    take_html = "".join(
        _risk_item(row.get("ticker"), "↗", "tp", *_take_brief(payload, row), go="查看 →") for row in takes
    )
    return (
        '<div class="rgroup">下行风险</div><div class="rlist" id="rlist">'
        + down_html
        + "</div>"
        + more
        + '<div class="rgroup" style="margin-top:14px">止盈提示 · 不计入风险</div><div class="rlist">'
        + (take_html or '<div class="empty">当前没有止盈提示</div>')
        + "</div>"
    )


def _bounds(payload):
    card = payload.get("risk_card") if isinstance(payload.get("risk_card"), dict) else {}
    bars = []
    for theme in card.get("themes") or []:
        share = theme.get("share")
        width = 0 if share is None else max(0, min(100, float(share) / 0.40 * 100))
        bars.append(
            f'<div class="conc"><span>{_text(theme.get("sector"))}</span>'
            f'<span class="num" style="text-align:right">{format_plain_percent(share)}</span>'
            f'<div class="bar" style="grid-column:1/-1"><i style="width:{width:.1f}%"></i>'
            '<span class="th" style="left:62.5%"></span><span class="th" style="left:87.5%"></span></div></div>'
        )
    drawdown = payload.get("drawdown")
    dd8, dd12 = _triggers(payload.get("params_version"))
    holdings, slots = card.get("holdings"), card.get("slots")
    full = isinstance(holdings, int) and isinstance(slots, int) and holdings >= slots
    return (
        '<div class="small muted">主题集中度 · 关注线 25% · 高风险线 35%</div>'
        + ("".join(bars) or f'<div class="small">{_miss()}</div>')
        + _axis(drawdown, dd8, dd12)
        + f'<p style="margin:10px 0 0">离回撤刹车{_text(card.get("dd8_gap") or MISSING)}，'
        + f"离更深闸门{_text(card.get('dd12_gap') or MISSING)}</p>"
        + '<div style="border-top:1px solid var(--line2);margin-top:14px;padding-top:12px" class="kv">'
        + f'<span class="k">持仓 / 名额</span><span><b class="num">{_count(holdings)} / {_count(slots)}</b>'
        + (' <span class="small muted">暂无新增名额</span>' if full else "")
        + "</span>"
        + '<span class="k">现金比例</span>'
        + f'<span class="num">{format_plain_percent(card.get("cash_ratio"))}</span></div>'
    )


def _triggers(version):
    if not version:
        return None, None
    try:
        risk = risk_params(version)
    except (OSError, KeyError, TypeError):
        return None, None
    return risk.get("dd8_trigger"), risk.get("dd12_trigger")


def _axis(drawdown, dd8, dd12):
    def place(points):
        if points is None:
            return None
        return max(0.0, min(100.0, (float(points) - (-14)) / 14 * 100))

    current = None if drawdown is None else float(drawdown) * 100
    marks = []
    if place(dd12) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(dd12):.1f}%;top:4px;height:20px;border-left:2px solid '
            'var(--r-hi-line)"></div>'
        )
    if place(dd8) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(dd8):.1f}%;top:4px;height:20px;border-left:2px solid '
            'var(--r-mid-line)"></div>'
        )
    if place(current) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(current):.1f}%;top:6px;width:14px;height:14px;'
            'margin-left:-7px;border-radius:50%;background:var(--ink)"></div>'
        )
    dd8_label = MISSING if dd8 is None else _signed(float(dd8), 0)
    dd12_label = MISSING if dd12 is None else _signed(float(dd12), 0)
    return (
        '<div class="gate"><div class="small muted">组合回撤</div><div class="track"><div class="axis"></div>'
        + "".join(marks)
        + '</div><div class="small" style="display:flex;justify-content:space-between">'
        + f'<span style="color:var(--r-hi)">更深闸门 {_text(dd12_label)}</span>'
        + f'<span style="color:var(--r-mid)">回撤刹车 {_text(dd8_label)}</span>'
        + f'<span class="num">当前 {_text(format_fraction(drawdown))}</span><span class="muted">0</span></div></div>'
    )


def _holdings_card(payload):
    rows = payload.get("holdings") or []
    downs = {row.get("ticker") for row in payload.get("risk_lines") or []}
    takes = {row.get("ticker") for row in payload.get("take_profits") or []}
    core = sum(1 for row in rows if row.get("kind_label") != "观察波段仓")
    filters = "".join(
        f'<button class="f{" on" if key == "all" else ""}" data-hf="{key}">{label}<span class="c">{count}</span>'
        "</button>"
        for key, label, count in (
            ("all", "全部持仓", len(rows)),
            ("down", "下行风险", len(downs)),
            ("tp", "止盈提示", len(takes)),
            ("core", "核心仓", core),
            ("swing", "观察波段仓", len(rows) - core),
        )
    )
    legend = (
        '<div class="legend"><span><i style="background:var(--r-hi-line)"></i>止损 / 灾难</span>'
        '<span><i style="background:var(--tp-line)"></i>止盈</span><span><i style="background:#9AA19F"></i>成本</span>'
        '<span><span style="display:inline-block;width:14px;border-top:2px dashed '
        'var(--ref);margin-right:4px;vertical-align:3px"></span>'
        '200 日线（参考）</span><span><i style="background:var(--ink)"></i>现价</span></div>'
    )
    return (
        '<div class="card sec" style="padding:0;overflow:hidden">'
        '<div style="padding:18px 18px '
        '12px;display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap">'
        '<div><div class="hd"><h2>持仓与关键价位</h2></div><div class="small ink2">价格尺只画该持仓类型适用的价位；'
        "实线着色 = 现价到最近触发价的距离；没有价格触发线的核心仓，用虚线标出到 200 "
        "日线的距离。点击一行在原位展开全部条件。"
        "</div>"
        "</div>" + legend + "</div>"
        '<div style="padding:0 18px 14px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">'
        f'<div class="filters" id="hfilters">{filters}</div>'
        '<div class="filters"><span class="small muted">排序</span><button class="f on" data-s="risk">风险优先</button>'
        '<button class="f" data-s="pnl">盈亏</button><button class="f" data-s="day">当日涨跌</button></div></div>'
        '<div class="hhead"><span>股票 / 持仓类型</span><span>成本 → 现价 / 盈亏</span><span>适用价位</span>'
        "<span>下一步 / 估值</span><span></span></div>"
        f'<div id="hlist">{_holdings(payload)}</div></div>'
    )


def _next_view(step):
    text = str(step or MISSING)
    hit = _PENDING_RE.search(text)
    if hit:
        reason = human_reason(hit.group(1)).strip()
        note = hit.group(2).strip()
        return f"待成交：{reason}", note
    if "额度已满" in text:
        return text, ""
    if text in ("继续持有", MISSING):
        return text, ""
    return text, "今日计划（计划记录，尚未成交）"


def _holdings(payload):
    downs = {row.get("ticker"): row for row in payload.get("risk_lines") or []}
    takes = {row.get("ticker") for row in payload.get("take_profits") or []}
    blocks = []
    for row in payload.get("holdings") or []:
        ticker = row.get("ticker") or ""
        level = row.get("risk_level") or (downs.get(ticker) or {}).get("level")
        chips = []
        rank, lv = 3, "ok"
        if level == "red":
            chips.append('<span class="chip hi">! 重点下行</span>')
            rank, lv = 0, "hi"
        elif level == "orange":
            chips.append('<span class="chip mid">▲ 下行关注</span>')
            rank, lv = 1, "mid"
        if ticker in takes:
            chips.append('<span class="chip tp">↗ 止盈提示</span>')
            if rank == 3:
                rank, lv = 2, "tp"
        if not chips:
            chips.append('<span class="chip ok">正常</span>')
        kind = row.get("kind_label") or MISSING
        day, pnl = row.get("day"), row.get("pnl")
        lead, note = _next_view(row.get("next_step"))
        spec = row.get("ruler") if isinstance(row.get("ruler"), dict) else {}
        swing_note = "观察波段仓不适用破位、灾难、警戒规则。" if kind == "观察波段仓" else ""
        blocks.append(
            f'<div class="hrow" id="row-{_text(ticker)}" data-row="{_text(ticker)}" data-lv="{lv}" '
            f'data-rank="{rank}" data-kind="{_text(kind)}" data-tp="{1 if ticker in takes else 0}" '
            f'data-pnl="{_num_attr(pnl)}" data-day="{_num_attr(day)}">'
            f'<div><div class="tk">{_text(ticker)}</div><div class="ty">{_text(kind)}</div></div>'
            f'<div><div class="px">{money(row.get("avg_cost"))} → {money(row.get("price"))}</div>'
            f'<div class="pl {_tone(pnl)}">{_text(MISSING if pnl is None else _signed(float(pnl) * 100, 1))}</div>'
            f'<div class="small muted">当日 {_pct(day)} · {_text(_shares(row.get("shares")))} 股</div></div>'
            f"{_ruler_box(spec)}"
            f'<div class="c-next"><div>{"".join(chips)}</div><div class="nx"><div class="lead">{_text(lead)}</div>'
            + (f'<div class="small ink2">{_text(note)}</div>' if note else "")
            + f'<div class="small muted" style="margin-top:4px">{_text(_valuation(row.get("valuation")))}'
            + "</div></div></div>"
            '<span class="caret">›</span></div>'
            f'<div class="detail" id="det-{_text(ticker)}"><div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin-top:10px"><b>{_text(ticker)} · {_text(kind)} · 适用的离场条件</b>'
            f'<span class="small"><a href="{_symbol_href(payload, ticker)}">打开个股页 →</a> · '
            f'<a href="javascript:void 0" data-close="{_text(ticker)}">收起 ↑</a></span></div>'
            f'<div class="small ink2">价格门槛与附加条件分别判断；风险提示不代表已生成订单。{swing_note}</div>'
            f'<div class="rules">{_rules(row.get("levels") or [])}</div></div>'
        )
    return "".join(blocks) or '<div class="empty">当前没有持仓</div>'


def _rule_lines(level):
    """Split the level sentence into a value line and a note line; conditions already have their own list."""
    text = str(level.get("text") or MISSING)
    name = str(level.get("name") or "")
    body = text.split("：", 1)[1] if "：" in text else text
    head, _, tail = body.partition("。")
    parts = [part.strip() for part in head.split("；") if part.strip() and "账本版本" not in part]
    value = [part for part in parts if "→" in part] or parts[:1]
    note = [part for part in parts if part not in value]
    if tail.strip() and not level.get("conds"):
        note.append(tail.strip().rstrip("。"))
    elif "附加条件当前" in tail:
        note.append("附加条件当前" + tail.rsplit("附加条件当前", 1)[1].strip().rstrip("。"))
    if level.get("pending_note"):
        note.insert(0, str(level["pending_note"]))
    shown = " · ".join(item.replace("质量分 ", "质量 ").replace("成长分 ", "成长 ") for item in value)
    return name.removesuffix("价"), shown, "；".join(note)


def _rules(levels):
    cards = []
    for row in levels:
        status = row.get("status") or "none"
        label = _RULE_STATE.get(status, _RULE_STATE["none"])
        name, value, note = _rule_lines(row)
        conds = []
        for cond in row.get("conds") or []:
            ok = bool(cond.get("ok"))
            extra = f' <span class="muted">（{_text(cond.get("note"))}）</span>' if cond.get("note") else ""
            conds.append(
                f'<li><span class="{"y" if ok else "n2"}">{"✓" if ok else "✗"}</span>'
                f"<span>{_text(cond.get('text'))}{extra}</span></li>"
            )
        cards.append(
            f'<div class="rule st-{_text(status)}"><div class="h"><span class="n">{_text(name)}</span>'
            f'<span class="stc">{label}</span></div><div class="v">{_text(value)}</div>'
            + (f'<ul class="conds">{"".join(conds)}</ul>' if conds else "")
            + (f'<div class="x">{_text(note)}</div>' if note else "")
            + "</div>"
        )
    return "".join(cards) or f'<div class="small">{_miss()}</div>'


def _pending(payload):
    rows = []
    for row in payload.get("pending_orders") or []:
        qty = row.get("qty")
        qty_html = _miss() if qty is None else f'<span class="num">{_text(_shares(qty))}</span>'
        side = _side(row)
        cls = "hi" if side in ("减仓", "卖出") else "buy"
        rows.append(
            f'<tr class="click" data-go="{_text(row.get("ticker"))}"><td class="mono">'
            f"<b>{_text(row.get('ticker'))}</b></td>"
            f'<td><span class="chip {cls}">{_text(side)}</span></td>'
            f'<td class="small">{_text(human_reason(row.get("reason")) or MISSING)}</td>'
            f'<td class="num">{_text(_md(row.get("since")))}</td><td class="r">{qty_html}</td></tr>'
        )
    note = (
        ""
        if payload.get("fills_readable", True)
        else '<div class="small muted">成交记录暂不可读，下面只显示计划。</div>'
    )
    if not rows:
        return note + '<div class="empty">当前没有待成交订单</div>'
    return (
        note
        + '<table><tr><th>股票</th><th>方向</th><th>原因</th><th>起始</th><th class="r">数量</th></tr>'
        + "".join(rows)
        + '</table><div class="small muted" style="margin-top:8px">'
        + "按下一交易日开盘价成交；数量在成交时由规则 A 账本确定。"
        + "</div>"
    )


def _md(value):
    when = _as_date(value)
    return MISSING if when is None else f"{when.month:02d}-{when.day:02d}"


_STATE_CHIP = {
    "已成交": "ok",
    "待成交": "mid",
    "过期未成交": "stale",
    "被新计划替代": "stale",
    "已取消": "stale",
    "未执行": "stale",
}


def _closed(payload):
    rows = []
    for row in reversed(payload.get("closed_records") or []):
        state = row.get("fill_state") or "计划"
        bits = [state]
        if state == "已成交":
            if row.get("fill_price") is not None:
                bits.append(money(row.get("fill_price")))
            if row.get("qty") is not None:
                bits.append(f"{_shares(row.get('qty'))} 股")
        label = " · ".join(bits)
        repeat = int(row.get("repeat") or 1)
        if repeat > 1:
            label += f" ×{repeat}"
        chip = _STATE_CHIP.get(state, "ok")
        rows.append(
            f'<tr><td class="num">{_text(_md(row.get("trade_date")))}</td><td class="mono">'
            f"<b>{_text(row.get('ticker'))}</b></td>"
            f"<td>{_text(_kind_label(row.get('kind')))}</td>"
            f"<td>{_text(human_reason(row.get('reason_zh')) or MISSING)}</td>"
            f'<td><span class="chip {chip}">{_text(label)}</span></td></tr>'
        )
    if not rows:
        return '<div class="empty">近期没有处置记录</div>'
    return (
        "<table><tr><th>日期</th><th>股票</th><th>动作</th><th>原因</th><th>状态</th></tr>"
        + "".join(rows)
        + '</table><div class="small muted" style="margin-top:8px">“计划”= 规则 A 计划记录，尚无对应订单；'
        "同一天、同一股票、同一原因只显示一行，×N 表示计划重复出现的次数。</div>"
    )


def _candidates(payload):
    rows = []
    card = payload.get("risk_card") if isinstance(payload.get("risk_card"), dict) else {}
    holdings, slots = card.get("holdings"), card.get("slots")
    for row in payload.get("candidates") or []:
        books = row.get("books") or {}
        score = " / ".join(_score(books.get(key)) for key in ("quality", "growth", "valuation", "timing"))
        rows.append(
            f'<tr><td><a class="mono" href="{_symbol_href(payload, row.get("ticker"))}">'
            f"<b>{_text(row.get('ticker'))}</b></a></td>"
            f'<td class="small">{_text(row.get("sector") or MISSING)}</td>'
            f'<td class="r num">{money(row.get("price"))}</td><td class="r">{_pct(row.get("ret"))}</td>'
            f'<td class="r num">{money(row.get("ma50"))}</td><td class="r num">{money(row.get("year_high"))}</td>'
            f'<td class="num small">{_text(score)}</td>'
            f'<td class="small ink2">{_text(_valuation(row.get("valuation")))}</td></tr>'
        )
    if isinstance(holdings, int) and isinstance(slots, int) and holdings >= slots:
        note = f"名额已满（{holdings} / {slots}），暂不会开新仓；列出供观察。"
    else:
        note = "符合买入条件，尚未持有。"
    body = (
        '<table style="margin-top:10px"><thead><tr><th>股票</th><th>主题</th><th class="r">现价</th><th class="r">当日'
        "</th>"
        '<th class="r">50 日线</th><th class="r">一年高点</th><th>质量 / 成长 / 估值 / 择时</th><th>估值参考</th></tr>'
        "</thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        if rows
        else '<div class="empty">今天没有符合买入条件的待选股票</div>'
    )
    return (
        '<div class="card sec"><div style="display:flex;justify-content:space-between;align-items:flex-end">'
        '<div><div class="hd"><h2>待选股票</h2> <span class="small muted">符合买入条件，尚未持有</span></div>'
        f'<div class="small ink2">{_text(note)}'
        "</div>"
        "</div>"
        f'<span class="small muted">{len(rows)} 只</span></div>{body}</div>'
    )


# ---------- trust ----------


_TRUST_NAME = {"M9": "冷静期覆盖层", "计划": "纸面计划"}
_TRUST_IMPACT = {
    "新闻": "大事原因标“暂不可信”，只能引用旧闻；价格、持仓和规则 A 计算不受影响。",
    "VIX": "市场情绪可用；行情汇总缺 VIX 时改用 FRED 官方数据。",
    "冷静期覆盖层": "页面不显示冷静期；规则 A 照常执行，不受影响。",
    "估值": "多数成长股、周期股估值模型不适用，页面只显示市盈率、历史分位和隐含增速，不给出估值价位。",
    "订单": "过期和被替代的旧单已标终态；待成交单按下一交易日开盘价成交。",
    "纸面计划": "计划缺失的日子，账户页沿用最近一次持仓并提示，不显示成空仓。",
    "期权数据": "看跌/看涨比不参与情绪判断；超过 2 个交易日即视为过期。",
}


def _trust_chip(state):
    text = str(state or MISSING)
    if any(word in text for word in ("缺失", "未上线")):
        return "miss"
    if "过期" in text:
        return "stale"
    if any(word in text for word in ("不适用", "部分")):
        return "mid"
    return "ok"


def _trust(payload):
    cards = []
    bad = 0
    news_bad = False
    for item in payload.get("statuses") or []:
        raw_name = str(item.get("item") or MISSING)
        name = _TRUST_NAME.get(raw_name, raw_name)
        state = str(item.get("state") or MISSING).replace("未上线/缺失", "未上线")
        cls = _trust_chip(state)
        bad += cls != "ok"
        if raw_name == "新闻":
            news_bad = cls != "ok"
            extra = (
                f"最近入库 {_text(payload.get('news_seen_beijing') or MISSING)} · "
                f"最近 1 个交易日 {_count(payload.get('news_day_count'))} 条"
            )
        else:
            extra = _text(item.get("detail") or "")
        cards.append(
            f'<div class="stat" data-stat><div class="h"><b>{_text(name)}</b>'
            f'<span class="chip {cls}">{_text(state)}</span></div>'
            f'<div class="w">{extra or "&nbsp;"}</div><div class="imp"><b>影响：'
            f"</b>{_text(_TRUST_IMPACT.get(name, '见该项状态。'))}</div></div>"
        )
    title = f"{bad} 项数据有缺口" + ("：今天的“原因”解释不可信" if news_bad else "")
    sub = (
        "新闻缺失时，大事原因只能引用旧闻；价格、持仓、规则 A 计算不受影响。"
        if news_bad
        else "下面逐项列出数据状态和影响。"
    )
    if payload.get("labels"):
        review = "".join(
            f"<p>{_text(row.get('horizon'))} {_text(row.get('as_of'))} {_text(row.get('reason') or '')}</p>"
            for row in payload["labels"]
        )
    else:
        review = (
            '<div class="empty">还没有完成的复盘记录。<br><span class="small">积累后显示：事后 1 / 5 / 20 个交易日，'
            "异常发现、原因解释和规则 A 动作的命中率。</span></div>"
            f'<div class="small muted" style="margin-top:8px">{_text(payload.get("review_gap") or MISSING)}</div>'
        )
    anomalies = payload.get("anomalies") or []
    found = (
        "".join(
            '<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line2)">'
            '<span class="ico mid">▲</span>'
            f'<div><div>{_text(row.get("title"))}</div><div class="small ink2">{_text(row.get("detail"))}</div>'
            "</div></div>"
            for row in anomalies
        )
        or '<div class="empty">当前没有列出的数据异常</div>'
    )
    formulas = "".join(f"<p>{_text(_formula(line))}</p>" for line in payload.get("formulas") or [])
    return (
        _crumb(f"复盘与数据 / {_text(payload.get('date'))}")
        + f'<h1>{_text(title)}</h1><p class="sub">{_text(sub)}</p>'
        + '<div class="card sec"><div style="display:flex;justify-content:space-between"><h2>数据状态</h2>'
        + f'<span class="small muted">点击查看影响</span></div><div class="status">{"".join(cards)}</div></div>'
        + '<div class="grid g2 sec"><div class="card"><h2>系统之前说的对不对</h2>'
        + f'{review}</div><div class="card"><div class="hd"><h2>发现的数据异常</h2> '
        + f'<span class="num muted">{len(anomalies)}</span></div>{found}</div></div>'
        + '<details class="method"><summary>计算口径说明</summary><div>'
        + "<p>止盈接近单独列为止盈提示，不计入下行风险数。</p><p>组合回撤与距历史高点同一口径。</p>"
        + formulas
        + "</div></details>"
    )


# ---------- stock ----------


def _price_bar(payload):
    pn = payload.get("price_now") or {}
    if not pn.get("px"):
        return ""
    px = pn["px"]
    ret = pn.get("ret")
    cls = "down" if (ret or 0) < 0 else "up"
    sess = {"pre": "盘前", "regular": "盘中", "post": "盘后", "close": "收盘"}.get(pn.get("session"), "")
    at = pn.get("at") or ""
    if "T" in str(at):
        from datetime import datetime as _dt

        try:
            at = (
                _dt.fromisoformat(str(at).replace("Z", "+00:00"))
                .astimezone(ZoneInfo("America/New_York"))
                .strftime("%H:%M ET")
            )
        except ValueError:
            pass
    chg = ""
    if ret is not None and pn.get("prev_close"):
        d = px - pn["prev_close"]
        chg = f'<span class="num {cls}" style="font-size:18px">{d:+.2f}</span>'
    st = payload.get("bar_stats") or {}
    extra = []
    if st.get("day_hi"):
        extra.append(f"今日 {st['day_lo']:,.2f}–{st['day_hi']:,.2f}")
    if st.get("hi52"):
        pos = f"（52周区间 {st['pos52']:.0f}% 位）" if st.get("pos52") is not None else ""
        extra.append(f"52周 {st['lo52']:,.2f}–{st['hi52']:,.2f}{pos}")
    if st.get("vol"):
        vr = f" · 量比 {st['vol_ratio']:.1f}" if st.get("vol_ratio") else ""
        extra.append(f"量 {st['vol']:,}{vr}")
    if st.get("next_earnings"):
        extra.append(f"下次财报 {_text(str(st['next_earnings']))}")
    return (
        '<div class="card sec cat-market"><div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap">'
        f'<span class="px-big">${px:,.2f}</span>{chg}'
        f'<span class="num {cls}" style="font-size:20px">{_pct(ret, 2) if ret is not None else ""}</span>'
        f'<span class="dim">{sess} · 截至 {_text(str(at)[:16])} · {pn.get("source") or ""}来源</span></div>'
        f'<div class="dim" style="margin-top:6px">{" · ".join(extra)}</div></div>'
    )


SEGMENT_LABELS = {
    "cpu_pc": "CPU 与电脑",
    "ai_accelerators": "AI 加速卡",
    "memory": "存储与内存",
    "eda_equipment": "EDA 与设备",
    "networking": "网络",
    "software": "软件",
}


def _chart_svg(payload, width=1180, height=340):
    rows = payload.get("chart") or []
    if len(rows) < 2:
        return '<div class="dim">没有走势数据</div>'
    marks = {m["d"]: "财报" for m in (payload.get("earnings_marks") or []) if isinstance(m, dict)}
    for d in payload.get("anomaly_marks") or []:
        marks.setdefault(d, "异常")
    data_json = escape(json.dumps(rows, ensure_ascii=False), quote=True)
    mark_json = escape(json.dumps(marks, ensure_ascii=False), quote=True)
    intraday = payload.get("intraday_series") or []
    intraday_json = escape(json.dumps(intraday, ensure_ascii=False), quote=True)
    ranges = {"1月": 22, "3月": 66, "6月": 132, "1年": 252, "全部": 0}
    btns = "".join(
        f'<button class="rc{" on" if label == "6月" else ""}"'
        f' onclick="InvestorChart.range(this,{k!r})">{label}</button>'
        for label, k in ranges.items()
    )
    btns += '<button class="rc" onclick="InvestorChart.range(this,\'day\')">当日</button>'
    return (
        '<script src="/lightweight-charts.js"></script>'
        f'<div class="chart-btns">{btns}</div>'
        '<div id="dchart-legend" class="dim small"></div>'
        f"<div id=\"dchart\" class=\"lwc\" data-rows='{data_json}' data-marks='{mark_json}'"
        f" data-intraday='{intraday_json}'></div>"
        '<div class="dim small">日 K 线 + 成交量 + 50/200 日均线；标记点为财报日与异常日；'
        "当日页签为分钟走势。</div>"
    )


def _peers_module(payload):
    peers, seg = payload.get("peers") or ([], None)
    if not peers:
        return ""
    rows = "".join(
        f"<tr><td>{_tk(p['ticker'])}</td>"
        f"<td class='num'>${p['px']:,.2f}</td>"
        f"<td class='num {'down' if (p.get('ret') or 0) < 0 else 'up'}'>{_pct(p.get('ret'), 1)}</td>"
        f"<td class='num'>{_pct(p.get('ret5'), 1) if p.get('ret5') is not None else '—'}</td></tr>"
        for p in peers
    )
    seg_txt = f'<span class="dim">环节：{_text(SEGMENT_LABELS.get(seg, seg))}</span>' if seg else ""
    return (
        '<div class="card sec cat-market"><h2>同环节与同篮子 ' + seg_txt + "</h2>"
        '<table class="tbl"><tr><th>代码</th><th>现价</th><th>今日涨跌</th><th>5日涨跌</th></tr>'
        + rows
        + "</table></div>"
    )


def _stock(payload):
    symbol = payload.get("symbol") or ""
    if payload.get("no_data"):
        return (
            _crumb(f"个股 / {_text(symbol)}")
            + f"<h1>{_text(symbol)}</h1>"
            + '<div class="card sec"><p>没有这只股票的数据。试试搜索：</p>'
            + _search_box()
            + "</div>"
        )
    if payload.get("untracked"):
        return (
            _crumb(f"个股 / {_text(symbol)}")
            + f"<h1>{_text(symbol)}</h1>"
            + _price_bar(payload)
            + '<div class="card sec"><h2>走势图</h2>'
            + _chart_svg(payload)
            + "</div>"
            + '<div class="card sec"><p>不在监控范围——这里只显示价格和走势。</p></div>'
        )
    trend = payload.get("trend") or {}
    position = payload.get("position") or {}
    held = position.get("kind") == "held"
    chips = (
        f'<span class="chip held">纸面持有 · {_text(position.get("holding_kind") or MISSING)}</span>'
        if held
        else '<span class="chip buy">未持有 · 可买</span>'
        if position.get("kind") == "buyable"
        else '<span class="chip ok">未持有</span>'
    )
    if position.get("risk_level") == "red":
        chips += ' <span class="chip hi">! 重点下行</span>'
    elif position.get("risk_level") == "orange":
        chips += ' <span class="chip mid">▲ 下行关注</span>'
    returns = "".join(
        f'<div><div class="small muted">{_text(trend.get(key + "_label") or label)}</div>'
        f'<div style="font-size:16px">{_pct(trend.get(key))}</div>'
        + (f'<div class="small muted">{_text(trend[key + "_tag"])}</div>' if trend.get(key + "_tag") else "")
        + "</div>"
        for label, key in (
            ("当日", "ret"),
            ("盘后", "post"),
            ("近 5 日", "ret_5"),
            ("近 20 日", "ret_20"),
            ("近 60 日", "ret_60"),
        )
    )
    rsi = trend.get("rsi")
    rsi_html = (
        _miss()
        if rsi is None
        else f'<span class="num">{int(half_up(rsi, 0))}</span>' + (" 接近超卖" if rsi < 30 else "")
    )
    vol = trend.get("volume_multiple")
    vol_html = (
        _miss()
        if vol is None
        else f'<span class="num">{half_up(vol, 1):.1f} 倍</span>' + ("，放量" if vol >= 1.3 else "")
    )
    resid = payload.get("resid_text")
    rel = (_text(resid) if resid and resid != MISSING else "") + (
        f" · {_text(payload.get('sector'))}当日 {_text(format_fraction(payload.get('theme_ret')))}"
        if payload.get("sector")
        else ""
    )
    position_html = _stock_position(payload, position, held)
    stamps = "".join(
        f'<span class="k">{_text(item.get("label"))}</span><span>{_stamp(item, payload)}</span>'
        for item in payload.get("stamps") or []
    )
    return (
        _crumb(f'<a href="/stocks{_query(payload)}">← 返回我的标的</a>')
        + '<div style="display:flex;gap:12px;align-items:baseline;margin-top:8px;flex-wrap:wrap">'
        + f'<h1 class="mono" style="margin:0">{_text(symbol)}</h1>{chips}</div>'
        + f'<p class="sub" style="margin-top:6px">{_text(payload.get("oneliner"))}</p>'
        + _price_bar(payload)
        + _key_stats(payload)
        + '<div class="card sec cat-market"><div style="display:flex;justify-content:space-between">'
        + '<h2>走势与位置</h2><span class="small muted">日收盘 · 均线与关键价位</span></div>'
        + (_chart_svg(payload) or _chart(trend, position, payload))
        + f'<div class="grid" style="grid-template-columns:repeat(5,1fr);margin-top:10px;gap:10px">{returns}'
        + "</div></div>"
        + _stock_today(payload)
        + _stock_earnings_card(payload)
        + position_html
        + _peers_module(payload)
        + '<div class="card sec"><h2>位置与情绪'
        + (
            f' <span class="chip stale">沿用 {_text(payload["carried_from"][5:].replace("-", "/"))} 收盘</span>'
            if payload.get("carried_from")
            else ""
        )
        + '</h2><div class="kv">'
        + f'<span class="k">距 50 日线</span><span>{_pts(trend.get("dev50"))} '
        + f'<span class="small muted">（{money(trend.get("ma50"))}）</span></span>'
        + f'<span class="k">距 200 日线</span><span>{_pts(trend.get("price_vs_ma200"))} '
        + f'<span class="small muted">（{money(trend.get("ma200"))}）</span></span>'
        + f'<span class="k">距一年高点</span><span>{_pts(trend.get("drawdown252"))} '
        + f'<span class="small muted">（{money(trend.get("year_high"))}）</span></span>'
        + f'<span class="k">RSI</span><span>{rsi_html}</span>'
        + f'<span class="k">成交量</span><span>{vol_html}</span>'
        + f'<span class="k">相对板块</span><span class="small">{rel or _miss()}</span>'
        + f'<span class="k">资金流</span><span>{_miss()}</span>'
        + f'<span class="k">形态</span><span>{_tech_cell(payload.get("tech"))} '
        + '<span class="small muted">技术参考，不触发交易</span></span>'
        + f'<span class="k">下次财报</span><span>{_next_earn(payload)}</span></div>'
        + f'<h3 style="margin-top:16px">四项评分</h3>{_score_bars(payload.get("books"))}</div>'
        + '<div class="grid g2 sec"><div class="card"><h2>新闻与事件</h2>'
        + _confirmed_events(payload)
        + _stock_news(payload)
        + _earnings_hist_module(payload)
        + _stock_feed(payload)
        + '</div><div class="card"><h2>机构观点</h2>'
        + _ratings_body(payload)
        + _actions_body(payload)
        + '</div><div class="card"><h2>基本面与估值</h2>'
        + f'<p style="margin:0">{_text(_valuation(payload.get("valuation"), full=True))}</p>'
        + _consensus(payload.get("consensus"))
        + '<div class="gap">系统目前不给出估值价位，只展示市盈率、历史分位和隐含增速。</div>'
        + f'<h3 style="margin-top:16px">数据时间</h3><div class="kv small">{stamps}</div></div></div>'
    )


def _stamp(item, payload):
    value = str(item.get("value") or MISSING)
    if value in (MISSING, "暂无"):
        return _miss(value)
    day = _day(payload)
    when = _as_date(value)
    if when is not None and day is not None and (day - when).days >= 2:
        return f'<span class="chip stale">{_text(value)} · 过期</span>'
    return _text(value)


def _stock_position(payload, position, held):
    if held:
        rows = (
            f'<span class="k">股数</span><span class="num">{_text(_shares(position.get("shares")))}</span>'
            '<span class="k">成本 → 现价</span>'
            f'<span class="num">{money(position.get("avg_cost"))} → {money(position.get("price"))}</span>'
            f'<span class="k">盈亏</span><span>{_pct(position.get("pnl"), 1)}</span>'
            f'<span class="k">下一步</span><span>{_text(_next_view(position.get("next_step"))[0])}</span>'
        )
        spec = position.get("ruler") if isinstance(position.get("ruler"), dict) else {}
        account = f"/account{_query(payload)}#{_text(payload.get('symbol'))}"
        return (
            '<div class="card sec"><div style="display:flex;justify-content:space-between;align-items:center">'
            '<div class="hd"><h2>我的仓位</h2> '
            f'<span class="small muted">{_text(position.get("holding_kind") or MISSING)}</span></div>'
            f'<a href="{account}">在纸面账户中定位 →</a></div>'
            + (
                f'<div class="small ink2" style="margin-top:4px">{_text(position.get("risk_text"))}</div>'
                if position.get("risk_text")
                else ""
            )
            + '<div style="display:grid;grid-template-columns:240px 1fr;gap:20px;align-items:center;margin-top:8px">'
            f'<div class="kv">{rows}</div>{_ruler_box(spec, 620)}</div>'
            f'<div class="rules">{_rules(position.get("levels") or [])}</div></div>'
        )
    if position.get("kind") == "buyable":
        why = position.get("why_not") or MISSING
        return (
            '<div class="card sec"><h2>为什么没买</h2>'
            f'<p style="margin:0">{_text(human_reason(why) or why)}</p><div class="kv" style="margin-top:8px">'
            f'<span class="k">回调参考</span><span class="num">{money(position.get("ma50"))}（50 日线）</span>'
            f'<span class="k">上方参考</span><span class="num">{money(position.get("year_high"))}（一年高点）</span>'
            "</div>"
            "</div>"
        )
    if position.get("kind") == "blocked":
        return (
            '<div class="card sec"><h2>为什么不可买</h2>'
            f'<p style="margin:0">{_text(position.get("blocker") or MISSING)}</p></div>'
        )
    return f'<div class="card sec"><h2>我的仓位</h2>{_miss()}</div>'


def _confirmed_events(payload):
    events = payload.get("news_events") or []
    strong = [e for e in events if (e.get("importance") or 0) >= 70]
    if not strong:
        return ""
    items = "".join(
        f'<div class="hl-card" style="border-left:4px solid var(--alert)">'
        f"{_kind_chip(e.get('kind'))} "
        + (
            f'<a href="{e["url"]}" target="_blank" rel="noopener">{_text(e.get("headline") or "")}</a>'
            if e.get("url")
            else _text(e.get("headline") or "")
        )
        + f'<span class="dim"> {_text(str(e.get("published_at") or "")[:16])}</span></div>'
        for e in strong[:5]
    )
    return f'<div class="sec"><h3>已确认事件</h3>{items}</div>'


def _stock_news(payload):
    blocks = []
    for row in payload.get("events") or []:
        items = row.get("reasons") or []
        reasons = [_reason_li(item) for item in items]
        label = "可能原因 · 含旧闻" if any(item.get("stale_note") for item in items) else "可能原因"
        status = str(row.get("status") or "")
        why = (
            f'<div class="small muted">{label}</div><ul class="news">{"".join(reasons)}</ul>'
            if reasons
            else '<div class="small muted">暂无可引用的解释。</div>'
        )
        blocks.append(
            '<div class="event open" style="margin-top:0"><div class="h" data-ev>'
            f'<b>{_text(row.get("title"))}</b><span class="chip mid">{_text(status.replace("·", " · "))}</span></div>'
            f'<div class="body">{why}</div></div>'
        )
    news = (payload.get("news") or [])[:6]
    day = _day(payload)
    items = []
    for item in news:
        when = str(item.get("published_beijing") or "")
        old = _as_date(when)
        stale = old is not None and day is not None and (day - old).days >= 1
        items.append(
            f"<li>{_text(item.get('summary'))} "
            f'<span class="small muted">· {_text(item.get("source"))} · {_text(when or MISSING)}</span>'
            + (' <span class="chip stale">旧闻</span>' if stale else "")
            + "</li>"
        )
    today = sum(1 for item in payload.get("news") or [] if _as_date(item.get("published_beijing")) == day)
    listing = f'<ul class="news">{"".join(items)}</ul>' if items else '<div class="empty">截点内没有该股新闻</div>'
    return (
        "".join(blocks)
        + f'<div class="small muted" style="margin-top:12px">最近新闻（{_text(payload.get("date"))} 当日 {today} 条）'
        + "</div>"
        + listing
    )


def _chart(trend, position, payload):
    closes = [float(item) for item in trend.get("closes") or []]
    if len(closes) < 2:
        return '<div class="gap">走势数据暂缺</div>'
    width, height, left, right, top, bottom = 760, 220, 56, 748, 14, 196
    lines = []
    if trend.get("ma200") is not None:
        lines.append(("200 日线（当前）", float(trend["ma200"]), "var(--ref)", "4 3"))
    if trend.get("ma50") is not None:
        lines.append(("50 日线（当前）", float(trend["ma50"]), "#B39B6B", "2 3"))
    if position.get("kind") == "held":
        if position.get("avg_cost") is not None:
            lines.append(("成本", float(position["avg_cost"]), "#9AA19F", ""))
        spec = position.get("ruler") if isinstance(position.get("ruler"), dict) else {}
        stop = spec.get("stop") if isinstance(spec.get("stop"), dict) else None
        if stop and stop.get("p") is not None:
            lines.append((str(stop.get("n") or "止损"), float(stop["p"]), "var(--r-hi-line)", ""))
    low = min([*closes, *(line[1] for line in lines)])
    high = max([*closes, *(line[1] for line in lines)])
    pad = (high - low) * 0.06 or 1
    low, high = low - pad, high + pad

    def x_at(index):
        return left + index / (len(closes) - 1) * (right - left)

    def y_at(price):
        return top + (high - price) / (high - low) * (bottom - top)

    svg = [f'<svg width="100%" viewBox="0 0 {width} {height}" role="img">']
    for step in range(5):
        price = low + (high - low) * step / 4
        svg.append(
            f'<line x1="{left}" x2="{right}" y1="{y_at(price):.1f}" y2="{y_at(price):.1f}" stroke="#F0ECE4"/>'
            f'<text x="{left - 6}" y="{y_at(price) + 4:.1f}" font-size="10" fill="#8A918F" '
            f'text-anchor="end">{price:.0f}</text>'
        )
    placed = {"R": [], "L": []}
    for name, price, color, dash in sorted(lines, key=lambda item: -item[1]):
        y = y_at(price)
        ty = y - 4
        side = "R" if all(abs(item - ty) >= 12 for item in placed["R"]) else "L"
        while any(abs(item - ty) < 12 for item in placed[side]):
            ty += 12
        ty = min(ty, height - 16)
        placed[side].append(ty)
        anchor, tx = ("end", right) if side == "R" else ("start", left + 4)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(
            f'<line x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.2"{dash_attr}/>'
            f'<text x="{tx}" y="{ty:.1f}" font-size="10" fill="{color}" text-anchor="{anchor}" paint-order="stroke" '
            f'stroke="#fff" stroke-width="3">{_text(name)} {money(price)}</text>'
        )
    points = " ".join(f"{x_at(index):.1f},{y_at(value):.1f}" for index, value in enumerate(closes))
    svg.append(f'<polyline fill="none" stroke="#1F2A2A" stroke-width="1.8" points="{points}"/>')
    svg.append(f'<circle cx="{x_at(len(closes) - 1):.1f}" cy="{y_at(closes[-1]):.1f}" r="4" fill="#1F2A2A"/>')
    day = _as_date((payload.get("trend") or {}).get("close_date")) or _day(payload)
    end = "" if day is None else f"{day.month:02d}-{day.day:02d} "
    svg.append(
        f'<text x="{left}" y="{height - 6}" font-size="10" fill="#8A918F">约 {len(closes)} 个交易日前</text>'
        f'<text x="{right}" y="{height - 6}" font-size="10" fill="#8A918F" text-anchor="end">{end}收盘 '
        f"{money(closes[-1])}</text>"
    )
    svg.append("</svg>")
    return "".join(svg)


def _score_bars(books):
    if not isinstance(books, dict):
        return _miss()
    parts = []
    for label, key in (("质量", "quality"), ("成长", "growth"), ("估值", "valuation"), ("择时", "timing")):
        value = books.get(key)
        width = 0 if value is None else max(0, min(100, float(value)))
        parts.append(
            f'<div><div class="small muted">{label}</div><div class="num" style="font-size:16px">{_score(value)}</div>'
            f'<div class="bar"><i style="width:{width:.1f}%"></i></div></div>'
        )
    return f'<div class="grid g4" style="gap:6px">{"".join(parts)}</div>'


def _consensus(consensus):
    if not isinstance(consensus, dict):
        return '<p class="small muted">暂无一致预期（轮询中）</p>'
    lines = []
    for key, label in (("fy1", "本财年"), ("fy2", "下财年")):
        row = consensus.get(key) or {}
        lines.append(
            f'<span class="k">{label}</span>'
            f"<span>每股收益 {_eps(row.get('eps'))} · {_count(row.get('count'))} 家机构 · "
            f"前瞻市盈率 {_eps_pe(row.get('forward_pe'))}</span>"
        )
    return (
        f'<div class="kv small" style="margin:8px 0">{"".join(lines)}'
        f'<span class="k">快照</span><span>{_text(consensus.get("as_of") or MISSING)}</span></div>'
    )


def _header(payload):
    day = _day(payload)
    shown = MISSING if day is None else f"{day.year}.{day.month:02d}.{day.day:02d}"
    dow = "" if day is None else f"周{_WEEK[day.weekday()]}"
    prev_link = _date_link(payload, _near(day, -1), "‹")
    next_link = _date_link(payload, _near(day, 1), "›")
    fresh = payload.get("freshness") or (
        MISSING if day is None else f"收盘快照 · 数据截至 {day.month}-{day.day} 16:00 ET"
    )
    return (
        '<header class="top"><div class="top-in"><div class="brand"><b>INVES·COG</b><div>投资研究工作台</div></div>'
        + _nav(payload)
        + '<div class="datebox"><div class="row">'
        + prev_link
        + f'<span class="d">{_text(shown)}</span><span class="small">{dow}</span>'
        + next_link
        + _date_picker(payload)
        + '<a class="step" href="'
        + _text(payload.get("page") or "/")
        + '">今天</a>'
        + '</div><div class="fresh"><span>'
        + _text(fresh)
        + '</span><span class="mode"><button id="lang-toggle" onclick="__setLang()">中文 / 英文</button>'
        + "</span></div></div></div></header>"
    )


def _tk(code, cls=""):
    """B-073: the single ticker renderer — every ticker text becomes /s/ link."""
    if not code:
        return ""
    c = _text(str(code))
    return f'<a class="tk {cls}" href="/s/{c}">{c}</a>'


def _severity(row):
    """B-073 §1 badge levels, derived only from existing row data:
    major: |z|>=5 or core-company earnings gap >=20% (facts already parsed)
    watch: any other active anomaly / near-term core earnings
    info:  rest."""
    z = row.get("peak_z") or row.get("last_z")
    if z is not None and abs(z) >= 5:
        return ("sev-major", "重大")
    if row.get("gap") is not None and abs(row["gap"]) >= 20:
        return ("sev-major", "重大")
    if z is not None or row.get("status") == "active":
        return ("sev-watch", "关注")
    return ("sev-info", "一般")


def _kind_chip(kind):
    label = {
        "earnings_result": "财报",
        "guidance": "指引",
        "capex": "资本开支",
        "mna": "并购",
        "supply_shock": "供应",
        "regulatory": "监管",
        "rating": "评级",
    }.get(kind, "其他")
    return f'<span class="chip kind-chip kind-{_text(kind or "other")}">{label}</span>'


def _search_box():
    return (
        '<div class="searchbox"><input id="q" type="search" placeholder="代码 / 公司名">'
        '<div class="searchres" id="qres"></div></div>'
    )


def _nav(payload):
    page = "/" if not isinstance(payload, dict) else payload.get("page") or "/"
    links = []
    for href, label, small in NAV:
        mark = ' class="on"' if _active(href, page) else ""
        badge = _badges(payload) if href == "/account" else ""
        links.append(f'<a href="{href}{_query(payload)}"{mark}>{_text(label)}{badge}<small>{_text(small)}</small></a>')
    return '<nav class="nav">' + "".join(links) + _search_box() + "</nav>"


def _badges(payload):
    if "down_red" not in payload and "down_orange" not in payload:
        return ""
    red = int(payload.get("down_red") or 0)
    orange = int(payload.get("down_orange") or 0)
    return f'<span class="badges"><span class="dot hi">{red}</span> <span class="dot mid">{orange}</span></span>'


def _foot(payload):
    links = " · ".join(f'<a href="{href}">{_text(label)}</a>' for href, label in DETAILS)
    day = payload.get("date") if isinstance(payload, dict) else None
    shot = "" if not day else f" · {_text(day)} 快照"
    return (
        f'<div class="foot"><span>{_text(payload.get("label") or PAPER_LABEL)}{shot}</span>'
        f'<span class="links">详情 {links}</span></div>'
    )


def _formula(line):
    text = str(line)
    if "目标价" in text or "合理价" in text:
        return "页面只引用已有估值输入。"
    return text


REFRESH_META = ""


def _search_page(payload):
    rows = payload.get("results") or []
    if rows:
        body = "".join(
            f'<div class="row">{_tk(r["ticker"])} <span class="dim">{_text(r.get("name") or "")}</span></div>'
            for r in rows
        )
        title = f"搜索 “{_text(payload.get('q') or '')}”"
    else:
        body = f"<p>没有找到 “{_text(payload.get('q') or '')}” 相关的标的。</p>" + _search_box()
        title = "搜索"
    return f'<div class="card sec"><h2>{title}</h2>{body}</div>'


def _document(title, body, refresh=False):
    global REFRESH_META
    REFRESH_META = '<meta name="refresh-today" content="1">' if refresh else ""
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_text(title)}</title>{REFRESH_META}<style>{_STYLE}{_EXTRA}</style></head>"
        f'<body>{body}<script src="/investor.js"></script></body></html>'
    )


def _ruler_box(spec, width=470):
    if not spec or spec.get("px") is None:
        return f'<div class="c-ruler">{_text(MISSING)}</div>'
    drawn = ruler(spec, width)
    blob = escape(json.dumps(spec, ensure_ascii=False, default=_json_default), quote=True)
    return f'<div class="c-ruler" data-ruler="{blob}">{drawn["svg"]}</div>'


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _active(href, page):
    if href == "/stocks" and isinstance(page, str) and page.startswith("/s/"):
        return True
    return href == page


def _day(payload):
    value = payload.get("date") if isinstance(payload, dict) else None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _near(day, step):
    if day is None:
        return None
    if step > 0:
        return next_trading_day(day)
    cursor = day - timedelta(days=1)
    for _ in range(12):
        if trading_day(cursor):
            return cursor
        cursor -= timedelta(days=1)
    return None


def _date_picker(payload):
    day = _day(payload)
    value = "" if day is None else day.isoformat()
    page = payload.get("page") or "/"
    nav = f"location.href='{_text(page)}?date='+this.value"
    return (
        f'<input type="date" value="{_text(value)}" max="{_text(payload.get("today") or value)}" '
        f'onchange="{nav}" '
        'style="font:12px var(--mono);border:1px solid var(--line);border-radius:6px;padding:1px 4px">'
    )


def _date_link(payload, day, label):
    if day is None:
        return f'<span class="step off">{label}</span>'
    page = payload.get("page") or "/"
    title = "前一交易日" if label == "‹" else "后一交易日"
    return f'<a class="step" title="{title}" href="{page}?date={day.isoformat()}">{label}</a>'


def _query(payload):
    chosen = payload.get("date") if isinstance(payload, dict) else None
    if isinstance(chosen, date):
        chosen = chosen.isoformat()
    if not chosen:
        return ""
    return f"?date={_text(chosen)}"


def _symbol_href(payload, ticker):
    return f"/s/{_text(ticker)}{_query(payload)}"


def _kind_label(kind):
    if kind in _KIND:
        return _KIND[kind]
    text = "" if kind is None else str(kind)
    if text and not any("a" <= char <= "z" or char == "_" for char in text):
        return text
    return "减仓"


def _tone(value):
    if value is None or value == 0:
        return "muted"
    return "up" if value > 0 else "down"


def _text(value):
    return escape("" if value is None else str(value), quote=True)


def _count(value):
    if value is None:
        return _text(MISSING)
    return _text(value)


def _shares(value):
    if value is None:
        return MISSING
    return str(int(half_up(float(value), 0)))


def _score(value):
    if value is None:
        return MISSING
    shown = half_up(value, 1)
    text = f"{shown:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _whole(value):
    if value is None:
        return MISSING
    return str(int(half_up(value, 0)))


def _rsi(value):
    if value is None:
        return MISSING
    return str(int(half_up(value, 0)))


def _vol(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 1):.1f} 倍"


def _eps(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 2):.2f}"


def _eps_pe(value):
    if value is None:
        return MISSING
    return f"{half_up(value, 1):.1f}"


def _plain(value):
    if value is None:
        return MISSING
    if isinstance(value, float):
        return f"{half_up(value, 2):.2f}"
    return str(value)


def _num_attr(value):
    if value is None:
        return ""
    return escape(str(value), quote=True)


# ---------- B-063 today-page news modules ----------


def _ticker_strip(payload):
    strip = payload.get("mstrip")
    if not strip:
        return ""
    cells = []
    for it in strip.get("items") or []:
        cls = "up" if it["dir"] > 0 else ("down" if it["dir"] < 0 else "flat")
        chg = f'<small class="{cls}">{_text(it["chg"])}</small>' if it.get("chg") else ""
        tag = f'<small class="muted">{_text(it["tag"])}</small>' if it.get("tag") else ""
        cells.append(
            f'<span class="tcell" title="{_text(it.get("title") or "")}">'
            f"<b>{_text(it['label'])}</b> {_text(it['value'])}{chg}{tag}</span>"
        )
    tail = strip.get("tail")
    note = f'<span class="small muted">{_text(tail)}</span>' if tail else ""
    return (
        '<div class="card mstrip" id="mstrip"><div class="ticker-row">'
        + "".join(cells)
        + "</div>"
        + f'<div class="small muted" style="margin-top:4px">{note} · 盘前/盘中行情只用于看盘，不进入规则 A</div>'
        + '<div class="small muted">IEX 为单一交易所实时成交，约占全市场成交 2–3%，仅供看盘，不进入规则 A</div></div>'
    )


def _sector_strip(payload):
    cards = payload.get("sector_strip")
    if not cards:
        return ""
    cells = []
    for c in cards:
        avg = c.get("average")
        cls = "up" if avg is not None and avg > 0 else ("down" if avg is not None and avg < 0 else "flat")
        lead = c.get("leader")
        lag = c.get("laggard")
        detail = []
        if lead:
            detail.append(f"领涨 {lead[0]} {_text(_signed(lead[1] * 100, 1))}")
        if lag:
            detail.append(f"领跌 {lag[0]} {_text(_signed(lag[1] * 100, 1))}")
        held = f"持仓 {c['held']}" if c.get("held") else ""
        detail.append(held)
        cells.append(
            f'<a class="scell" href="/stocks#{_text(c["slug"])}"><span class="sname">{_text(c["sector"])}</span>'
            f'<span class="num {cls}">{_pct(avg)}</span>'
            f'<span class="small muted">{_text(" · ".join(d for d in detail if d))}</span></a>'
        )
    return f'<div class="card sstrip" id="sstrip"><div class="sector-grid">{"".join(cells)}</div></div>'


def _carry_banner(payload):
    day = payload.get("carry_from")
    if not day:
        return ""
    et = payload.get("et_now") or ""
    trading = payload.get("trading_day")
    if not trading:
        head, note = "休市", "显示最近交易日数据"
    elif et < "09:30":
        head, note = "美股未开盘", "行情为最新可得值，收盘后自动换成今日收盘"
    elif et < "16:00":
        head, note = "盘中", "行情延迟约 15 分钟，收盘后换成今日收盘"
    else:
        head, note = "已收盘", "收盘数据整理中，暂用最新行情"
    carry = f"以下收盘数据沿用 {str(day)[5:].replace('-', '/')}，新闻与日历为今日。"
    return f'<div class="banner info"><b>{head}</b><span>{note}；{carry}</span></div>'


def _carry_tag(payload):
    day = payload.get("carry_from")
    if not day:
        return ""
    return f' <span class="chip stale">沿用 {str(day)[5:].replace("-", "/")} 收盘</span>'


_SESSION_LABEL = {"pre": "盘前", "regular": "盘中", "post": "盘后", "overnight": "隔夜"}


def _intra_line(row):
    if not row:
        return ""
    last, prev = row.get("last"), row.get("prev_close")
    if last is None or prev in (None, 0):
        return ""
    pct = float(last) / float(prev) - 1
    moment = _parse_iso(row.get("as_of"))
    src = row.get("source") or ""
    src_label = {
        "Alpaca:iex": "Alpaca IEX",
        "Alpaca:delayed_sip": "Alpaca 延迟 SIP",
        "Yahoo": "Yahoo",
        "FRED": "FRED",
    }.get(src, src or "snapshot")
    if src == "Alpaca:iex" and moment:
        label = f"IEX 实时 {moment.astimezone(NY):%H:%M:%S}"
    elif src == "Alpaca:delayed_sip" and moment:
        label = f"延迟 15 分 {moment.astimezone(NY):%H:%M}"
    else:
        session = _SESSION_LABEL.get(row.get("session"), _text(row.get("session")))
        hm = moment.astimezone(NY).strftime("%H:%M") if moment else "—"
        delay = row.get("delay_minutes")
        label = f"{session} · 截至 {hm} 美东" + (f" · 延迟约 {delay} 分钟" if delay is not None else "")
    alt = row.get("alt")
    alt_text = ""
    if alt is not None:
        a_src = {
            "Alpaca:iex": "Alpaca IEX",
            "Alpaca:delayed_sip": "Alpaca 延迟 SIP",
            "Yahoo": "Yahoo",
            "FRED": "FRED",
        }.get(alt.get("source") or "", alt.get("source") or "snapshot")
        a_asof = _parse_iso(alt.get("as_of"))
        alt_text = f" · {a_src} {float(alt['last']):.2f} 于 {a_asof.astimezone(NY):%H:%M}" if a_asof else ""
    return f'<div class="small muted" title="{_text(src_label + alt_text)}">{label} {_signed(pct * 100, 2)}</div>'


def _safe_url(url):
    text = str(url or "")
    return text if text.startswith(("http://", "https://")) else "#"


def _hm(iso):
    try:
        moment = _parse_iso(iso)
        return moment.astimezone(SH).strftime("%H:%M") + " 北京" if moment else "—"
    except Exception:
        return "—"


def _parse_iso(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _md_local(value):
    text = str(value or "")[:10]
    return text[5:].replace("-", "/") if len(text) >= 10 else text


def _nrule(item):
    rule = item.get("rule")
    if rule is None:
        return {}
    if isinstance(rule, dict):
        return rule
    return {
        "primary_tickers": rule.primary_tickers if hasattr(rule, "primary_tickers") else [],
        "tags": rule.tags,
        "macro": rule.macro,
        "importance": rule.importance,
        "held": rule.held,
    }


def _ntags(item):
    tags = _nrule(item).get("tags") or []
    out = ""
    for tag in tags:
        cls = " hot" if tag in ("财报", "指引", "评级", "并购", "财报前瞻") else " macro" if tag == "宏观" else ""
        out += f'<span class="tag{cls}">{_text(tag)}</span>'
    return out


def _ncodes(item, held):
    return "".join(
        f'<span class="tick{" held" if t in held else ""}">{_text(t)}</span>'
        for t in (_nrule(item).get("primary_tickers") or [])
    )


def _nlate(item):
    return '<span class="chip stale">事后补采</span>' if item.get("late") else ""


def _ntitle(item, url):
    """Headline link: Chinese title when translated, English on hover/toggle."""
    en = str(item.get("headline") or item.get("summary") or "")
    zh = item.get("title_zh")
    attrs = f'href="{url}" target="_blank" rel="noopener" title="{_text(en)}"'
    if zh:
        return f'<a {attrs}><span class="nzh">{_text(zh)}</span><span class="nen" hidden>{_text(en)}</span></a>'
    return f"<a {attrs}>{_text(en)}</a>"


def _news_row(item, held):
    if item.get("grouped"):
        return _group_row(item, held)
    url = _text(_safe_url(item.get("url")))
    return (
        f'<div class="nrow"><span class="tm">{_hm(item.get("published_at") or item.get("published"))}</span>'
        f'<div class="hl">{_ntags(item)}{_ntitle(item, url)} {_nlate(item)}</div>'
        f'<span class="codes">{_ncodes(item, held)}</span></div>'
    )


def _group_row(item, held):
    """One collapsed row for a ticker's weak-rating headlines (B-064)."""
    members = item.get("group_items") or [item]
    sources = []
    for m in members:
        src = m.get("source")
        if src and src not in sources:
            sources.append(src)
    ticker = item.get("group_ticker") or ""
    count = item.get("group_count") or len(members)
    names = "、".join(_text(x) for x in sources[:4])
    detail = "".join(_news_row(m, held) for m in members)
    return (
        f'<details class="nrow ngroup"><summary>'
        f'<span class="tm">{_hm(item.get("published_at") or item.get("published"))}</span>'
        f'<span class="hl"><span class="tag">评级</span>{_text(ticker)} 今日 {count} 家机构调整目标价（{names}）</span>'
        f'<span class="codes">{_ncodes(item, held)}</span></summary>{detail}</details>'
    )


def _tech_chip(tech):
    if not isinstance(tech, dict):
        return ""
    shape = tech.get("shape")
    if not shape or shape == "数据不足":
        return ""
    cls = (
        " ok"
        if shape in ("震荡", "空头反弹")
        else " mid"
        if shape == "多头回调"
        else " buy"
        if shape == "多头排列"
        else " hi"
    )
    sig = " · " + "、".join(tech.get("signals") or []) if tech.get("signals") else ""
    return f'<span class="chip{cls}" title="技术参考，不触发交易">{_text(shape)}{_text(sig)}</span>'


def _prev_session_tag(r):
    """'（上一交易日盘后）' when the event landed 16:00-20:00 ET of the
    previous trading day; '（上一交易日）' otherwise. '' when the event is
    on the same trade date."""
    ev_at = r.get("cause_first_seen")
    day = r.get("trade_date")
    if isinstance(ev_at, str):  # payload may be JSON-serialized
        from datetime import datetime, timezone

        try:
            ev_at = datetime.fromisoformat(ev_at.replace("Z", "+00:00"))
            if ev_at.tzinfo is None:
                ev_at = ev_at.replace(tzinfo=timezone.utc)
        except ValueError:
            ev_at = None
    if isinstance(day, str):
        try:
            from datetime import date as _d

            day = _d.fromisoformat(day)
        except ValueError:
            day = None
    if not hasattr(ev_at, "astimezone") or day is None:
        return ""
    local = ev_at.astimezone(ZoneInfo("America/New_York"))
    if getattr(day, "date", None) and callable(day.date):
        day = day.date()
    if local.date() == day:
        return ""
    prev = local
    return (
        "（上一交易日盘后）"
        if (prev.hour, prev.minute) >= (16, 0) and (prev.hour, prev.minute) < (20, 0)
        else "（上一交易日）"
    )


def _live_module(payload):
    rows = (payload.get("news_modules") or {}).get("live") or []
    if not rows:
        return ""
    body = []
    for r in rows:
        scope = {"stock": "个股", "basket": "板块", "market": "市场"}.get(r["scope"], r["scope"])
        name = r.get("basket_name") or r["subject"]
        link = _tk(r["subject"]) if r["scope"] == "stock" else _text(name)
        cur = r.get("last_ret")
        peak = r.get("peak_ret")
        cur_html = (
            f'<span class="num {"down" if cur < 0 else "up"}">{cur * 100:+.1f}%</span>' if cur is not None else ""
        )
        px_html = f"${r['last_px']:,.2f}" if r.get("last_px") is not None else "—"
        fs = r.get("first_seen_at")
        when = (
            f"{_bj_hhmm(fs)} / {fs.astimezone(ZoneInfo('America/New_York')).strftime('%H:%M')}"
            if hasattr(fs, "astimezone")
            else ""
        )
        sev_cls, sev_label = _severity(r)
        faded = ' <span class="chip stale">已消退</span>' if r.get("status") == "faded" else ""
        cause_html = "原因未明"
        if r.get("cause_event_id"):
            lag = r.get("cause_lag_minutes")
            if lag is not None and lag < 0:
                lag_txt = f"股价先动，新闻晚 {abs(lag):.0f} 分钟入库"
            elif lag is not None and lag >= 120:
                lag_txt = f"事件后约 {round(lag / 60)} 小时{_prev_session_tag(r)}"
            elif lag is not None:
                lag_txt = f"事件后 {lag:.0f} 分钟"
            else:
                lag_txt = ""
            cause_html = (
                f"{_kind_chip(r.get('cause_kind'))}"
                f'<span class="trunc" title="{_text(r.get("cause_headline") or "")}">'
                f"{_text(r.get('cause_headline') or r['cause_event_id'])}</span>"
                f'<span class="dim"> {lag_txt}</span>'
            )
        members = ""
        if r["scope"] == "basket" and r.get("members"):
            parts = " ".join(
                f"{_tk(t)} <span class='num'>{v * 100:+.1f}%</span>" for t, v in (r["members"] or {}).items()
            )
            members = f'<details><summary class="dim">成员</summary><div class="dim">{parts}</div></details>'
        badge = f'<span class="badge {sev_cls}">{sev_label}</span>'
        body.append(
            f"<tr><td style='white-space:nowrap'>{scope}</td><td>{link} {badge}{faded}</td>"
            f"<td class='num'>{px_html}</td>"
            f"<td class='num'>{cur_html}</td><td class='num'>{_pct(peak, 1) if peak is not None else ''}</td>"
            f"<td style='white-space:nowrap'>{when}</td><td>{cause_html}{members}</td></tr>"
        )
    return (
        '<div class="card sec cat-anomaly" id="live"><h2>实时异常'
        '<span class="stamp">' + _text(str(payload.get("et_now") or "")) + " ET</span></h2>"
        '<table class="tbl"><tr><th>层级</th><th>对象</th><th>涨跌</th><th>峰值</th><th>首次出现</th><th>起因</th></tr>'
        + "".join(body)
        + "</table></div>"
    )


def _highlights_module(payload):
    """今日要点: top-5 cards sorted major>watch then |z|; sources are the
    active anomalies + near-term core earnings already in the payload."""
    live = (payload.get("news_modules") or {}).get("live") or []
    cards_in = (payload.get("news_modules") or {}).get("earnings_cards") or []
    picks = [r for r in live if r.get("status") == "active" and (r.get("peak_z") or 0) != 0]
    picks.sort(key=lambda r: (0 if abs(r.get("peak_z") or 0) >= 5 else 1, -abs(r.get("peak_z") or 0)))
    items = []
    for r in picks[:5]:
        sev_cls, sev_label = _severity(r)
        subj = r.get("basket_name") or r["subject"]
        link = _tk(r["subject"]) if r["scope"] == "stock" else _text(subj)
        peak = r.get("peak_ret")
        px_txt = f"${r['last_px']:,.2f} " if r.get("last_px") is not None else ""
        if r["scope"] == "basket" and r.get("members"):
            worst = min((r["members"] or {}).items(), key=lambda kv: kv[1])
            cause = _text(f"{len(r['members'])} 家 · 最弱 {worst[0]} {worst[1] * 100:+.1f}%")
        else:
            cause = _text((r.get("cause_headline") or "原因未明")[:60])
        items.append(
            f'<div class="hl-card"><span class="badge {sev_cls}">{sev_label}</span> '
            f'<span class="who">{link}</span>'
            f'<div class="num {"down" if (peak or 0) < 0 else "up"}">{px_txt}{_pct(peak, 1)}</div>'
            f'<div class="cause trunc" title="{cause}">{cause}</div></div>'
        )
    for c in cards_in:
        if len(items) >= 5:
            break
        if c.get("stage") == "upcoming" and c.get("report_date"):
            when = "盘后" if c.get("report_time") == "post" else "盘前" if c.get("report_time") == "pre" else ""
            items.append(
                f'<div class="hl-card"><span class="badge sev-watch">关注</span> '
                f'<span class="who">{_tk(c["ticker"])}</span>'
                f'<div class="cause">财报 {c["report_date"]} {when}</div></div>'
            )
    if not items:
        items.append('<div class="dim">今天没有需要重点关注的异常</div>')
    return '<div class="card sec cat-anomaly"><h2>今日要点</h2><div class="hl-cards">' + "".join(items) + "</div></div>"


def _facts_chips(facts):
    parts = []
    if facts.get("guide_gap_pct") is not None:
        parts.append(f"指引{'低于' if facts['guide_gap_pct'] < 0 else '高于'}预期 {abs(facts['guide_gap_pct']):.0f}%")
    if facts.get("surprise_pct") is not None:
        parts.append(f"业绩{'低于' if facts['surprise_pct'] < 0 else '超出'}预期 {abs(facts['surprise_pct']):.0f}%")
    return " ".join(f'<span class="chip">{_text(p)}</span>' for p in parts)


def _card_lines(row):
    card = row.get("card") or {}
    missing = row.get("missing") or []
    time_label = {"post": "盘后", "pre": "盘前"}.get(row.get("report_time"), "时间待定")
    head = f"<b>{_text(row['ticker'])}</b> {row['report_date']} {time_label}"
    if card.get("report_time") and card.get("report_time") != "unknown":
        head += f"（北京时间 {_bj_time_for_report(row['report_date'], row['report_time'])}）"
    lines = [head]
    for m in missing:
        lines.append(f'<span class="dim">缺：{_text(m)}</span>')
    if row.get("stage") == "upcoming":
        cons = card.get("consensus")
        if cons:
            bits = [
                f"EPS {cons['eps']:.2f}" if cons.get("eps") is not None else "",
                f"营收 {cons['rev'] / 1e9:.1f}B" if cons.get("rev") else "",
            ]
            lines.append(f"一致预期 {' · '.join(b for b in bits if b)}（{cons['as_of'][:10]}）")
        imp = card.get("implied_move")
        if imp:
            lines.append(f"期权预期涨跌 {imp['straddle_pct'] * 100:.1f}%（{imp['note']}）")
        hist = card.get("history") or {}
        if hist.get("note"):
            lines.append("历史财报后涨跌：历史不足")
        elif hist.get("median_abs") is not None:
            lines.append(f"历史财报后涨跌中位 {hist['median_abs'] * 100:.1f}%（{len(hist['votes'])} 次）")
        if card.get("segment") and card.get("peers"):
            lines.append(f'<span class="dim">同环节：{_text("、".join(card["peers"]))}</span>')
    else:
        for e in (card.get("events") or [])[:3]:
            react = ""
            r = e.get("reaction") or {}
            if r.get("m15") and r["m15"].get("ret") is not None:
                react = f" 15分钟 {_pct(r['m15']['ret'], 1)}"
            if r.get("m60") and r["m60"].get("ret") is not None:
                react += f" · 60分钟 {_pct(r['m60']['ret'], 1)}"
            lines.append(
                f'{_facts_chips(e.get("facts") or {})} {_text(e["headline"] or "")}<span class="dim">{react}</span>'
            )
        for a in (card.get("live_anomalies") or [])[:3]:
            label = f"异动 {a['scope']}:{_text(a['subject'])} {_pct(a.get('peak_ret'))}（{a['status']}）"
            lines.append(f'<span class="dim">{label}</span>')
        if row.get("stage") == "voted" and card.get("vote_ret") is not None:
            lines.append(f"次日投票 {_pct(card['vote_ret'], 1)} · {_text(card.get('vs_implied') or '')}")
            seg = card.get("segment_reaction")
            if seg:
                lines.append(
                    f'<span class="dim">同环节跟随 {seg["followed"]} 家 · 未跟 {seg["not_followed"]} 家</span>'
                )
    return lines


def _bj_time_for_report(report_date, report_time):
    # post ~16:00 ET -> 次日 04:00/05:00 北京；pre ~09:30 ET -> 当日 21:30/22:30
    return "次日 04:00–05:00" if report_time == "post" else "当日 21:30–22:30"


def _earnings_cards_module(payload):
    rows = (payload.get("news_modules") or {}).get("earnings_cards") or []
    if not rows:
        return ""
    up = [r for r in rows if r.get("stage") == "upcoming"]
    done = [r for r in rows if r.get("stage") != "upcoming"]
    parts = []
    if up:
        body = []
        for r in up:
            card = r.get("card") or {}
            cons = card.get("consensus") or {}
            imp = card.get("implied_move") or {}
            cons_txt = f"EPS {cons['eps']:.2f}" if cons.get("eps") is not None else "—"
            imp_txt = f"{imp['straddle_pct'] * 100:.1f}%" if imp.get("straddle_pct") is not None else "—"
            tl = {"post": "盘后", "pre": "盘前"}.get(r.get("report_time"), "待定")
            body.append(
                f"<tr><td>{r['report_date']}</td>"
                f"<td>{_bj_time_for_report(r['report_date'], r.get('report_time') or '')}</td>"
                f"<td>{_tk(r['ticker'])}</td><td>{tl}</td>"
                f"<td class='num'>{imp_txt}</td><td class='num'>{cons_txt}</td></tr>"
            )
        parts.append(
            "<h3>即将发布</h3><table class='tbl'>"
            "<tr><th>日期</th><th>北京时间</th><th>代码</th><th>时段</th><th>期权预期</th><th>一致预期</th></tr>"
            + "".join(body)
            + "</table>"
        )
    for r in done:
        card = r.get("card") or {}
        vote = card.get("vote_ret")
        vote_txt = f"次日投票 {_pct(vote, 1)}" if vote is not None else ""
        chips = ""
        for e in (card.get("events") or [])[:2]:
            chips += _facts_chips(e.get("facts") or {})
        seg = card.get("segment_reaction") or {}
        follow = f"同环节跟随 {seg['followed']}/{seg['not_followed']}" if seg else ""
        summ = " · ".join(x for x in [_tk(r["ticker"]), vote_txt, follow, _text(card.get("vs_implied") or "")] if x)
        lines = _card_lines(r)
        detail = "".join(f'<div class="row">{line if "<" in line else _text(line)}</div>' for line in lines)
        parts.append(f"<details><summary>{summ} {chips}</summary>{detail}</details>")
    return '<div class="card sec cat-earnings" id="earnings"><h2>财报</h2>' + "".join(parts) + "</div>"


def _human(v):
    v = float(v)
    return f"{v / 1e9:.1f}B" if v >= 1e9 else f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v:,.0f}"


def _key_stats(payload):
    """§8 key-stats grid under the price bar."""
    an = payload.get("analyst") or {}
    st = payload.get("bar_stats") or {}
    fy1 = (payload.get("consensus") or {}).get("fy1") or {} if isinstance(payload.get("consensus"), dict) else {}
    pt_mean = an.get("pt_mean") or an.get("pt_mean_col")
    opinions = an.get("opinions") or an.get("coverage")
    pt_range = f"{an['pt_low']:,.0f}–{an['pt_high']:,.0f} · " if an.get("pt_low") and an.get("pt_high") else ""
    eps_cq = an.get("eps_cq")
    nr = payload.get("next_report")
    fpe = an.get("forward_pe") or fy1.get("forward_pe")
    cells = [
        ("市值", _human(an.get("market_cap")) if an.get("market_cap") else "暂缺"),
        ("前瞻市盈率", f"{float(fpe):.1f}" if fpe else "暂缺"),
        ("52周区间", f"{st['lo52']:,.2f}–{st['hi52']:,.2f}" if st.get("hi52") else "暂缺"),
        (
            "平均量（20日）",
            _human(st.get("vol") / st["vol_ratio"]) if st.get("vol") and st.get("vol_ratio") else "暂缺",
        ),
        (
            "下次财报",
            f"{nr['report_date']} {({'post': '盘后', 'pre': '盘前'}).get(nr.get('time'), '')}" if nr else "暂缺",
        ),
        ("本季一致预期 EPS", f"{float(eps_cq):.2f}" if eps_cq is not None else "暂缺"),
        (
            "机构目标价",
            f"均值 ${float(pt_mean):,.2f}（{pt_range}{int(opinions) if opinions else '—'} 家）" if pt_mean else "暂缺",
        ),
    ]
    return (
        '<div class="card sec"><div class="kv" style="grid-template-columns:repeat(4,1fr)">'
        + "".join(f'<span class="k">{k}</span><span>{v}</span>' for k, v in cells)
        + "</div></div>"
    )


def _ratings_module(payload):
    return f'<div class="card sec"><h2>评级分布</h2>{_ratings_body(payload)}</div>'


def _ratings_body(payload):
    trend = (payload.get("analyst") or {}).get("trend") or {}
    cur = next((p for p in (trend.get("trend") or []) if p.get("period") == "0m"), {})
    prev = next((p for p in (trend.get("trend") or []) if p.get("period") == "-1m"), {})
    if not cur:
        return '<div class="card sec"><h2>评级分布</h2><p class="dim">暂缺</p></div>'
    names = [("strongBuy", "强买"), ("buy", "买"), ("hold", "持有"), ("sell", "卖"), ("strongSell", "强卖")]
    mx = max((cur.get(k) or 0) for k, _ in names) or 1
    rows = "".join(
        f'<div class="row"><span style="width:42px">{lab}</span>'
        f'<span style="display:inline-block;height:10px;width:{(cur.get(k) or 0) / mx * 200:.0f}px;'
        'background:var(--brand)"></span>'
        f' <b>{cur.get(k) or 0}</b> <span class="dim">上月 {prev.get(k) or 0}</span></div>'
        for k, lab in names
    )
    return rows + '<p class="dim small">数据源只提供机构名，不含分析师个人姓名。</p>'


def _actions_module(payload):
    return f'<div class="card sec"><h2>机构评级与目标价</h2>{_actions_body(payload)}</div>'


def _actions_body(payload):
    rows = payload.get("analyst_actions") or []
    if not rows:
        return '<p class="dim">评级调整数据尚未采集——首轮采集后这里会列出各家机构最近两次调整。</p>'
    items = []
    seen = {}
    for r in rows:
        key = r["firm"]
        if seen.get(key, 0) >= 2:
            continue
        seen[key] = seen.get(key, 0) + 1
        prior, cur = r.get("prior_pt"), r.get("current_pt")
        pt = ""
        if cur:
            cur = float(cur)
            if prior:
                prior = float(prior)
                tone = "down" if cur < prior else "up" if cur > prior else ""
                mark = "↓" if cur < prior else "↑" if cur > prior else "→"
                pt = f' · 目标价 ${prior:,.0f} → <b class="{tone}">${cur:,.0f} {mark}</b>'
            else:
                pt = f" · 目标价 前值暂缺 → ${cur:,.0f}"
        act = r.get("action")
        grade_tone = "down" if act == "down" else "up" if act == "up" else ""
        grade = (
            f"{_text(r.get('from_grade'))} → {_text(r.get('to_grade'))}"
            if r.get("from_grade") and r.get("from_grade") != r.get("to_grade")
            else f"维持 {_text(r.get('to_grade') or '—')}"
        )
        items.append(
            f'<div class="row"><span class="dim">{r["action_date"]}</span> <b>{_text(r["firm"])}</b> '
            f'<span class="{grade_tone}">{grade}</span>{pt}</div>'
        )
    newest = max((r["action_date"] for r in rows), default=None)
    recent = [
        r
        for r in rows
        if newest and (date.fromisoformat(str(newest)[:10]) - date.fromisoformat(str(r["action_date"])[:10])).days <= 30
    ]
    ups = sum(
        1 for r in recent if r.get("current_pt") and r.get("prior_pt") and float(r["current_pt"]) > float(r["prior_pt"])
    )
    downs = sum(
        1 for r in recent if r.get("current_pt") and r.get("prior_pt") and float(r["current_pt"]) < float(r["prior_pt"])
    )
    return (
        '<div class="card sec"><h2>机构评级与目标价'
        f'<span class="stamp">近 30 天目标价 上调 {ups} 家 · 下调 {downs} 家</span></h2>'
        + "".join(items[:10])
        + (
            f'<details><summary class="dim">更多 {len(items) - 10} 条</summary>' + "".join(items[10:]) + "</details>"
            if len(items) > 10
            else ""
        )
        + '<p class="dim small">数据源只提供机构名，不含分析师个人姓名。</p></div>'
    )


def _earnings_hist_module(payload):
    rows = payload.get("earnings_hist") or []
    if not rows:
        return ""

    def num(v, fmt):
        return format(v, fmt) if v is not None else "—"

    trs = "".join(
        f"<tr><td>{_text(r['q'])}</td><td>{_text(r.get('report_date') or '日期未知')}</td>"
        f"<td class='num'>{num(r.get('est'), '.2f')}</td><td class='num'>{num(r.get('act'), '.2f')}</td>"
        f"<td class='num {_tone(r.get('gap') or 0)}'>{num(r.get('gap'), '+.1f')}%</td>"
        f"<td class='num'>{_pct(r.get('next_day'), 1) if r.get('next_day') is not None else '—'}</td></tr>"
        for r in reversed(rows)
    )
    return (
        '<div class="card sec"><h2>历次财报</h2>'
        '<table class="tbl"><tr><th>财季截止</th><th>发布日</th><th>预期 EPS</th><th>实际 EPS</th>'
        "<th>超出 / 不及</th><th>次日涨跌</th></tr>" + trs + "</table>"
        '<div class="small muted">发布日只在财报日历或系统记录中有时显示；没有发布日时不计算次日涨跌。</div></div>'
    )


def _stock_today(payload):
    """§4 '今天发生了什么': live anomalies for this stock and its baskets."""
    rows = (payload.get("news_modules") or {}).get("live") or []
    symbol = payload.get("symbol") or ""
    mine = [r for r in rows if r.get("subject") == symbol or (r.get("members") and symbol in r["members"])]
    if not mine:
        return (
            '<div class="card sec cat-anomaly"><h2>今天发生了什么</h2>'
            '<p class="dim">今天没有该股或所在板块的异常</p></div>'
        )
    items = "".join(
        f'<div class="row">{_kind_chip(r.get("cause_kind"))} <b>{_text(r.get("basket_name") or r["subject"])}</b>'
        f' <span class="num">{_pct(r.get("peak_ret"), 1)}</span> '
        f'<span class="dim trunc" title="{_text(r.get("cause_headline") or "")}">'
        f"{_text(r.get('cause_headline') or '原因未明')}</span></div>"
        for r in mine
    )
    return f'<div class="card sec cat-anomaly"><h2>今天发生了什么</h2>{items}</div>'


def _stock_earnings_card(payload):
    row = payload.get("earnings_card")
    if not row:
        return ""
    stage = {"upcoming": "财报前", "released": "已发布", "voted": "次日投票"}[row.get("stage")]
    card = row.get("card") or {}
    tl = {"post": "盘后", "pre": "盘前"}.get(row.get("report_time"), "时间待定")
    stats = [("发布", f"{row['report_date']} {tl}")]
    imp = card.get("implied_move") or {}
    imp_txt = f"{imp['straddle_pct'] * 100:.1f}%" if imp.get("straddle_pct") is not None else "无期权参照"
    if row.get("stage") == "upcoming":
        cons = card.get("consensus") or {}
        stats += [
            ("一致预期 EPS", f"{cons['eps']:.2f}" if cons.get("eps") is not None else "暂缺"),
            ("期权预期涨跌", imp_txt),
            (
                "历史财报后涨跌",
                f"中位 {card['history']['median_abs'] * 100:.1f}%"
                if (card.get("history") or {}).get("median_abs") is not None
                else "历史不足",
            ),
        ]
    else:
        seg = card.get("segment_reaction") or {}
        vote = card.get("vote_ret")
        stats += [
            ("次日投票", _pct(vote, 1) if vote is not None else "待收盘"),
            ("与期权预期比", _text(card.get("vs_implied") or imp_txt)),
            ("同环节跟随", f"{seg['followed']} 家跟 · {seg['not_followed']} 家未跟" if seg else "暂缺"),
        ]
    stat_html = "".join(
        f'<div><div class="small muted">{_text(k)}</div><div style="font-size:16px">'
        f"{v if '<' in str(v) else _text(v)}</div></div>"
        for k, v in stats
    )
    events = []
    for e in (card.get("events") or [])[:4]:
        r = e.get("reaction") or {}
        react = " · ".join(
            f"{label} {_pct(r[key]['ret'], 1)}"
            for key, label in (("m15", "15 分钟"), ("m60", "60 分钟"), ("session_end", "时段末"))
            if isinstance(r.get(key), dict) and r[key].get("ret") is not None
        )
        events.append(
            f'<div class="row">{_kind_chip(e.get("kind"))} {_facts_chips(e.get("facts") or {})} '
            f"{_text(e.get('headline') or '')}"
            + (f'<div class="small muted">发布后反应：{react}</div>' if react else "")
            + "</div>"
        )
    missing = row.get("missing") or []
    miss_html = f'<div class="small muted">缺：{_text("、".join(missing))}</div>' if missing else ""
    return (
        f'<div class="card sec cat-earnings"><h2>财报 · {row["report_date"]} '
        f'<span class="chip">{stage}</span></h2>'
        f'<div class="grid" style="grid-template-columns:repeat({len(stats)},1fr);gap:10px">{stat_html}</div>'
        + "".join(events)
        + miss_html
        + "</div>"
    )


def _movers_module(payload):
    mods = payload.get("news_modules") or {}
    rows = []
    held = set(payload.get("held_tickers") or [])
    for m in mods.get("movers") or []:
        warn = '<div class="small muted">暂无相关新闻</div>' if not m.get("has_news") else ""
        ev = m.get("event")
        ev_html = ""
        if ev is not None:
            chip = f'<span class="chip stale">{_text(m.get("event_chip") or "")}</span>' if m.get("event_chip") else ""
            when = _bj_hhmm(ev.get("first_seen_at"))
            shown_headline = ev.get("title_zh") or ev.get("headline") or ""
            ev_html = (
                f'<div class="mnews"><a href="{_text(ev.get("url") or "#")}">{_text(shown_headline)}</a>'
                f' {chip} <span class="small muted">{when}</span></div>'
            )
        own = "".join(_news_row(n, held) for n in m.get("news") or [])
        if m.get("news_unconfirmed") and own:
            own = f'<div class="small muted">相关新闻，未确认是原因</div>{own}'
        own_html = ev_html + (f'<div class="mnews">{own}</div>' if own else "")
        badge = '<span class="chip held">持仓</span>' if m.get("held") else '<span class="chip buy">标的</span>'
        intra = _intra_line((payload.get("intraday") or {}).get(m.get("ticker")))
        snap_ret = m.get("snap_ret")
        main_ret = snap_ret if snap_ret is not None else m.get("ret")
        sub = (
            f'<span class="small muted">收盘 {_signed(m["ret"] * 100, 2) if m.get("ret") is not None else "—"}</span>'
            if snap_ret is not None
            else ""
        )
        vol = _times(m.get("vol"))
        vol_html = "量比 暂缺" if vol == "暂缺" else _text(vol)
        rows.append(
            f'<div class="mrow"><span class="tk">{_text(m["ticker"])} {badge}{_tech_chip(m.get("tech"))}</span>'
            f'<span class="small ink2">{_text(m.get("theme"))}{warn}</span>'
            f'<span class="num r">{_pct(main_ret)}{sub}</span>'
            f'<span class="num r v4">{vol_html}</span></div>{intra}{own_html}'
        )
    if not rows:
        return ""
    carry = _carry_tag(payload)
    note = ' <span class="muted">盘前数据不进入规则 A</span>' if payload.get("intraday") else ""
    return (
        f'<div class="card sec" id="movers"><h2>持仓与标的异动{carry}</h2>'
        '<div class="small muted" style="margin-bottom:8px">'
        f"当日涨跌幅绝对值最大的 8 只 · 每只最多 1 条相关新闻{note}</div>" + "".join(rows) + "</div>"
    )


def _theme_news_module(payload):
    mods = payload.get("news_modules") or {}
    held = set(payload.get("held_tickers") or [])
    rows = []
    for n in mods.get("theme_news") or []:
        rows.append(
            f'<div class="nrow"><span class="tm">{_hm(n.get("published_at") or n.get("published"))}</span>'
            f'<div class="hl"><span class="tag macro">{_text(n.get("theme"))}</span>'
            f"{_ntitle(n, _text(_safe_url(n.get('url'))))} {_nlate(n)}</div>"
            f'<span class="codes">{_ncodes(n, held)}</span></div>'
        )
    if not rows:
        return ""
    return f'<div class="card sec"><h2>热门主题新闻</h2>{"".join(rows)}</div>'


def _feed_module(payload):
    mods = payload.get("news_modules") or {}
    held = set(payload.get("held_tickers") or [])
    feed = mods.get("feed") or []
    rows = []
    for i, n in enumerate(feed):
        row = _news_row(n, held)
        if i >= 10:
            row = row.replace('<div class="nrow"', '<div class="nrow x" hidden', 1).replace(
                '<details class="nrow', '<details class="nrow x" hidden', 1
            )
        rows.append(row)
    more = (
        f'<button class="small" data-feed-more>展开剩余 {max(0, len(feed) - 10)} 条</button>' if len(feed) > 10 else ""
    )
    body = "".join(rows) or '<div class="empty">无</div>'
    return (
        f'<div class="card" id="feed"><h2>滚动新闻 <span class="small muted">'
        f"{'最近 24 小时' if payload.get('is_today') else f'最近 {len(feed)} 条'}</span></h2>"
        f'<div class="scroll">{body}{more}</div></div>'
    )


_ETIME = {
    "pre": "盘前",
    "post": "盘后",
    "overnight": "隔夜",
    "unknown": "未定",
    "pre-market": "盘前",
    "after-hours": "盘后",
}


def _e_time(e):
    return _ETIME.get(str(e.get("time")), _text(e.get("time")))


def _e_eps(e):
    return _text(e.get("eps_forecast") or "—")


def _cal_week(e):
    head = f"{_md_local(e['report_date'])} · {_e_time(e)}"
    tail = f"预期 EPS {_e_eps(e)} · {_count(e.get('n_estimates'))} 家"
    return (
        f'<div class="cal"><span class="cd">{head}</span>'
        f' <span class="cs">{_text(e["ticker"])}</span> '
        f'<span class="small ink2">{_text(e.get("company"))}</span>'
        f'<span class="small muted" style="float:right">{tail}</span></div>'
    )


def _cal_mine(e):
    chip = '<span class="chip held">持仓</span>' if e.get("held") else '<span class="chip buy">标的</span>'
    line = f"{_e_time(e)} {_md_local(e['report_date'])} · 预期 EPS {_e_eps(e)}"
    pvs = "".join(
        f'<div class="pv"><span class="tag hot">财报前瞻</span>{_ntitle(n, _text(_safe_url(n.get("url"))))}</div>'
        for n in e.get("previews") or []
    )
    return (
        f'<div class="cal"><span class="cs">{_text(e["ticker"])}</span> {chip} '
        f'<span class="cd">{line}</span>{pvs}</div>'
    )


def _calendar_module(payload):
    earnings = payload.get("earnings")
    econ = payload.get("econ")
    if earnings is None and econ is None:
        return '<div class="card"><h2>财报日历</h2><div class="empty">日历待接入</div></div>'
    parts = ['<div class="card"><h2>财报日历 <span class="small muted">来源 日历</span></h2><div class="scroll">']
    empty = '<div class="empty">无</div>'
    if earnings is None:
        parts.append('<h3>本周重点（市值前 10）</h3><div class="empty">日历待接入</div>')
    else:
        wk = "".join(_cal_week(e) for e in earnings.get("week") or [])
        parts.append("<h3>本周重点（市值前 10）</h3>" + (wk or empty))
        mine = "".join(_cal_mine(e) for e in earnings.get("mine") or [])
        parts.append('<h3 style="margin-top:14px">持仓与标的（未来 10 天）</h3>' + (mine or empty))
    if econ is None:
        parts.append('<h3 style="margin-top:14px">本周宏观</h3><div class="empty">日历待接入</div>')
    else:
        rows = "".join(
            '<div class="nrow" style="grid-template-columns:64px 1fr auto">'
            f'<span class="tm">{_md_local(e["event_date"])} {_text(e.get("event_time_et") or "")}</span>'
            f'<div class="hl">{_text(e.get("name"))}</div>'
            f'<span class="small muted">预期 {_text((e.get("consensus") or "—").strip() or "—")}'
            f" / 前值 {_text(e.get('previous') or '—')}</span></div>"
            for e in econ
        )
        parts.append(
            '<h3 style="margin-top:14px">本周宏观</h3>' + (rows or '<div class="empty">本周暂无关键宏观数据</div>')
        )
    parts.append("</div></div>")
    return "".join(parts)


def _close_cell(r):
    return "$" + (f"{float(r.get('close')):.2f}" if r.get("close") is not None else "—")


def _lb_row(r, extra):
    return (
        '<div class="nrow" style="grid-template-columns:64px 1fr auto">'
        f'<span style="font:600 13px var(--mono)">{_text(r["ticker"])}</span>'
        f'<span class="small ink2">{_text(extra(r))}</span>'
        f'<span class="num">{_pct(r.get("ret"))}</span></div>'
    )


def _lb_theme(r):
    return r.get("theme") or ""


def _lb_cell(items, fn):
    return "".join(_lb_row(r, fn) for r in items)


def _leaderboards_module(payload):
    mods = payload.get("news_modules") or {}
    up = mods.get("pool_leaders_up") or []
    down = mods.get("pool_leaders_down") or []
    wup = payload.get("wide_movers_up") or []
    wdown = payload.get("wide_movers_down") or []
    return (
        '<div class="card sec"><h2>涨跌排行榜</h2><div class="lboard">'
        f"<div><h3>标的池 · 涨幅前 5</h3>{_lb_cell(up, _lb_theme)}</div>"
        f"<div><h3>标的池 · 跌幅前 5</h3>{_lb_cell(down, _lb_theme)}</div>"
        f"<div><h3>全市场 · 涨幅前 5</h3>{_lb_cell(wup, _close_cell)}</div>"
        f"<div><h3>全市场 · 跌幅前 5</h3>{_lb_cell(wdown, _close_cell)}</div>"
        "</div></div>"
    )


def _earnings_chips(payload):
    near = payload.get("earnings_near") or []
    if not near:
        return ""
    bits = []
    for e in near[:6]:
        when = f"{_ETIME.get(str(e.get('time')), _text(e.get('time')))} {_md_local(e['report_date'])}"
        bits.append(f'<span class="chip ok">财报临近 {_text(e["ticker"])} {when}</span>')
    return '<div class="small" style="margin-top:8px">' + " ".join(bits) + "</div>"


def _stock_feed(payload):
    feed = payload.get("news_feed") or []
    held = set(payload.get("held_tickers") or [])
    rows = "".join(_news_row(n, held) for n in feed)
    ev = payload.get("event")
    if ev is not None:
        from inves_cog.web.brief import _facts_chip

        chip = _facts_chip(ev.get("facts") or {})
        when = _bj_hhmm(ev.get("first_seen_at"))
        rows = (
            f'<div class="mnews"><a href="{_text(ev.get("url") or "#")}">'
            f"{_text(ev.get('title_zh') or ev.get('headline') or '')}</a>"
            + (f' <span class="chip stale">{_text(chip)}</span>' if chip else "")
            + f' <span class="small muted">{when}</span></div>'
            + rows
        )
    empty = '<div class="empty">近 7 天没有该股新闻</div>'
    return '<h3 style="margin-top:14px">新闻流（近 7 天）</h3>' + (rows or empty)


def _tech_cell(tech):
    if not isinstance(tech, dict):
        return '<span class="muted">暂缺</span>'
    shape = tech.get("shape") or "数据不足"
    rsi = tech.get("rsi")
    tail = ""
    if rsi is not None:
        note = " 超买" if rsi >= 70 else " 超卖" if rsi <= 30 else ""
        tail = f'<span class="small muted"> · RSI {half_up(rsi, 1):.1f}{note}</span>'
    sig = "、".join(tech.get("signals") or [])
    extra = f'<div class="muted">{_text(sig)}</div>' if sig else ""
    return f'<span class="num">{_text(shape)}</span>{tail}{extra}'


def _next_earn(payload):
    e = payload.get("next_earnings")
    if not isinstance(e, dict):
        return _miss()
    when = f"{_ETIME.get(str(e.get('time')), _text(e.get('time')))} {_md_local(e['report_date'])}"
    return f"{_text(when)} · 预期 EPS {_text(e.get('eps_forecast') or '—')}"
