"""Investor pages. Structure follows the final prototype; numbers come from the brief payload."""

import json
from datetime import date, timedelta
from html import escape
from pathlib import Path

from inves_cog.ingest.market import next_trading_day, trading_day
from inves_cog.web.brief import (
    MISSING,
    PAPER_LABEL,
    format_fraction,
    format_points,
    half_up,
    human_reason,
    short_unvalued_text,
)
from inves_cog.web.exit_levels import money
from inves_cog.web.pages import CLOSED
from inves_cog.web.risk_brief import format_plain_percent, risk_params
from inves_cog.web.ruler import ruler

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
_STYLE = Path(__file__).with_name("investor.css").read_text(encoding="utf-8")
_EXTRA = """
body:not(.intra) #intra-banner{display:none}
.hrow[hidden],.detail[hidden]{display:none}
"""


def render_brief(payload):
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("message") == CLOSED:
        return _document("非交易日", _nav(payload) + "<main><p>非交易日</p></main>")
    page = payload.get("page")
    if page == "/stocks":
        main = _stocks(payload)
    elif page == "/account":
        main = _account(payload)
    elif page == "/trust":
        main = _trust(payload)
    elif isinstance(page, str) and page.startswith("/s/"):
        main = _stock(payload)
    else:
        main = _market(payload)
    title = payload.get("title") or "每日页面"
    body = _header(payload) + "<main>" + _intra() + main + _foot(payload) + "</main>"
    return _document(title, body)


def _market(payload):
    headings = payload.get("headings") or ["市场总览", "资金：领跌或领涨暂缺", "情绪：谨慎，未恐慌", "今天的大事"]
    judgment = payload.get("judgment") or ""
    held = set(payload.get("held_tickers") or [])
    cards = []
    closes = payload.get("index_closes") if isinstance(payload.get("index_closes"), dict) else {}
    for row in payload.get("indexes") or []:
        series = closes.get(row.get("id")) or []
        spark = _mini(series) if len(series) >= 2 else '<span class="gap">近 20 日走势：待接入</span>'
        post = row.get("post")
        post_html = "" if post is None else f"<span>盘后 {format_fraction(post)}</span>"
        cards.append(
            '<div class="card kpi">'
            f'<span class="l">{_text(row.get("name"))}</span> '
            f'<b class="{_tone(row.get("ret"))}">{format_fraction(row.get("ret"))}</b> '
            f"{post_html} {spark}</div>"
        )
    up = payload.get("advancers")
    down = payload.get("decliners")
    total = (up or 0) + (down or 0)
    share = 0 if not total else (up or 0) / total * 100
    cards.append(
        '<div class="card kpi"><span class="l">涨 / 跌家数</span> '
        f'<b><span class="up">{_count(up)}</span> / <span class="down">{_count(down)}</span></b>'
        f'<div class="bar" style="height:8px"><i style="width:{share:.0f}%"></i></div></div>'
    )
    bars = _leaders(payload.get("leaders_down") or [], "领跌") + _leaders(payload.get("leaders_up") or [], "领涨")
    styles = "".join(
        f'<span class="chip ok">{_text(row.get("name"))} {format_fraction(row.get("ret"))}</span>'
        for row in payload.get("styles") or []
    )
    spread = payload.get("sector_spread_z")
    spread_text = MISSING if spread is None else f"{float(spread):.1f}σ"
    vix = payload.get("vix")
    source = " <span>来源 FRED</span>" if payload.get("vix_source") == "FRED" else ""
    vix_html = (
        f'<span class="chip miss">{MISSING}</span>' if vix is None else f'<b class="num">{float(vix):.2f}</b>{source}'
    )
    pin = 0 if vix is None else max(0, min(100, (float(vix) - 10) / 30 * 100))
    events = _events(payload, held)
    note = payload.get("risk_note") or MISSING
    return (
        f"<h1>判断：{_text(judgment)}</h1>"
        f'<p class="sub">{_text(payload.get("oneliner"))}</p>'
        f'<div class="grid g4 sec">{"".join(cards)}</div>'
        '<div class="card sec"><h3>对我意味着什么</h3>'
        f"<p>{_text(payload.get('implication') or MISSING)}</p><p>{_text(note)}</p></div>"
        '<div class="grid g-main sec"><div class="card">'
        f"<h2>{_text(headings[1])}</h2>{bars}"
        f'<div class="filters">{styles}'
        f'<span class="chip ok">板块分化 <span class="num">{_text(spread_text)}</span></span></div>'
        '</div><div class="card">'
        f"<h2>{_text(headings[2])}</h2>"
        f'<div class="gauge"><div class="pin" style="left:{pin:.0f}%"></div></div>'
        f"<p>VIX {vix_html}</p>"
        f"<p>期权看跌/看涨比 {_text(payload.get('put_call_text') or MISSING)}</p>"
        f"<p>3 个月 VIX {_plain(payload.get('vix3m'))}</p>"
        f"<p>近 5 日下跌股占比 {_plain(payload.get('down_share_5d_pct'))}</p>"
        f"<p>标普距一年高点 {format_points(payload.get('spy_drawdown_252_pct'))}</p>"
        "</div></div>"
        f'<div class="card sec"><h2>{_text(headings[3])}</h2>{events}</div>'
    )


