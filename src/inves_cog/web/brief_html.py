"""HTML for the four investor brief pages. Numbers come from the brief payload."""

from html import escape

from inves_cog.web.brief import (
    MISSING,
    PAPER_LABEL,
    UNTRUSTED,
    format_fraction,
    format_points,
    half_up,
    human_reason,
    short_unvalued_text,
)
from inves_cog.web.pages import CLOSED

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
tr.risk-red, td.risk-red { background: #fde8e8; }
tr.risk-orange, td.risk-orange { background: #fff1dc; }
.bar { background: #efeae0; height: 8px; border-radius: 4px; }
.bar span { display: block; height: 8px; background: #9a6b2f; border-radius: 4px; }
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
    elif isinstance(page, str) and page.startswith("/s/"):
        main = _stock(payload)
    else:
        main = _market(payload)
    title = payload.get("title") or "每日页面"
    return _document(title, _nav(payload) + _form(payload) + "<main>" + main + _foot(payload) + "</main>")


def _market(payload):
    headings = payload.get("headings") or ["市场总览", "资金", "情绪", "今天的大事"]
    indexes = "".join(
        (
            f'<div class="kpi"><span>{_text(row["name"])}</span>'
            f'<b class="{_tone(row.get("ret"))}">{_pct(row.get("ret"))}</b>{_post(row.get("post"))}</div>'
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
    vix_note = ""
    if payload.get("vix") is None:
        vix_gap = '<div class="gap"><b>缺口：</b>VIX 暂缺。</div>'
    elif payload.get("vix_source") == "FRED":
        vix_note = "<span>来源 FRED</span>"
    events = []
    notes = []
    for row in payload.get("events") or []:
        href = f"/linkage/{_text(row['event_id'])}" if row.get("event_id") else "/market"
        z = MISSING if row.get("max_abs_z") is None else f"{row['max_abs_z']:.1f}σ"
        events.append(
            f'<p><span class="pill">{_text(z)}</span> <a href="{href}"><b>{_text(row.get("title"))}</b></a></p>'
        )
        if payload.get("news_fresh"):
            notes.extend(_reason_lines(row))
    if payload.get("news_fresh"):
        reason = "".join(notes) or f"<p>{_text(MISSING)}</p>"
    else:
        reason = f'<div class="gap"><b>{_text(UNTRUSTED)}：</b>当日新闻缺失，原因解释不可用。</div>'
    return (
        f"<h1>{_text(headings[0])}</h1>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p>'
        f'<div class="grid">{indexes}<div class="kpi"><span>涨 / 跌家数</span><b>{breadth}</b></div></div>'
        f"<p><b>对我意味着什么：</b>{_text(payload.get('implication'))}</p>"
        f"<p>{_text(payload.get('risk_note') or MISSING)}</p></div>"
        f'<div class="card"><h2>{_text(headings[1])}</h2>{funds}'
        f"<p>风格：{styles} · 板块分化 {_text(spread_text)}</p>"
        '<div class="gap"><b>缺口：</b>没有真实资金流，目前用板块相对强弱近似。</div></div>'
        f'<div class="card"><h2>{_text(headings[2])}</h2>'
        f'<div class="grid"><div class="kpi"><span>VIX</span><b>{_plain(payload.get("vix"))}</b>{vix_note}</div>'
        f'<div class="kpi"><span>期权看跌/看涨比</span><b>{_text(payload.get("put_call_text") or MISSING)}</b></div>'
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
            f'<td class="num">{_multiple(theme.get("volume_multiple"))}</td>'
            f'<td class="num">{_count(theme.get("held_count"))}</td>'
            f'<td class="num">{_count(theme.get("buyable_count"))}</td>'
            f"<td>{_text(theme.get('line'))}</td>"
            f'<td class="num">{_count(theme.get("news_count"))}</td>'
            f"<td>{_text(theme.get('short_text') or MISSING)}</td></tr>"
        )
        body = "".join(_member_row(row, payload.get("date")) for row in theme.get("members") or [])
        opened = " open" if theme.get("open") else ""
        details.append(
            f'<details class="theme"{opened}><summary>{_text(theme["sector"])} {_pct(theme.get("average"))}</summary>'
            "<table><tr><th>代码</th><th>当日涨跌</th><th>成交量倍数</th><th>RSI</th>"
            "<th>距200日线</th><th>距一年高点</th><th>持有</th><th>可买</th><th>事件</th><th>估值</th>"
            "<th>今日新闻</th><th>空头</th></tr>"
            f"{body}</table></details>"
        )
    table = (
        "<table><tr><th>主题</th><th>平均涨跌</th><th>成交量相对20日</th><th>持有数</th><th>可买数</th>"
        "<th>一句话</th><th>今日新闻</th><th>平均空头占比</th></tr>" + "".join(rows) + "</table>"
    )
    return (
        f"<h1>{_text(headings[0])}</h1>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p></div>'
        f'<div class="card"><h2>{_text(headings[1])}</h2>{table}</div>'
        f'<div class="card"><h2>{_text(headings[2])}</h2>{"".join(details)}</div>'
    )


def _risk_block(payload):
    from inves_cog.web.risk_brief import EMPTY

    lines = payload.get("risk_lines") or []
    if not lines:
        body = f"<p>{_text(EMPTY)}</p>"
    else:
        rows = []
        for row in lines:
            level = row.get("level") if row.get("level") in {"red", "orange"} else "orange"
            rows.append(f'<p class="risk-{level}">{_text(row.get("text"))}</p>')
        body = "".join(rows)
    return f'<div class="card"><h2>风险提示</h2>{body}</div>'


def _risk_card(card):
    themes = []
    for row in card.get("themes") or []:
        share = row.get("share")
        width = MISSING if share is None else f"{half_up(float(share) * 100, 2):.2f}"
        themes.append(
            f"<p>{_text(row.get('sector'))} {_pct(share)}</p>"
            f'<div class="bar"><span style="width:{width}%"></span></div>'
        )
    body = "".join(themes) or f"<p>{_text(MISSING)}</p>"
    return (
        '<div class="card"><h2>组合风险</h2>'
        f"{body}"
        f"<p>距回撤刹车 {_text(card.get('dd8_gap'))}，距更深闸门 {_text(card.get('dd12_gap'))}</p>"
        f"<p>持仓 {_count(card.get('holdings'))} 只，名额 {_count(card.get('slots'))} 只</p>"
        f"<p>现金比例 {_pct(card.get('cash_ratio'))}</p></div>"
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
        level = row.get("risk_level") if row.get("risk_level") in {"red", "orange"} else None
        if row.get("near_disaster"):
            mark = ' class="warn"'
            paint = f' class="risk-{level}"' if level else ""
        elif level:
            mark = f' class="risk-{level}"'
            paint = ""
        else:
            mark = ""
            paint = ""
        near = " 距灾难线过近" if row.get("near_disaster") else ""
        valuation = _valuation(row.get("valuation"))
        tone = _tone(row.get("pnl"))
        pnl_classes = [item for item in ((f"risk-{level}" if paint else None), tone) if item]
        pnl_mark = f' class="{" ".join(pnl_classes)}"'
        holdings.append(
            f'<tr{mark}><td{paint}><a href="{_symbol_href(payload, row["ticker"])}">{_text(row["ticker"])}</a></td>'
            f"<td{paint}>{_price(row.get('avg_cost'))} → {_price(row.get('price'))}</td>"
            f"<td{pnl_mark}>{_pct(row.get('pnl'))}</td>"
            f"<td{paint}>{_price(row.get('take_profit'))}</td><td{paint}>{_price(row.get('ma200'))}</td>"
            f"<td{paint}>{_price(row.get('disaster'))}</td><td{paint}>{_count(row.get('below_days'))}</td>"
            f"<td{paint}>{_text(row.get('next_step'))}{_text(near)}</td><td{paint}>{valuation}</td></tr>"
        )
    closed = []
    for row in payload.get("closed_records") or []:
        closed.append(
            f"<tr><td>{_text(row.get('ticker'))}</td><td>{_text(row.get('trade_date'))}</td>"
            f"<td>{_text(row.get('kind'))}</td><td>{_reason(row.get('reason_zh'))}</td>"
            f"<td>{_text(row.get('source'))}</td></tr>"
        )
    candidates = []
    for row in payload.get("candidates") or []:
        books = row.get("books") or {}
        candidates.append(
            f'<tr><td><a href="{_symbol_href(payload, row["ticker"])}">{_text(row["ticker"])}</a></td>'
            f"<td>{_book(books)}</td><td>{_price(row.get('ma50'))}</td><td>{_price(row.get('year_high'))}</td>"
            f"<td>{_text(row.get('view'))}</td><td>{_valuation(row.get('valuation'))}</td></tr>"
        )
    estimate = payload.get("close_estimate") if isinstance(payload.get("close_estimate"), dict) else None
    if estimate:
        label = f"<small>{_text(estimate.get('label'))}</small>"
        equity_cell = f"{_money(estimate.get('equity'))}{label}"
        day_cell = f"{_money(estimate.get('day_pnl'))}{label}"
    else:
        equity_cell = _money(payload.get("equity"))
        day_cell = _pct(payload.get("day_change"))
    return (
        f"<h1>{_text(headings[0])}</h1><p>{_text(payload.get('label') or PAPER_LABEL)}</p>"
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p>'
        f'<div class="grid"><div class="kpi"><span>总资产</span><b>{equity_cell}</b></div>'
        f'<div class="kpi"><span>当日</span><b>{day_cell}</b></div>'
        f'<div class="kpi"><span>距高点</span><b>{_pct(payload.get("drawdown"))}</b></div>'
        f'<div class="kpi"><span>现金</span><b>{_money(payload.get("cash"))}</b></div></div></div>'
        f"{_risk_block(payload)}{_risk_card(payload.get('risk_card') or {})}"
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
        kind = "bad" if state in {"缺失", "警示", "过期", "未上线/缺失", "模型不适用"} else "ok"
        if state == MISSING:
            kind = "warn"
        extra = ""
        if item.get("item") == "新闻":
            extra = (
                f" 最近入库 {_text(payload.get('news_seen_beijing') or MISSING)}"
                f" 最近 1 个交易日 {_count(payload.get('news_day_count'))} 条"
            )
        elif item.get("detail"):
            extra = f" {_text(item.get('detail'))}"
        rows.append(f'<p class="status {kind}"><b>{_text(item.get("item"))}</b> {_text(state)}{extra}</p>')
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


def _stock(payload):
    headings = payload.get("headings") or ["走势与位置", "资金与情绪", "新闻与事件", "基本面与估值", "我的仓位"]
    sentences = payload.get("sentences") or {}
    trend = payload.get("trend") or {}
    symbol = payload.get("symbol") or ""
    news = (
        "".join(
            f"<p>{_text(item.get('summary'))} · {_text(item.get('source'))} · "
            f"{_text(item.get('published_beijing'))}</p>"
            for item in payload.get("news") or []
        )
        or f"<p>{_text(MISSING)}</p>"
    )
    events = []
    for row in payload.get("events") or []:
        events.append(
            f"<p><b>{_text(row.get('title'))}</b> 状态 {_text(row.get('status'))} 暴露 {_text(row.get('exposure'))}</p>"
        )
        events.extend(_reason_lines(row))
    event_html = "".join(events) or f"<p>{_text(MISSING)}</p>"
    consensus = _consensus_block(payload.get("consensus"))
    stamps = " ".join(f"{_text(item.get('label'))} {_text(item.get('value'))}" for item in payload.get("stamps") or [])
    return (
        f"<h1>{_text(symbol)}</h1>"
        f'<p><a href="/stocks">返回我的标的</a></p>'
        f'<div class="card hero"><p class="lead">{_text(payload.get("oneliner"))}</p></div>'
        f'<div class="card"><h2>{_text(headings[0])}</h2><p>{_text(sentences.get("trend"))}</p>'
        f"<p>当日 {_pct(trend.get('ret'))} 盘后 {_pct(trend.get('post'))}</p>"
        f"<p>近 5 日 {_pct(trend.get('ret_5'))} 近 20 日 {_pct(trend.get('ret_20'))} "
        f"近 60 日 {_pct(trend.get('ret_60'))}</p>"
        f"<p>距 50 日线 {_points(trend.get('dev50'))}（{_price(trend.get('ma50'))}）"
        f" 距 200 日线 {_points(trend.get('price_vs_ma200'))}（{_price(trend.get('ma200'))}）"
        f" 距一年高点 {_points(trend.get('drawdown252'))}（{_price(trend.get('year_high'))}）</p>"
        f"<p>RSI {_whole(trend.get('rsi'))} 成交量倍数 {_multiple(trend.get('volume_multiple'), '倍')}</p>"
        f"{_sparkline(trend.get('closes') or [])}</div>"
        f'<div class="card"><h2>{_text(headings[1])}</h2><p>{_text(sentences.get("funds"))}</p>'
        f"<p>成交量倍数 {_multiple(trend.get('volume_multiple'), '倍')}</p>"
        f"<p>{_text(payload.get('short_text') or MISSING)}</p>"
        f"<p>{_text(payload.get('resid_text') or MISSING)}</p>"
        f"<p>{_text(payload.get('sector') or MISSING)} {_pct(payload.get('theme_ret'))}</p></div>"
        f'<div class="card"><h2>{_text(headings[2])}</h2><p>{_text(sentences.get("news"))}</p>{news}'
        f"<p>{_text(sentences.get('events'))}</p>{event_html}</div>"
        f'<div class="card"><h2>{_text(headings[3])}</h2><p>{_text(sentences.get("valuation"))}</p>'
        f"<p>{_book(payload.get('books'))}</p>"
        f"<p>{_valuation(payload.get('valuation'))}</p>"
        f"<p>{_text(sentences.get('consensus'))}</p>{consensus}</div>"
        f'<div class="card"><h2>{_text(headings[4])}</h2><p>{_text(sentences.get("position"))}</p>'
        f"{_position_block(payload.get('position') or {})}</div>"
        f"<p>{stamps}</p>"
    )


def _consensus_block(consensus):
    if not isinstance(consensus, dict):
        return f"<p>{_text('暂无一致预期（轮询中）')}</p>"
    lines = []
    for key, label in (("fy1", "FY1"), ("fy2", "FY2")):
        row = consensus.get(key) or {}
        lines.append(
            f"<p>{label} 每股收益 {_eps(row.get('eps'))} 机构 {_count(row.get('count'))} 家 "
            f"前瞻市盈率 {_eps_pe(row.get('forward_pe'))}</p>"
        )
    lines.append(f"<p>快照 {_text(consensus.get('as_of') or MISSING)}</p>")
    return "".join(lines)


def _eps(value):
    if value is None:
        return _text(MISSING)
    return _text(f"{half_up(value, 2):.2f}")


def _eps_pe(value):
    if value is None:
        return _text(MISSING)
    return _text(f"{half_up(value, 1):.1f}")


def _position_block(position):
    kind = position.get("kind")
    if kind == "held":
        pending = "、".join(position.get("pending") or []) or MISSING
        risk = f"<p>{_text(position.get('risk_text') or MISSING)}</p>"
        return risk + (
            f"<p>股数 {_count(position.get('shares'))} 成本 {_price(position.get('avg_cost'))}"
            f" → 现价 {_price(position.get('price'))} 盈亏 {_pct(position.get('pnl'))}</p>"
            f"<p>止盈线 {_price(position.get('take_profit'))} 距离 {_pct(position.get('take_profit_gap'))}</p>"
            f"<p>200 日线 {_price(position.get('ma200'))} 距离 {_pct(position.get('ma200_gap'))}</p>"
            f"<p>灾难线 {_price(position.get('disaster'))} 距离 {_pct(position.get('disaster_gap'))}"
            f" 破位天数 {_count(position.get('below_days'))}</p>"
            f"<p>待成交 {_text(pending)} 下一步 {_text(position.get('next_step') or MISSING)}</p>"
        )
    if kind == "buyable":
        return (
            f"<p>回调参考 {_price(position.get('ma50'))} 上方参考 {_price(position.get('year_high'))}</p>"
            f"<p>为什么没买 {_text(position.get('why_not') or MISSING)}</p>"
        )
    if kind == "blocked":
        return f"<p>主要卡点 {_text(position.get('blocker') or MISSING)}</p>"
    return f"<p>{_text(MISSING)}</p>"


def _sparkline(closes):
    if not closes:
        return f"<p>{_text(MISSING)}</p>"
    width, height = 240, 48
    low, high = min(closes), max(closes)
    span = high - low or 1
    last = len(closes) - 1
    coords = []
    for index, value in enumerate(closes):
        x = 0 if last == 0 else index * width / last
        y = height - 4 - (float(value) - low) / span * (height - 8)
        coords.append(f"{x:.1f},{y:.1f}")
    points = " ".join(coords)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">'
        f'<polyline fill="none" stroke="#1a1a1a" stroke-width="1.5" points="{points}"/></svg>'
    )


def _symbol_href(payload, ticker):
    chosen = payload.get("date") if isinstance(payload, dict) and isinstance(payload.get("date"), str) else ""
    query = f"?date={_text(chosen)}" if chosen else ""
    return f"/s/{_text(ticker)}{query}"


def _member_row(row, day=None):
    events = "、".join(row.get("events") or []) or "无"
    held = "持有" if row.get("held") else "未持有"
    if row.get("held"):
        buyable = ""
    elif row.get("entry_pass") is True:
        buyable = "可买"
    elif row.get("entry_pass") is False:
        buyable = "不可买"
    else:
        buyable = MISSING
    return (
        f'<tr><td><a href="{_symbol_href({"date": day}, row["ticker"])}">{_text(row["ticker"])}</a></td>'
        f'<td class="{_tone(row.get("ret"))}">{_pct(row.get("ret"))}</td>'
        f"<td>{_multiple(row.get('volume_multiple'), '×')}</td><td>{_whole(row.get('rsi'))}</td>"
        f"<td>{_points(row.get('price_vs_ma200'))}</td><td>{_points(row.get('drawdown252'))}</td>"
        f"<td>{_text(held)}</td><td>{_text(buyable)}</td><td>{_text(events)}</td>"
        f"<td>{_valuation(row.get('valuation'))}</td><td>{_news_cell(row)}</td>"
        f"<td>{_text(row.get('short_text') or MISSING)}</td></tr>"
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


def _reason_lines(row):
    reasons = row.get("reasons") or []
    if not reasons and (row.get("explanation") or row.get("cited_at")):
        reasons = [{"text": row.get("explanation"), "cited_at": row.get("cited_at"), "stale_note": None}]
    lines = []
    for item in reasons:
        stale = item.get("stale_note")
        extra = f" {_text(stale)}" if stale else ""
        lines.append(
            f"<p>{_text(item.get('text') or MISSING)} "
            f"<span>引用时间 {_text(item.get('cited_at') or MISSING)}</span>{extra}</p>"
        )
    return lines


def _news_cell(row):
    count = row.get("news_count")
    if not count:
        return _text(0 if count == 0 else MISSING)
    lines = []
    for item in row.get("news") or []:
        summary = _text(item.get("summary"))
        source = _text(item.get("source"))
        when = _text(item.get("published_beijing"))
        lines.append(f"<p>{summary} · {source} · {when}</p>")
    return f"<details><summary>{_text(count)}</summary>{''.join(lines)}</details>"


def _percentiles(view):
    low, mid, high = view.get("pe_p25"), view.get("pe_p50"), view.get("pe_p75")
    if low is not None and low == mid == high:
        return "历史样本不足"
    return f"25分位 {_whole(low)} 50分位 {_whole(mid)} 75分位 {_whole(high)}"


def _valuation(view):
    if not isinstance(view, dict):
        return _text(MISSING)
    if view.get("state") == "未估值":
        return _text(short_unvalued_text(view.get("text") or "未估值"))
    bits = [
        f"市盈率 {_pe(view.get('pe'))}",
        _percentiles(view),
        f"隐含 {_points(view.get('implied_growth'))}",
        f"营收 {_points(view.get('rev_cagr_3y'))}",
        f"EPS {_points(view.get('eps_growth'))}",
    ]
    text = " ".join(bits)
    if view.get("state") == "模型不适用":
        text = f"模型不适用 {text}"
    if view.get("implied_reason"):
        text = f"{text} {_text(view['implied_reason'])}"
    return text


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
    links = []
    chosen = payload.get("date") if isinstance(payload, dict) and isinstance(payload.get("date"), str) else ""
    query = f"?date={_text(chosen)}" if chosen else ""
    for href, label, small in NAV:
        mark = ' class="on"' if href == page else ""
        links.append(f'<a href="{href}{query}"{mark}>{_text(label)}<small>{_text(small)}</small></a>')
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
    return _text(format_fraction(value))


def _points(value):
    return _text(format_points(value))


def _post(value):
    if value is None:
        return ""
    return f"<small>盘后 {_pct(value)}</small>"


def _money(value):
    if value is None:
        return _text(MISSING)
    amount = int(half_up(value, 0))
    return _text(f"${amount:,}")


def _price(value):
    if value is None:
        return _text(MISSING)
    number = float(value)
    if abs(number) >= 100:
        shown = f"{int(half_up(number, 0)):,}"
    else:
        shown = f"{half_up(number, 2):,}"
    return _text(f"${shown}")


def _multiple(value, suffix="倍"):
    if value is None:
        return _text(MISSING)
    return _text(f"{half_up(value, 1)}{suffix}")


def _whole(value):
    if value is None:
        return _text(MISSING)
    return _text(str(int(half_up(value, 0))))


def _pe(value):
    if value is None:
        return _text(MISSING)
    return _text(str(half_up(value, 1)))


def _reason(value):
    if not value:
        return _text(MISSING)
    return _text(human_reason(value) or MISSING)


def _plain(value):
    if value is None:
        return _text(MISSING)
    if isinstance(value, bool):
        return _text("是" if value else "否")
    if isinstance(value, int) and not isinstance(value, bool):
        return _text(value)
    if isinstance(value, float):
        if value.is_integer():
            return _text(str(int(value)))
        return _text(f"{value:.2f}".rstrip("0").rstrip("."))
    return _text(value)


def _count(value):
    if value is None:
        return _text(MISSING)
    return _text(value)


def _tone(value):
    if value is None or value == 0:
        return "muted"
    return "up" if value > 0 else "down"
