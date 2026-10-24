"""Server-rendered HTML for the daily pages. The renderer only receives JSON."""

import json
from datetime import timedelta
from html import escape

from inves_cog.ingest.market import NY, trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.web.pages import PAPER_LABEL, VALUATION_LABEL

MEANINGS = {
    "①": "原因未明",
    "②": "已归因·不需要行动",
    "③": "已行动",
    "④": "截止日已结",
    "⑤": "事后确认漏检",
}
COUNT_LABELS = (
    ("anomaly_count", "异常数"),
    ("pool_anomaly_count", "池内异常数"),
    ("wide_anomaly_count", "宽池异常数"),
    ("high_priority_info_count", "高优先级信息数"),
    ("trade_action_count", "交易动作数"),
    ("no_action_count", "决定不动数"),
    ("shadow_divergence_count", "影子分歧数"),
)
NAV = (
    ("/", "市场总览"),
    ("/stocks", "我的标的"),
    ("/account", "纸面账户"),
    ("/trust", "复盘与数据"),
    ("/log", "系统日志"),
    ("/market", "市场"),
    ("/graph", "图谱"),
    ("/settings/data", "数据健康"),
    ("/paper/plan", "盘前计划"),
    ("/paper/portfolio", "纸面账户"),
    ("/paper/universe", "标的池"),
    ("/paper/health", "数据质量"),
    ("/paper/ledger", "纸面流水"),
    ("/review", "复盘"),
)
TITLES = {
    "/": "系统日志",
    "/market": "市场",
    "/linkage/{id}": "联动",
    "/stock/{symbol}": "个股",
    "/graph": "图谱",
    "/settings/data": "数据健康",
    "/paper/plan": "盘前计划",
    "/paper/portfolio": "纸面账户",
    "/paper/universe": "标的池",
    "/paper/stock/{symbol}": "纸面个股",
    "/paper/health": "数据质量",
    "/paper/ledger": "纸面流水",
    "/review": "复盘",
}
# Market and research pages omit these keys. Paper pages still render them.
HIDDEN_ON_RESEARCH = {
    "orders",
    "order",
    "order_id",
    "cancels",
    "positions",
    "position",
    "qty",
    "quantity",
    "shares",
    "fill_price",
    "cash",
    "equity",
    "peak_equity",
    "bear",
    "neutral",
    "bull",
    "holdings",
    "cost",
    "side",
    "notional",
    "notional_est",
    "position_panel",
    "valuation_range",
    "valuation_ranges",
    "tier_usage",
    "tier_budget",
    "portfolio",
}
_RESEARCH = {"/", "/market", "/linkage/{id}", "/stock/{symbol}", "/graph", "/settings/data", "/review"}
_LABELS = {
    "spy_5d_pct": "标普五日涨跌",
    "L1": "第一层",
    "L2": "第二层",
    "L3": "第三层",
    "L4": "第四层",
}
_STYLE = """
body { margin: 0; color: black; background: white; font-family: sans-serif; }
nav a { display: block; color: black; text-decoration: none; }
main { display: block; }
.mark { color: crimson; font-weight: bold; background: yellow; }
form, dl, dt, dd, p { display: block; }
@media (min-width: 60em) { nav a { display: inline-block; } }
"""


def latest_visible_session(clock):
    """Latest US session whose ET next-day 01:00 cutoff has arrived."""
    now = clock.now_utc()
    day = now.astimezone(NY).date()
    for _ in range(14):
        day = day - timedelta(days=1)
        if trading_day(day) and cutoff(day) <= now:
            return day
    raise RuntimeError("no visible trade date")