def _leaders(rows, label):
    body = "".join(
        '<div class="small">'
        f'{_text(row.get("name"))} <span class="{_tone(row.get("ret"))}">{format_fraction(row.get("ret"))}</span></div>'
        for row in rows
    )
    return f'<div class="small muted">{label}</div>{body or _text(MISSING)}'


def _events(payload, held):
    rows = payload.get("events") or []
    if not payload.get("news_fresh"):
        banner = '<div class="banner warn"><b>原因暂不可信</b><span>当日新闻缺失，下列引用只作参考。</span></div>'
    else:
        banner = ""
    blocks = []
    for index, row in enumerate(rows):
        href = f"/linkage/{_text(row['event_id'])}" if row.get("event_id") else "/market"
        z = MISSING if row.get("max_abs_z") is None else f"{float(row['max_abs_z']):.1f}σ"
        members = []
        for ticker in row.get("members") or []:
            mark = " held" if ticker in held else ""
            members.append(f'<a class="tick{mark}" href="{_symbol_href(payload, ticker)}">{_text(ticker)}</a>')
        reasons = []
        if payload.get("news_fresh"):
            items = row.get("reasons") or []
            if not items and (row.get("explanation") or row.get("cited_at")):
                items = [{"text": row.get("explanation"), "cited_at": row.get("cited_at"), "stale_note": None}]
            for item in items:
                stale = item.get("stale_note")
                chip = f' <span class="chip stale">旧闻 {_text(stale)}</span>' if stale else ""
                reasons.append(
                    f"<li>{_text(item.get('text') or MISSING)} "
                    f"<span>引用时间 {_text(item.get('cited_at') or MISSING)}</span>{chip}</li>"
                )
        opened = " open" if index == 0 else ""
        blocks.append(
            f'<div class="event{opened}"><div class="h" data-ev>'
            f'<span class="sig">{_text(z)}</span> <a href="{href}"><b>{_text(row.get("title"))}</b></a>'
            '</div><div class="body">'
            f'{"".join(members)}<ul class="news">{"".join(reasons) or "<li>暂无可引用的解释。</li>"}</ul>'
            "</div></div>"
        )
    return banner + ("".join(blocks) or f"<p>{_text(MISSING)}</p>")


def _stocks(payload):
    themes = payload.get("themes") or []
    theme_rows = []
    flat = []
    for theme in themes:
        sector = theme.get("sector") or MISSING
        opened = bool(theme.get("open"))
        hidden = "" if opened else " hidden"
        members = theme.get("members") or []
        ticks = []
        for row in members:
            row = dict(row)
            row["sector"] = sector
            flat.append(row)
            mark = " held" if row.get("held") else ""
            href = _symbol_href(payload, row.get("ticker"))
            ticks.append(
                f'<a class="tick{mark}" href="{href}">{_text(row.get("ticker"))} {format_fraction(row.get("ret"))}</a>'
            )
        vol = theme.get("volume_multiple")
        vol_text = MISSING if vol is None else f"{half_up(vol, 1):.1f}倍"
        theme_rows.append(
            f'<tr class="click" data-th="{_text(sector)}"><td><b>{_text(sector)}</b></td>'
            f"<td>{format_fraction(theme.get('average'))}</td>"
            f'<td class="r">{_text(vol_text)}</td>'
            f'<td class="r">{_count(theme.get("held_count"))} / {_count(theme.get("buyable_count"))}</td>'
            f'<td class="small">{_text(theme.get("line"))}</td>'
            f'<td class="r">平均空头占比 {_text(theme.get("short_text") or MISSING)}</td></tr>'
            f'<tr class="members"{hidden}><td colspan="6">{"".join(ticks)}'
            f'<a data-only="{_text(sector)}">在下表只看这个主题</a></td></tr>'
        )
    head = (
        '<tr><th data-sc="t">代码</th><th data-sc="theme">主题</th><th data-sc="chg">当日</th>'
        '<th data-sc="vol">量比</th><th data-sc="rsi">RSI</th><th data-sc="d200">距 200 日线</th>'
        '<th data-sc="dhigh">距一年高点</th><th data-sc="short_ratio">空头</th>'
        '<th data-sc="st">状态</th><th data-sc="event">事件</th><th>今日新闻</th><th>估值</th></tr>'
    )
    body = "".join(_stock_row(payload, row) for row in flat)
    filters = (
        '<button class="f on" data-sf="all">全部</button>'
        '<button class="f" data-sf="held">持仓</button>'
        '<button class="f" data-sf="buy">可买</button>'
        '<button class="f" data-sf="move">异动</button>'
        '<button class="f" data-sf="crowd">空头拥挤</button>'
        '<select class="f" id="sth"><option value="">全部主题</option>'
        + "".join(f"<option>{_text(theme.get('sector'))}</option>" for theme in themes)
        + '</select><input class="f" id="sq" placeholder="搜索代码">'
    )
    return (
        f"<h1>{_text(payload.get('oneliner') or MISSING)}</h1>"
        '<div class="card sec"><h2>主题强弱</h2>'
        f'<table><thead><tr><th>主题</th><th>平均涨跌</th><th class="r">量比</th>'
        '<th class="r">持有 / 可买</th><th>一句话</th><th class="r">空头占比</th></tr></thead>'
        f'<tbody id="ttable">{"".join(theme_rows)}</tbody></table></div>'
        '<div class="card sec"><h2>逐只明细</h2><p class="num" id="scount"></p>'
        f'<div class="filters" id="sfilters">{filters}</div>'
        f'<table><thead id="shead">{head}</thead><tbody id="stable">{body}</tbody></table></div>'
    )


