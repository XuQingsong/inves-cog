"""HTML for the four investor brief pages. Numbers come from the brief payload."""

from html import escape

from inves_cog.web.brief import MISSING, PAPER_LABEL, UNTRUSTED
from inves_cog.web.pages import CLOSED

NAV = (
    ("/", "市场总览", "大环境怎么样"),
    ("/stocks", "我的标的", "只各自怎样"),
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
_STYLE = """
body { margin: 0; color: #1a1a1a; background: #f6f4ef; font-family: sans-serif; }
.wrap { max-width: 980px; margin: 0 auto; padding: 16px; }
nav a { display: inline-block; margin-right: 12px; color: inherit; }
nav a.on { font-weight: bold; }
h1, h2 { font-weight: 650; }
.card { background: white; border-radius: 12px; padding: 14px 16px; margin: 12px 0; }
.hero { border: 1px solid #e4dcc8; }
.gap { border: 1px dashed #e67e22; padding: 8px; margin-top: 8px; }
.down { color: #b00020; }
.up { color: #0a7a32; }
.muted, .missing { color: #777; }
.warn { color: #b00020; font-weight: bold; }
table { width: 100%; border-collapse: collapse; }
td, th { text-align: left; padding: 4px 6px; vertical-align: top; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
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
    else:
        main = _market(payload)
    title = payload.get("title") or "每日页面"
    return _document(title, _nav(payload) + _form(payload) + "<main>" + main + _foot(payload) + "</main>")


def _market(payload):
    headings = payload.get("headings") or ["市场总览", "资金", "情绪", "今天的大事"]
    indexes = "".join(
        (
            f'<div class="kpi"><span>{_text(row["name"])}</span>'
            f'<b class="{_tone(row.get("ret"))}">{_pct(row.get("ret"))}</b></div>'
        )
        for row in payload.get("indexes") or []
    )
    breadth = f"{_count(payload.get('advancers'))} / {_count(payload.get('decliners'))}"
    funds = _pairs(payload.get("leaders_down") or [], payload.get("leaders_up") or [])
    styles = " · ".join(
        f'{_text(row["name"])} <span class="{_tone(row.get("ret"))}">{_pct(row.get("ret"))}</span>'
        for row in payload.get("styles") or []
    )
    spread = payload.get("sector_spread_z")
    spread_text = MISSING if spread is None else f"{spread:.1f}σ"
    vix_gap = ""
    if payload.get("vix") is None:
        vix_gap = '<div class="gap"><b>缺口：</b>VIX 暂缺。</div>'
    events = []
    for row in payload.get("events") or []:
        href = f"/linkage/{_text(row['event_id'])}" if row.get("event_id") else "/market"
        z = MISSING if row.get("max_abs_z") is None else f"{row['max_abs_z']:.1f}σ"
        events.append(
            f'<p><span class="pill">{_text(z)}</span> <a href="{href}"><b>{_text(row.get("title"))}</b></a></p>'
        )
    if payload.get("news_fresh"):
        notes = []
        for row in payload.get("events") or []:
            if row.get("explanation") or row.get("cited_at"):
                notes.append(
                    f"<p>{_text(row.get('explanation') or MISSING)} "
                    f"<span>引用时间 {_text(row.get('cited_at') or MISSING)}</span></p>"
                )
        reason = "".join(notes) or f"<p>{_text(MISSING)}</p>"
    else:
        reason = f'<div class="gap"><b>{_text(UNTRUSTED)}：</b>当日新闻缺失，原因解释不可用。</div>'
    return (
        f"<h1>{_text(headings[0])}</h1>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p>'
        f'<div class="grid">{indexes}<div class="kpi"><span>涨 / 跌家数</span><b>{breadth}</b></div></div>'
        f"<p><b>对我意味着什么：</b>{_text(payload.get('implication'))}</p></div>"
        f'<div class="card"><h2>{_text(headings[1])}</h2>{funds}'
        f"<p>风格：{styles} · 板块分化 {_text(spread_text)}</p>"
        '<div class="gap"><b>缺口：</b>没有真实资金流，目前用板块相对强弱近似。</div></div>'
        f'<div class="card"><h2>{_text(headings[2])}</h2>'
        f'<div class="grid"><div class="kpi"><span>VIX</span><b>{_plain(payload.get("vix"))}</b></div>'
        f'<div class="kpi"><span>3 个月 VIX</span><b>{_plain(payload.get("vix3m"))}</b>'
        f"<span>前日 {_plain(payload.get('vix3m_prev'))}</span></div>"
        f'<div class="kpi"><span>近 5 日下跌股占比</span><b>{_points(payload.get("down_share_5d_pct"))}</b></div>'
        f'<div class="kpi"><span>标普距一年高点</span><b>{_points(payload.get("spy_drawdown_252_pct"))}</b></div></div>'
        f"{vix_gap}</div>"
        f'<div class="card"><h2>{_text(headings[3])}</h2>{"".join(events)}{reason}</div>'
    )


def _stocks(payload):
    headings = payload.get("headings") or ["我的标的", "主题一览（按今日表现排序）", "逐只明细"]
    rows = []
    details = []
    for theme in payload.get("themes") or []:
        rows.append(
            "<tr>"
            f"<td>{_text(theme['sector'])}</td>"
            f'<td class="num {_tone(theme.get("average"))}">{_pct(theme.get("average"))}</td>'
            f'<td class="num">{_plain(theme.get("volume_multiple"))}</td>'
            f'<td class="num">{_count(theme.get("held_count"))}</td>'
            f'<td class="num">{_count(theme.get("buyable_count"))}</td>'
            f"<td>{_text(theme.get('line'))}</td></tr>"
        )
        body = "".join(_member_row(row) for row in theme.get("members") or [])
        opened = " open" if theme.get("open") else ""
        details.append(
            f'<details class="theme"{opened}><summary>{_text(theme["sector"])} {_pct(theme.get("average"))}</summary>'
            "<table><tr><th>代码</th><th>当日涨跌</th><th>成交量倍数</th><th>RSI</th>"
            f"<th>距200日线</th><th>距一年高点</th><th>持有</th><th>可买</th><th>事件</th></tr>{body}</table></details>"
        )
    table = (
        "<table><tr><th>主题</th><th>平均涨跌</th><th>成交量相对20日</th><th>持有数</th><th>可买数</th><th>一句话</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return (
        f"<h1>{_text(headings[0])}</h1>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p></div>'
        f'<div class="card"><h2>{_text(headings[1])}</h2>{table}</div>'
        f'<div class="card"><h2>{_text(headings[2])}</h2>{"".join(details)}</div>'
    )


def _account(payload):
    headings = payload.get("headings") or [
        "纸面账户",
        "持仓与关键价位",
        "已止盈 / 止损 / 清仓",
        "待选：符合买入条件但还没买的",
    ]
    holdings = []
    for row in payload.get("holdings") or []:
        mark = ' class="warn"' if row.get("near_disaster") else ""
        near = " 距灾难线过近" if row.get("near_disaster") else ""
        valuation = _valuation(row.get("valuation"))
        holdings.append(
            f'<tr{mark}><td><a href="/paper/stock/{_text(row["ticker"])}">{_text(row["ticker"])}</a></td>'
            f"<td>{_plain(row.get('avg_cost'))} → {_plain(row.get('price'))}</td>"
            f'<td class="{_tone(row.get("pnl"))}">{_pct(row.get("pnl"))}</td>'
            f"<td>{_plain(row.get('take_profit'))}</td><td>{_plain(row.get('ma200'))}</td>"
            f"<td>{_plain(row.get('disaster'))}</td><td>{_count(row.get('below_days'))}</td>"
            f"<td>{_text(row.get('next_step'))}{_text(near)}</td><td>{valuation}</td></tr>"
        )
    closed = []
    for row in payload.get("closed_records") or []:
        closed.append(
            f"<tr><td>{_text(row.get('ticker'))}</td><td>{_text(row.get('trade_date'))}</td>"
            f"<td>{_text(row.get('kind'))}</td><td>{_text(row.get('reason_zh') or MISSING)}</td>"
            f"<td>{_text(row.get('source'))}</td></tr>"
        )
    candidates = []
    for row in payload.get("candidates") or []:
        books = row.get("books") or {}
        candidates.append(
            f'<tr><td><a href="/stock/{_text(row["ticker"])}">{_text(row["ticker"])}</a></td>'
            f"<td>{_book(books)}</td><td>{_plain(row.get('ma50'))}</td><td>{_plain(row.get('year_high'))}</td>"
            f"<td>{_text(row.get('view'))}</td><td>{_valuation(row.get('valuation'))}</td></tr>"
        )
    return (
        f"<h1>{_text(headings[0])}</h1><p>{_text(payload.get('label') or PAPER_LABEL)}</p>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p>'
        f'<div class="grid"><div class="kpi"><span>总资产</span><b>{_plain(payload.get("equity"))}</b></div>'
        f'<div class="kpi"><span>当日</span><b>{_pct(payload.get("day_change"))}</b></div>'
        f'<div class="kpi"><span>距高点</span><b>{_pct(payload.get("drawdown"))}</b></div>'
        f'<div class="kpi"><span>现金</span><b>{_plain(payload.get("cash"))}</b></div></div></div>'
        f'<div class="card"><h2>{_text(headings[1])}</h2><table><tr><th>代码</th><th>成本→现价</th><th>盈亏</th>'
        f"<th>止盈线</th><th>200日线</th><th>灾难止损线</th><th>破位天数</th><th>下一步</th><th>估值</th></tr>"
        f"{''.join(holdings) or '<tr><td>暂缺</td></tr>'}</table></div>"
        f'<div class="card"><h2>{_text(headings[2])}</h2><table><tr><th>代码</th><th>日期</th><th>类型</th>'
        f"<th>原因</th><th>来源</th></tr>{''.join(closed) or '<tr><td>暂缺</td></tr>'}</table></div>"
        f'<div class="card"><h2>{_text(headings[3])}</h2><table><tr><th>代码</th><th>四本账</th><th>50日线</th>'
        "<th>一年高点</th><th>怎么看</th><th>估值</th></tr>"
        f"{''.join(candidates) or '<tr><td>暂缺</td></tr>'}</table></div>"
    )


def _trust(payload):
    headings = payload.get("headings") or ["复盘与数据", "数据状态", "系统之前说的对不对（复盘）"]
    rows = []
    for item in payload.get("statuses") or []:
        state = item.get("state")
        kind = "bad" if state in {"缺失", "警示", "未上线/缺失", "模型不适用"} else "ok"
        if state == MISSING:
            kind = "warn"
        rows.append(f'<p class="status {kind}"><b>{_text(item.get("item"))}</b> {_text(state)}</p>')
    if payload.get("labels"):
        review = "".join(
            f"<p>{_text(row.get('case_id'))} {_text(row.get('horizon'))} {_text(row.get('as_of'))} "
            f"{_text(row.get('labels'))} {_text(row.get('reason') or '')}</p>"
            for row in payload["labels"]
        )
    else:
        review = f'<div class="gap"><b>缺口：</b>{_text(payload.get("review_gap") or MISSING)}</div>'
    return (
        f"<h1>{_text(headings[0])}</h1>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p></div>'
        f'<div class="card"><h2>{_text(headings[1])}</h2>{"".join(rows)}</div>'
        f'<div class="card"><h2>{_text(headings[2])}</h2>{review}</div>'
    )


def _member_row(row):
    events = "、".join(row.get("events") or []) or "无"
    held = "持有" if row.get("held") else "未持有"
    if row.get("entry_pass") is True:
        buyable = "可买"
    elif row.get("entry_pass") is False:
        buyable = "不可买"
    else:
        buyable = MISSING
    return (
        f'<tr><td><a href="/stock/{_text(row["ticker"])}">{_text(row["ticker"])}</a></td>'
        f'<td class="{_tone(row.get("ret"))}">{_pct(row.get("ret"))}</td>'
        f"<td>{_plain(row.get('volume_multiple'))}</td><td>{_plain(row.get('rsi'))}</td>"
        f"<td>{_points(row.get('price_vs_ma200'))}</td><td>{_points(row.get('drawdown252'))}</td>"
        f"<td>{_text(held)}</td><td>{_text(buyable)}</td><td>{_text(events)}</td></tr>"
    )


def _pairs(down, up):
    width = max(len(down), len(up))
    if not width:
        return f"<p>{_text(MISSING)}</p>"
    rows = ["<tr><th>流出（领跌）</th><th>涨跌</th><th>流入（领涨）</th><th>涨跌</th></tr>"]
    for index in range(width):
        left = down[index] if index < len(down) else None
        right = up[index] if index < len(up) else None
        rows.append("<tr>" + _side(left) + _side(right) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def _side(row):
    name = MISSING if row is None else _text(row["name"])
    ret = None if row is None else row.get("ret")
    return f'<td>{name}</td><td class="{_tone(ret)}">{_pct(ret)}</td>'


def _valuation(view):
    if not isinstance(view, dict):
        return _text(MISSING)
    if view.get("neutral") is None:
        return _text(view.get("status") or MISSING)
    return _text(view.get("neutral"))


def _book(books):
    if not books:
        return _text(MISSING)
    parts = [
        f"{name}{_plain(books.get(key))}"
        for name, key in (("质", "quality"), ("增", "growth"), ("估", "valuation"), ("时", "timing"))
    ]
    return " ".join(parts)


def _nav(payload):
    page = "/" if not isinstance(payload, dict) else payload.get("page") or "/"
    count = payload.get("pool_count") if isinstance(payload, dict) else None
    links = []
    chosen = payload.get("date") if isinstance(payload, dict) and isinstance(payload.get("date"), str) else ""
    query = f"?date={_text(chosen)}" if chosen else ""
    for href, label, small in NAV:
        mark = ' class="on"' if href == page else ""
        if href == "/stocks":
            hint = f"{_count(count)} {small}"
        else:
            hint = small
        links.append(f'<a href="{href}{query}"{mark}>{_text(label)}<small>{_text(hint)}</small></a>')
    return "<nav>" + "".join(links) + "</nav>"


def _form(payload):
    chosen = payload.get("date") if isinstance(payload, dict) and isinstance(payload.get("date"), str) else ""
    value = f' value="{_text(chosen)}"' if chosen else ""
    return (
        f'<form method="get"><label>交易日<input type="date" name="date"{value}></label>'
        '<button type="submit">查看</button></form>'
    )


def _foot(payload):
    links = "".join(f'<a href="{href}">{_text(label)}</a> ' for href, label in DETAILS)
    formulas = "".join(f"<p>{_text(line)}</p>" for line in payload.get("formulas") or [])
    return f"<footer><p>{_text(PAPER_LABEL)}</p><p>详情 {links}</p>{formulas}</footer>"


def _document(title, body):
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>{_text(title)}</title><style>{_STYLE}</style></head><body><div class="wrap">{body}</div></body></html>'
    )


def _text(value):
    return escape(str(value), quote=True)


def _pct(value):
    if value is None:
        return _text(MISSING)
    return _text(f"{value * 100:.2f}%")


def _points(value):
    if value is None:
        return _text(MISSING)
    return _text(f"{value:.2f}%")


def _plain(value):
    if value is None:
        return _text(MISSING)
    if isinstance(value, bool):
        return _text("是" if value else "否")
    if isinstance(value, int) and not isinstance(value, bool):
        return _text(value)
    if isinstance(value, float):
        return _text(f"{value:.4f}".rstrip("0").rstrip("."))
    return _text(value)


def _count(value):
    if value is None:
        return _text(MISSING)
    return _text(value)


def _tone(value):
    if value is None or value == 0:
        return "muted"
    return "up" if value > 0 else "down"