def render_page(payload):
    """Return an HTML document for one page payload."""
    if not isinstance(payload, dict):
        payload = {}
    page = payload.get("page")
    research = page in _RESEARCH
    parts = []
    if isinstance(page, str) and page.startswith("/paper"):
        parts.append(f"<p>{_text(PAPER_LABEL)}</p><p>{_text(VALUATION_LABEL)}</p>")
    if isinstance(payload.get("summary_oneliner"), str):
        parts.append(f'<p class="summary">{_text(payload["summary_oneliner"])}</p>')
    if isinstance(payload.get("counts"), dict):
        parts.append(f"<section>{_counts(payload['counts'])}</section>")
    if isinstance(payload.get("unhandled"), list):
        rows = "".join(_value(row, research) for row in payload["unhandled"])
        parts.append(f"<section><h2>未处置</h2>{rows}</section>")
    if page in {"/", "/market"}:
        parts.append(_legend())
    parts.append(_value(payload, research))
    title = TITLES.get(page, "每日页面")
    if payload.get("message") == "非交易日":
        title = "非交易日"
    return _document(title, _nav(payload) + _form(payload) + "<main>" + "".join(parts) + "</main>")


def _counts(counts):
    lines = []
    for key, label in COUNT_LABELS:
        if key in counts:
            lines.append(f"<p>{_text(label)} {_value(counts[key], False)}</p>")
    if "status_counts" in counts:
        lines.append(f"<p>各状态数</p>{_value(counts['status_counts'], False)}")
    return "".join(lines)


def _legend():
    items = "".join(f"<li>{_text(mark)} {_text(label)}</li>" for mark, label in MEANINGS.items())
    return f"<section><h2>处置卡</h2><ul>{items}</ul></section>"


def _nav(payload):
    chosen = payload.get("date") if isinstance(payload.get("date"), str) else ""
    query = f"?date={_text(chosen)}" if chosen else ""
    links = "".join(f'<a href="{href}{query}">{_text(label)}</a>' for href, label in NAV)
    return f"<nav>{links}</nav>"


def _form(payload):
    chosen = payload.get("date") if isinstance(payload.get("date"), str) else ""
    value = f' value="{_text(chosen)}"' if chosen else ""
    control = f'<label>交易日<input type="date" name="date"{value}></label>'
    return f'<form method="get">{control}<button type="submit">查看</button></form>'


def _document(title, body):
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{_text(title)}</title><style>{_STYLE}</style></head><body>{body}</body></html>"
    )


def _label(key):
    if key in _LABELS:
        return _LABELS[key]
    if any(character.isdigit() for character in str(key)):
        return "字段"
    return str(key)


def _text(value):
    return escape(str(value), quote=True)


def _value(value, research):
    if isinstance(value, dict):
        return _mapping(value, research)
    if isinstance(value, list):
        rows = "".join(f"<div>{_value(item, research)}</div>" for item in value)
        return rows or "<p>无</p>"
    if isinstance(value, bool):
        return _text("是" if value else "否")
    if value is None:
        return "<p>空</p>"
    if isinstance(value, (int, float)):
        return _text(json.dumps(value, ensure_ascii=False))
    text = value if isinstance(value, str) else str(value)
    if text in MEANINGS:
        return f"{_text(text)} {_text(MEANINGS[text])}"
    return _text(text)


def _mapping(value, research):
    rows = []
    for key, item in value.items():
        if research and key in HIDDEN_ON_RESEARCH:
            continue
        shown = _linked(key, item) if isinstance(item, str) else _value(item, research)
        rows.append(f"<dt>{_text(_label(key))}</dt><dd>{shown}</dd>")
    body = "<dl>" + "".join(rows) + "</dl>"
    if value.get("highlighted") is True:
        return f'<div class="mark">{body}<p>标红</p></div>'
    return body


def _linked(key, item):
    if key == "event_id" and item:
        return f'<a href="/linkage/{_text(item)}">{_text(item)}</a>'
    if key == "symbol" and item:
        return f'<a href="/stock/{_text(item)}">{_text(item)}</a>'
    if item in MEANINGS:
        return f"{_text(item)} {_text(MEANINGS[item])}"
    return _text(item)