def _stock_row(payload, row):
    ticker = row.get("ticker") or ""
    ret = row.get("ret")
    vol = row.get("volume_multiple")
    move = (ret is not None and abs(float(ret)) >= _MOVE) or (vol is not None and float(vol) >= 2)
    short = row.get("short") if isinstance(row.get("short"), dict) else None
    crowd = bool(short and short.get("crowded"))
    held = bool(row.get("held"))
    buy = row.get("entry_pass") is True and not held
    if held:
        status = "持有"
    elif buy:
        status = "未持有 可买"
    elif row.get("entry_pass") is False:
        status = "未持有"
    else:
        status = MISSING
    rsi = row.get("rsi")
    rsi_text = MISSING if rsi is None else str(int(half_up(rsi, 0)))
    vol_text = MISSING if vol is None else f"{half_up(vol, 1):.1f}×（{half_up(vol, 1):.1f}倍）"
    events = "、".join(row.get("events") or []) or "—"
    news = row.get("news") or []
    count = row.get("news_count")
    if count:
        lines = "".join(
            f"<p>{_text(item.get('summary'))} · {_text(item.get('source'))} · "
            f"{_text(item.get('published_beijing'))}</p>"
            for item in news
        )
        news_html = f"<details><summary>{int(count)}</summary>{lines}</details>"
    else:
        news_html = _text(0 if count == 0 else MISSING)
    short_text = row.get("short_text") or MISSING
    attrs = " ".join(
        [
            f'data-ticker="{_text(ticker)}"',
            f'data-theme="{_text(row.get("sector") or "")}"',
            f'data-held="{1 if held else 0}"',
            f'data-buy="{1 if buy else 0}"',
            f'data-move="{1 if move else 0}"',
            f'data-crowd="{1 if crowd else 0}"',
            f'data-chg="{_num_attr(ret)}"',
            f'data-vol="{_num_attr(vol)}"',
            f'data-rsi="{_num_attr(rsi)}"',
            f'data-d200="{_num_attr(row.get("price_vs_ma200"))}"',
            f'data-dhigh="{_num_attr(row.get("drawdown252"))}"',
            f'data-short_ratio="{_num_attr(None if short is None else short.get("pct"))}"',
            f'data-st="{0 if held else 1 if buy else 2}"',
            f'data-t="{_text(ticker)}"',
        ]
    )
    return (
        f"<tr {attrs}>"
        f'<td><a href="{_symbol_href(payload, ticker)}"><b>{_text(ticker)}</b></a></td>'
        f'<td class="small">{_text(row.get("sector"))}</td>'
        f'<td class="{_tone(ret)}">{format_fraction(ret)}</td>'
        f"<td>{_text(vol_text)}</td>"
        f"<td>{_text(rsi_text)}</td>"
        f"<td>{format_points(row.get('price_vs_ma200'))}</td>"
        f"<td>{format_points(row.get('drawdown252'))}</td>"
        f"<td>{_text(short_text)}</td>"
        f"<td>{_text(status)}</td>"
        f'<td class="small">{_text(events)}</td>'
        f"<td>{news_html}</td>"
        f"<td>{_valuation(row.get('valuation'))}</td></tr>"
    )


def _account(payload):
    red = int(payload.get("down_red") or 0)
    orange = int(payload.get("down_orange") or 0)
    takes = payload.get("take_profits") or []
    pending = payload.get("pending_orders") or []
    title = f"{red} 项重点下行风险"
    if pending:
        title += f"，{_text(pending[0].get('ticker'))} 待成交"
    banner = ""
    if payload.get("plan_missing"):
        carried = payload.get("carried_from") or MISSING
        banner = (
            '<div class="banner warn"><b>计划缺失</b><span>'
            f"{_text(payload.get('date'))} 计划缺失，以下沿用 {_text(carried)} 日持仓，不代表空仓。"
            "</span></div>"
        )
    estimate = payload.get("close_estimate") if isinstance(payload.get("close_estimate"), dict) else None
    if estimate:
        equity = money(estimate.get("equity"))
        day_pnl = money(estimate.get("day_pnl"))
        label = _text(estimate.get("label") or "")
        day_foot = f"{format_fraction(payload.get('day_change'))} · {label}"
        equity_foot = label
    else:
        equity = money(payload.get("equity"))
        day_pnl = format_fraction(payload.get("day_change"))
        equity_foot = ""
        day_foot = ""
    kpis = (
        f'<div class="card kpi"><span class="l">总资产</span><b>{equity}</b><span class="ft">{equity_foot}</span></div>'
        f'<div class="card kpi"><span class="l">当日损益</span>'
        f'<b class="{_tone(payload.get("day_change"))}">{day_pnl}</b>'
        f'<span class="ft">{day_foot}</span></div>'
        f'<div class="card kpi"><span class="l">距历史高点</span><b>{format_fraction(payload.get("drawdown"))}</b>'
        '<span class="ft">与回撤刹车同一口径</span></div>'
        f'<div class="card kpi"><span class="l">现金</span><b>{money(payload.get("cash"))}</b></div>'
    )
    groups = _risk_groups(payload)
    bounds = _bounds(payload)
    holdings = _holdings(payload)
    orders = _pending(payload)
    closed = _closed(payload)
    candidates = _candidates(payload)
    return (
        banner
        + f"<h1>{title}</h1>"
        + f'<p class="sub">下行风险：重点 {red} / 关注 {orange} · 止盈提示 {len(takes)} 项（不计入风险）</p>'
        + f'<div class="grid g4 sec">{kpis}</div>'
        + '<div class="grid g-main sec"><div class="card"><h2>今天先看这些</h2>'
        + '<div class="legend"><span class="chip hi">! 重点下行</span><span class="chip mid">▲ 下行关注</span>'
        + '<span class="chip tp">↗ 止盈提示</span></div>'
        + groups
        + '</div><div class="card"><h2>组合边界</h2>'
        + bounds
        + "</div></div>"
        + '<div class="card sec"><h2>持仓与关键价位</h2>'
        + '<div class="filters" id="hfilters">'
        + '<button class="f on" data-hf="all">全部持仓</button>'
        + '<button class="f" data-hf="down">下行风险</button>'
        + '<button class="f" data-hf="tp">止盈提示</button>'
        + '<button class="f" data-hf="core">核心仓</button>'
        + '<button class="f" data-hf="swing">观察波段仓</button></div>'
        + '<div class="filters"><button class="f on" data-s="risk">风险优先</button>'
        + '<button class="f" data-s="pnl">盈亏</button><button class="f" data-s="day">当日涨跌</button></div>'
        + f'<div id="hlist">{holdings}</div></div>'
        + '<div class="grid g2 sec"><div class="card"><h2>待成交</h2>'
        + orders
        + '</div><div class="card"><h2>处置记录</h2>'
        + closed
        + "</div></div>"
        + '<div class="card sec"><h2>待选股票</h2><p class="small">符合买入条件，尚未持有</p>'
        + candidates
        + "</div>"
    )


def _risk_groups(payload):
    downs = [row for row in payload.get("risk_lines") or [] if row.get("ticker")]
    takes = payload.get("take_profits") or []
    down_html = (
        "".join(_risk_item(row, False) for row in downs) or '<div class="empty">当前没有需要关注的下行风险</div>'
    )
    take_html = "".join(_risk_item(row, True) for row in takes) or '<div class="empty">当前没有止盈提示</div>'
    return (
        '<div class="rgroup">下行风险</div><div class="rlist" id="rlist">'
        + down_html
        + '</div><div class="rgroup">止盈提示 · 不计入风险</div><div class="rlist">'
        + take_html
        + "</div>"
    )


def _risk_item(row, take):
    if take:
        icon = '<span class="ico tp">↗</span>'
    elif row.get("level") == "red":
        icon = '<span class="ico hi">!</span>'
    else:
        icon = '<span class="ico mid">▲</span>'
    ticker = row.get("ticker") or ""
    return (
        f'<div class="ritem" data-go="{_text(ticker)}">{icon}<div><div class="t">'
        f'<span class="mono">{_text(ticker)}</span> {_text(row.get("text"))}</div></div>'
        '<span class="go">定位</span></div>'
    )


def _bounds(payload):
    card = payload.get("risk_card") if isinstance(payload.get("risk_card"), dict) else {}
    bars = []
    for theme in card.get("themes") or []:
        share = theme.get("share")
        width = 0 if share is None else max(0, min(100, float(share) / 0.40 * 100))
        bars.append(
            '<div class="conc"><span>'
            f'{_text(theme.get("sector"))}</span><span class="num">{format_plain_percent(share)}</span>'
            f'<div class="bar"><i style="width:{width:.1f}%"></i>'
            '<span class="th" style="left:62.5%"></span><span class="th" style="left:87.5%"></span></div></div>'
        )
    drawdown = payload.get("drawdown")
    dd8, dd12 = _triggers(payload.get("params_version"))
    axis = _axis(drawdown, dd8, dd12)
    gaps = (
        f"<p>距回撤刹车 {_text(card.get('dd8_gap'))}，距更深闸门 {_text(card.get('dd12_gap'))}</p>"
        f"<p>持仓 {_count(card.get('holdings'))} 只，名额 {_count(card.get('slots'))} 只</p>"
        f"<p>现金比例 {format_plain_percent(card.get('cash_ratio'))}</p>"
    )
    return "".join(bars) + axis + gaps


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
        return max(0, min(100, (float(points) - (-14)) / 14 * 100))

    current = None if drawdown is None else float(drawdown) * 100
    marks = []
    if place(dd12) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(dd12):.1f}%;top:4px;height:20px;'
            'border-left:2px solid var(--r-hi-line)"></div>'
        )
    if place(dd8) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(dd8):.1f}%;top:4px;height:20px;'
            'border-left:2px solid var(--r-mid-line)"></div>'
        )
    if place(current) is not None:
        marks.append(
            f'<div style="position:absolute;left:{place(current):.1f}%;top:6px;width:14px;height:14px;'
            'margin-left:-7px;border-radius:50%;background:var(--ink)"></div>'
        )
    dd8_label = MISSING if dd8 is None else format_points(dd8)
    dd12_label = MISSING if dd12 is None else format_points(dd12)
    return (
        '<div class="gate"><div class="small muted">组合回撤</div><div class="track"><div class="axis"></div>'
        + "".join(marks)
        + '</div><div class="small">'
        + f"更深闸门 {dd12_label} 回撤刹车 {dd8_label} 当前 {format_fraction(drawdown)}</div></div>"
    )


def _holdings(payload):
    takes = {row.get("ticker") for row in payload.get("take_profits") or []}
    blocks = []
    for row in payload.get("holdings") or []:
        ticker = row.get("ticker") or ""
        level = row.get("risk_level")
        chips = []
        rank = 3
        lv = "ok"
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
        day = row.get("day")
        pnl = row.get("pnl")
        spec = row.get("ruler") if isinstance(row.get("ruler"), dict) else {}
        blocks.append(
            f'<div class="hrow" id="row-{_text(ticker)}" data-row="{_text(ticker)}" data-lv="{lv}" '
            f'data-rank="{rank}" data-kind="{_text(kind)}" data-tp="{1 if ticker in takes else 0}" '
            f'data-pnl="{_num_attr(pnl)}" data-day="{_num_attr(day)}">'
            f'<div><div class="tk">{_text(ticker)}</div><div class="ty">{_text(kind)}</div></div>'
            f'<div><div class="px">{money(row.get("avg_cost"))} → {money(row.get("price"))}</div>'
            f'<div class="pl {_tone(pnl)}">{format_fraction(pnl)}</div>'
            f'<div class="small muted">当日 {format_fraction(day)}</div>'
            f'<div class="small">股数 {_shares(row.get("shares"))}</div></div>'
            f"{_ruler_box(spec)}"
            f'<div class="c-next">{"".join(chips)}<div class="nx">{_text(row.get("next_step") or MISSING)}</div>'
            f'<div class="small">{_valuation(row.get("valuation"))}</div></div>'
            '<span class="caret">›</span></div>'
            f'<div class="detail" id="det-{_text(ticker)}"><b>{_text(ticker)} · {_text(kind)}</b>'
            f'<a href="{_symbol_href(payload, ticker)}">打开个股页</a>'
            f'<a data-close="{_text(ticker)}">收起</a>'
            f'<div class="rules">{_rules(row.get("levels") or [])}</div></div>'
        )
    return "".join(blocks) or f"<p>{_text(MISSING)}</p>"


def _rules(levels):
    cards = []
    for row in levels:
        status = row.get("status") or "none"
        label = _RULE_STATE.get(status, _RULE_STATE["none"])
        conds = []
        for cond in row.get("conds") or []:
            ok = bool(cond.get("ok"))
            mark = "✓" if ok else "✗"
            note = cond.get("note") or ""
            extra = f"（{_text(note)}）" if note else ""
            conds.append(f'<li><span class="{"y" if ok else "n2"}">{mark}</span>{_text(cond.get("text"))}{extra}</li>')
        cond_html = f'<ul class="conds">{"".join(conds)}</ul>' if conds else ""
        cards.append(
            f'<div class="rule st-{_text(status)}"><div class="h"><span class="n">{_text(row.get("name"))}</span>'
            f'<span class="stc">{label}</span></div><div class="v">{_text(row.get("text") or MISSING)}</div>'
            f"{cond_html}</div>"
        )
    return "".join(cards) or f"<p>{_text(MISSING)}</p>"


def _pending(payload):
    rows = []
    for row in payload.get("pending_orders") or []:
        qty = row.get("qty")
        qty_text = '<span class="chip miss">暂缺</span>' if qty is None else _text(_shares(qty))
        side = _SIDE.get(row.get("side"), "减仓")
        when = row.get("since") or row.get("trade_date") or MISSING
        rows.append(
            f'<tr data-go="{_text(row.get("ticker"))}"><td><b>{_text(row.get("ticker"))}</b></td>'
            f"<td>{_text(side)}</td><td>{_text(human_reason(row.get('reason')) or MISSING)}</td>"
            f"<td>{_text(when)}</td><td>{qty_text}</td></tr>"
        )
    note = "" if payload.get("fills_readable", True) else "<p>成交记录暂不可读，下面只显示计划。</p>"
    return (
        note
        + "<table><tr><th>股票</th><th>方向</th><th>原因</th><th>起始</th><th>数量</th></tr>"
        + ("".join(rows) or f"<tr><td>{_text(MISSING)}</td></tr>")
        + "</table>"
    )


def _closed(payload):
    rows = []
    for row in payload.get("closed_records") or []:
        state = row.get("fill_state") or "计划"
        if state == "已成交":
            bits = ["已成交"]
            if row.get("fill_price") is not None:
                bits.append(money(row.get("fill_price")))
            if row.get("qty") is not None:
                bits.append(f"{_shares(row.get('qty'))} 股")
            label = " · ".join(bits)
        else:
            label = "计划"
        repeat = int(row.get("repeat") or 1)
        if repeat > 1:
            label += f" ×{repeat}"
        rows.append(
            "<tr>"
            f"<td>{_text(row.get('trade_date'))}</td><td><b>{_text(row.get('ticker'))}</b></td>"
            f"<td>{_text(_kind_label(row.get('kind')))}</td>"
            f"<td>{_text(human_reason(row.get('reason_zh')) or MISSING)}</td>"
            f"<td>{_text(label)}</td></tr>"
        )
    return (
        "<table><tr><th>日期</th><th>股票</th><th>动作</th><th>原因</th><th>状态</th></tr>"
        + ("".join(rows) or f"<tr><td>{_text(MISSING)}</td></tr>")
        + '</table><p class="small">计划为规则记录；成交后显示已成交、价格和股数。'
        "同一天同一代码同一原因的计划合并为一条，并标次数。</p>"
    )


def _candidates(payload):
    rows = []
    for row in payload.get("candidates") or []:
        books = row.get("books") or {}
        score = " / ".join(_score(books.get(key)) for key in ("quality", "growth", "valuation", "timing"))
        rows.append(
            f'<tr><td><a href="{_symbol_href(payload, row.get("ticker"))}"><b>{_text(row.get("ticker"))}</b></a></td>'
            f'<td class="r">{money(row.get("price"))}</td>'
            f'<td class="r">{money(row.get("ma50"))}</td>'
            f'<td class="r">{money(row.get("year_high"))}</td>'
            f"<td>{_text(score)}</td><td>{_valuation(row.get('valuation'))}</td></tr>"
        )
    return (
        "<table><tr><th>股票</th><th>现价</th><th>50 日线</th><th>一年高点</th><th>质量 / 成长 / 估值 / 择时</th>"
        "<th>估值参考</th></tr>" + ("".join(rows) or f"<tr><td>{_text(MISSING)}</td></tr>") + "</table>"
    )


def _trust(payload):
    cards = []
    for item in payload.get("statuses") or []:
        state = item.get("state") or MISSING
        extra = ""
        if item.get("item") == "新闻":
            extra = (
                f"最近入库 {_text(payload.get('news_seen_beijing') or MISSING)} "
                f"最近 1 个交易日 {_count(payload.get('news_day_count'))} 条"
            )
        elif item.get("detail"):
            extra = _text(item.get("detail"))
        cards.append(
            '<div class="stat" data-stat><div class="h"><b>'
            f'{_text(item.get("item"))}</b><span class="chip">{_text(state)}</span></div>'
            f'<div class="w">{extra}</div><div class="imp">影响见该项状态。</div></div>'
        )
    if payload.get("labels"):
        review = "".join(
            f"<p>{_text(row.get('horizon'))} {_text(row.get('as_of'))} {_text(row.get('reason') or '')}</p>"
            for row in payload["labels"]
        )
    else:
        review = (
            '<div class="empty">还没有完成的复盘记录。</div>'
            f"<p>{_text(payload.get('review_gap') or '尚无 T+1/T+5/T+20 打标记录')}</p>"
        )
    anomalies = payload.get("anomalies") or []
    found = (
        "".join(
            f'<div><b>{_text(row.get("title"))}</b><div class="small">{_text(row.get("detail"))}</div></div>'
            for row in anomalies
        )
        or '<div class="empty">当前没有列出的数据异常</div>'
    )
    return (
        f"<h1>{_text(payload.get('oneliner') or '复盘与数据')}</h1>"
        f'<div class="card sec"><h2>数据状态</h2><div class="status">{"".join(cards)}</div></div>'
        '<div class="grid g2 sec"><div class="card"><h2>系统之前说的对不对</h2>'
        f'{review}</div><div class="card"><h2>发现的数据异常</h2>{found}</div></div>'
        '<details class="method"><summary>计算口径说明</summary><div>'
        "<p>止盈接近单独列为止盈提示，不计入下行风险数。</p>"
        "<p>组合回撤与距历史高点同一口径。</p></div></details>"
    )


def _stock(payload):
    symbol = payload.get("symbol") or ""
    sentences = payload.get("sentences") or {}
    trend = payload.get("trend") or {}
    position = payload.get("position") or {}
    held = position.get("kind") == "held"
    chip = '<span class="chip held">纸面持有</span>' if held else '<span class="chip buy">未持有</span>'
    if position.get("risk_level") == "red":
        chip += '<span class="chip hi">! 重点下行</span>'
    elif position.get("risk_level") == "orange":
        chip += '<span class="chip mid">▲ 下行关注</span>'
    chart = _chart(trend, position)
    returns = (
        f"<p>当日 {format_fraction(trend.get('ret'))} 盘后 {format_fraction(trend.get('post'))}</p>"
        f"<p>近 5 日 {format_fraction(trend.get('ret_5'))} 近 20 日 {format_fraction(trend.get('ret_20'))} "
        f"近 60 日 {format_fraction(trend.get('ret_60'))}</p>"
        f"<p>距 50 日线 {format_points(trend.get('dev50'))}（{money(trend.get('ma50'))}） "
        f"距 200 日线 {format_points(trend.get('price_vs_ma200'))}（{money(trend.get('ma200'))}） "
        f"距一年高点 {format_points(trend.get('drawdown252'))}（{money(trend.get('year_high'))}）</p>"
        f"<p>RSI {_rsi(trend.get('rsi'))} 成交量 {_vol(trend.get('volume_multiple'))}</p>"
    )
    books = _books(payload.get("books"))
    if held:
        position_html = (
            f"<h2>我的仓位</h2><p>{_text(sentences.get('position'))}</p>"
            f"<p>{_text(position.get('holding_kind') or MISSING)}</p>"
            f"<p>{_text(position.get('risk_text') or MISSING)}</p>"
            f"<p>股数 {_shares(position.get('shares'))} 成本 {money(position.get('avg_cost'))} "
            f"→ 现价 {money(position.get('price'))} 盈亏 {format_fraction(position.get('pnl'))}</p>"
            f"{_ruler_box(position.get('ruler') if isinstance(position.get('ruler'), dict) else {}, 620)}"
            f'<div class="rules">{_rules(position.get("levels") or [])}</div>'
            f"<p>下一步 {_text(position.get('next_step') or MISSING)}</p>"
        )
    elif position.get("kind") == "buyable":
        position_html = (
            "<h2>为什么没买</h2>"
            f"<p>{_text(position.get('why_not') or sentences.get('position') or MISSING)}</p>"
            f"<p>回调参考 {money(position.get('ma50'))} 上方参考 {money(position.get('year_high'))}</p>"
        )
    elif position.get("kind") == "blocked":
        position_html = f"<h2>为什么没买</h2><p>主要卡点 {_text(position.get('blocker') or MISSING)}</p>"
    else:
        position_html = f"<h2>我的仓位</h2><p>{_text(MISSING)}</p>"
    news = _stock_news(payload)
    stamps = " ".join(f"{_text(item.get('label'))} {_text(item.get('value'))}" for item in payload.get("stamps") or [])
    return (
        f'<p><a href="/stocks{_query(payload)}">返回我的标的</a></p>'
        f"<h1>{_text(symbol)}</h1>{chip}"
        f'<p class="sub">{_text(payload.get("oneliner"))}</p>'
        f'<div class="card"><h2>走势与位置</h2><p>{_text(sentences.get("trend"))}</p>{chart}{returns}</div>'
        f'<div class="card"><h2>位置与情绪</h2><p>{_text(sentences.get("funds"))}</p>'
        f"<p>{_text(payload.get('short_text') or MISSING)}</p>"
        f"<p>{_text(payload.get('resid_text') or MISSING)}</p>"
        f"<p>{_text(payload.get('sector') or MISSING)} {format_fraction(payload.get('theme_ret'))}</p>"
        f"<p>{books}</p>{_score_bars(payload.get('books'))}</div>"
        f'<div class="card"><h2>新闻与事件</h2><p>{_text(sentences.get("news"))}</p>{news}'
        f"<p>{_text(sentences.get('events'))}</p></div>"
        f'<div class="card"><h2>基本面与估值</h2><p>{_text(sentences.get("valuation"))}</p>'
        f"<p>{_valuation(payload.get('valuation'))}</p><p>{_text(sentences.get('consensus'))}</p>"
        f"{_consensus(payload.get('consensus'))}</div>"
        f'<div class="card">{position_html}</div><p>{stamps}</p>'
    )


def _stock_news(payload):
    blocks = []
    for row in payload.get("events") or []:
        reasons = []
        for item in row.get("reasons") or []:
            stale = item.get("stale_note")
            chip = f' <span class="chip stale">旧闻 {_text(stale)}</span>' if stale else ""
            reasons.append(f"<li>{_text(item.get('text') or MISSING)}{chip}</li>")
        blocks.append(
            '<div class="event open"><div class="h" data-ev><b>'
            f"{_text(row.get('title'))}</b> 状态 {_text(row.get('status'))} 暴露 {_text(row.get('exposure'))}</div>"
            f'<div class="body"><ul class="news">{"".join(reasons)}</ul></div></div>'
        )
    items = []
    for item in payload.get("news") or []:
        items.append(
            f"<li>{_text(item.get('summary'))} · {_text(item.get('source'))} · {_text(item.get('published_beijing'))}"
            ' <span class="chip stale">旧闻</span></li>'
        )
    return "".join(blocks) + f'<ul class="news">{"".join(items)}</ul>'


def _chart(trend, position):
    closes = trend.get("closes") or []
    poly = _polyline(closes)
    overlays = []
    for name, key in (("50 日线", "ma50"), ("200 日线", "ma200")):
        if trend.get(key) is not None:
            overlays.append((name, trend.get(key)))
    if position.get("kind") == "held":
        if position.get("avg_cost") is not None:
            overlays.append(("成本", position.get("avg_cost")))
        spec = position.get("ruler") if isinstance(position.get("ruler"), dict) else {}
        stop = spec.get("stop") if isinstance(spec.get("stop"), dict) else None
        if stop and stop.get("p") is not None:
            overlays.append((stop.get("n") or "止损", stop.get("p")))
    return (
        f'<svg viewBox="0 0 760 220" width="760" height="220" role="img">{poly}{_overlay_lines(closes, overlays)}</svg>'
    )


def _polyline(closes):
    if not closes:
        return ""
    width, height = 760, 220
    low, high = min(closes), max(closes)
    span = high - low or 1
    last = len(closes) - 1
    coords = []
    for index, value in enumerate(closes):
        x = 56 if last == 0 else 56 + index * (width - 68) / last
        y = 14 + (high - float(value)) / span * (height - 38)
        coords.append(f"{x:.1f},{y:.1f}")
    return f'<polyline fill="none" stroke="#1F2A2A" stroke-width="1.8" points="{" ".join(coords)}"/>'


def _overlay_lines(closes, overlays):
    if not closes:
        return ""
    low, high = min(closes), max(closes)
    for _name, price in overlays:
        low = min(low, float(price))
        high = max(high, float(price))
    span = high - low or 1
    lines = []
    for name, price in overlays:
        y = 14 + (high - float(price)) / span * (220 - 38)
        lines.append(
            f'<line x1="56" x2="748" y1="{y:.1f}" y2="{y:.1f}" stroke="#B9B2A4" stroke-dasharray="4 3"/>'
            f'<text x="60" y="{max(12, y - 4):.1f}" font-size="10">{_text(name)} {money(price)}</text>'
        )
    return "".join(lines)


def _mini(closes):
    return _polyline(closes[-20:])


def _score_bars(books):
    if not isinstance(books, dict):
        return ""
    parts = []
    for label, key in (("质量", "quality"), ("成长", "growth"), ("估值", "valuation"), ("择时", "timing")):
        value = books.get(key)
        width = 0 if value is None else max(0, min(100, float(value)))
        parts.append(
            f'<div><div class="small">{label}</div><div class="num">{_score(value)}</div>'
            f'<div class="bar"><i style="width:{width:.1f}%"></i></div></div>'
        )
    return f'<div class="grid g4">{"".join(parts)}</div>'


def _books(books):
    if not isinstance(books, dict) or not books:
        return _text(MISSING)
    return " ".join(
        f"{label}{_score(books.get(key))}"
        for label, key in (("质量", "quality"), ("成长", "growth"), ("估值", "valuation"), ("择时", "timing"))
    )


def _consensus(consensus):
    if not isinstance(consensus, dict):
        return "<p>暂无一致预期（轮询中）</p>"
    lines = []
    for key, label in (("fy1", "FY1"), ("fy2", "FY2")):
        row = consensus.get(key) or {}
        lines.append(
            f"<p>{label} 每股收益 {_eps(row.get('eps'))} 机构 {_count(row.get('count'))} 家 "
            f"前瞻市盈率 {_eps_pe(row.get('forward_pe'))}</p>"
        )
    lines.append(f"<p>快照 {_text(consensus.get('as_of') or MISSING)}</p>")
    return "".join(lines)


def _valuation(view):
    if not isinstance(view, dict):
        return _text(MISSING)
    if view.get("state") == "未估值":
        return _text(short_unvalued_text(view.get("text") or "未估值"))
    pe = view.get("pe_text") or MISSING
    bits = [
        f"市盈率 {_text(pe)}",
        _percentiles(view),
        f"隐含 {format_points(view.get('implied_growth'))}",
        f"营收 {format_points(view.get('rev_cagr_3y'))}",
        f"EPS {format_points(view.get('eps_growth'))}",
    ]
    text = " ".join(bits)
    if view.get("state") == "模型不适用":
        text = f"模型不适用 {text}"
    reason = view.get("implied_reason")
    if reason:
        text = f"{text} {_text(reason)}"
    return text


def _percentiles(view):
    low, mid, high = view.get("pe_p25"), view.get("pe_p50"), view.get("pe_p75")
    if low is not None and low == mid == high:
        return "历史样本不足"
    return f"25分位 {_whole(low)} 50分位 {_whole(mid)} 75分位 {_whole(high)}"


def _header(payload):
    day = _day(payload)
    shown = MISSING if day is None else f"{day.year}.{day.month:02d}.{day.day:02d}"
    dow = "" if day is None else f"周{_WEEK[day.weekday()]}"
    prev_link = _date_link(payload, _near(day, -1), "‹")
    next_link = _date_link(payload, _near(day, 1), "›")
    fresh = MISSING if day is None else f"收盘快照 · 数据截至 {day.month}-{day.day} 16:00 ET"
    return (
        '<header class="top"><div class="top-in"><div class="brand"><b>投资研究工作台</b></div>'
        + _nav(payload)
        + '<div class="datebox"><div class="row">'
        + prev_link
        + f'<span class="d">{_text(shown)}</span><span class="small">{dow}</span>'
        + next_link
        + '</div><div class="fresh"><span>'
        + _text(fresh)
        + '</span><span class="mode"><button data-m="close" class="on">收盘</button>'
        + '<button data-m="intra">盘中</button></span></div></div></div></header>'
    )


def _intra():
    return (
        '<div class="banner info" id="intra-banner"><b>盘中示例</b><span>'
        "盘中每 30 分钟刷新指数、标的和持仓盈亏，免费行情延迟约 16 分钟；"
        "盘中数据只用于看盘和风险高亮，不进入规则 A 的交易决策。此处为状态示例，数值仍为收盘快照。"
        "</span></div>"
    )


def _nav(payload):
    page = "/" if not isinstance(payload, dict) else payload.get("page") or "/"
    links = []
    for href, label, small in NAV:
        mark = ' class="on"' if _active(href, page) else ""
        badge = _badges(payload) if href == "/account" else ""
        links.append(f'<a href="{href}{_query(payload)}"{mark}>{_text(label)}{badge}<small>{_text(small)}</small></a>')
    return '<nav class="nav">' + "".join(links) + "</nav>"


def _badges(payload):
    if "down_red" not in payload and "down_orange" not in payload:
        return ""
    red = int(payload.get("down_red") or 0)
    orange = int(payload.get("down_orange") or 0)
    return f'<span class="badges"><span class="dot hi">{red}</span> <span class="dot mid">{orange}</span></span>'


def _foot(payload):
    links = "".join(f'<a href="{href}">{_text(label)}</a> ' for href, label in DETAILS)
    formulas = "".join(f"<p>{_text(_formula(line))}</p>" for line in payload.get("formulas") or [])
    return f"<footer><p>{_text(payload.get('label') or PAPER_LABEL)}</p><p>详情 {links}</p>{formulas}</footer>"


def _formula(line):
    text = str(line)
    if "目标价" in text or "合理价" in text:
        return "页面只引用已有估值输入。"
    return text


def _document(title, body):
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_text(title)}</title><style>{_STYLE}{_EXTRA}</style></head>"
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


def _date_link(payload, day, label):
    if day is None:
        return f"<span>{label}</span>"
    page = payload.get("page") or "/"
    return f'<a href="{page}?date={day.isoformat()}">{label}</a>'


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
