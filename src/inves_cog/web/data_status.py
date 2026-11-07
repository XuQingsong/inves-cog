"""Format persisted guard results only; never recompute market or trading decisions."""

import re
from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo

from inves_cog.dataguard.mail import KINDS, STATES


def payload(connection, _day, clock):
    unknown = dict(
        available=False, fresh=False, gaps=[], mail_status="邮件状态尚未核实", detect_only=True, checked_at=None
    )
    # A savepoint prevents an unavailable/uninstalled schema from breaking the surrounding page read.
    try:
        with connection.transaction():
            connection.execute("SET LOCAL statement_timeout TO '1000ms'")
            if not connection.execute("SELECT to_regclass('ops.data_gaps') AS name").fetchone()["name"]:
                return unknown
            runtime = connection.execute("SELECT * FROM ops.data_guard_runtime WHERE singleton").fetchone()
            if not runtime:
                return unknown
            gaps = connection.execute(
                "SELECT dataset,data_date,kind,status,detail->>'impact' AS impact,"
                "detail->>'affects_barometer' AS affects_barometer,detail->>'recovery_reason' AS recovery_reason "
                "FROM ops.data_gaps WHERE status<>'resolved' "
                "ORDER BY data_date DESC,dataset LIMIT 100"
            ).fetchall()
            revisions = []
            if connection.execute("SELECT to_regclass('ops.barometer_revisions') AS name").fetchone()["name"]:
                revisions = connection.execute(
                    "SELECT DISTINCT ON (data_date) data_date,revised_at,record FROM ops.barometer_revisions "
                    "ORDER BY data_date DESC,revised_at DESC,input_hash LIMIT 7"
                ).fetchall()
            fresh = timedelta(0) <= clock.now_utc() - runtime["checked_at"] <= timedelta(minutes=20)
            stamp = runtime["checked_at"].astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
            return dict(
                revisions=revisions,
                available=True,
                fresh=fresh,
                gaps=gaps,
                mail_status=runtime["mail_status"],
                detect_only=runtime["detect_only"],
                checked_at=stamp,
            )
    except Exception:
        return unknown


def banner(data, *, barometer=False):
    if not data["available"]:
        message = "数据核查尚未就绪，完整性暂不能确认"
    elif not data["fresh"]:
        message = "数据核查已超过20分钟未更新，完整性暂不能确认"
    elif data["gaps"]:
        if barometer:
            relevant = [
                g
                for g in data["gaps"]
                if g.get("affects_barometer") in {True, "true"} or "晴雨表" in (g.get("impact") or "")
            ]
            if not relevant:
                return ""
            dates = sorted({str(g["data_date"]) for g in relevant})
            message = "该读数受数据缺失影响：" + "、".join(dates)
        else:
            labels = list(dict.fromkeys(g["dataset"] for g in data["gaps"]))
            message = "部分数据缺失：" + "、".join(labels[:4]) + ("等" if len(labels) > 4 else "")
    else:
        return ""
    return (
        '<aside role="status" style="background:#FDF0D8;color:#8A5A00;padding:12px 32px;'
        'border-bottom:1px solid #D08A16;font:14px/1.6 sans-serif">'
        + escape(message)
        + '（<a href="/data-status" style="color:inherit;text-decoration:underline">详见数据状态</a>）</aside>'
    )


def decorate(response, data, *, barometer=False):
    from starlette.responses import HTMLResponse

    notice = banner(data, barometer=barometer)
    if barometer:
        notice += revision_notice(data.get("revisions", []))
    if not notice:
        return response
    body = response.body.decode("utf-8")
    if re.search(r"<body\b[^>]*>", body, re.I):
        body = re.sub(r"(<body\b[^>]*>)", lambda m: m[0] + notice, body, count=1, flags=re.I)
    else:
        body = notice + body
    return HTMLResponse(body, status_code=response.status_code)


def render_status(data):
    if not data["available"]:
        summary = "数据核查尚未就绪，当前完整性尚不能确认。"
    elif not data["fresh"]:
        summary = "数据核查超过20分钟未更新，请核查守护程序。"
    elif data["gaps"]:
        summary = "以下数据仍有缺口。相关读数与判断需结合这些局限查看。"
    else:
        summary = "本轮已检查的数据未发现缺口；尚未到发布时间的数据不计入完整。"
    rows = []
    for r in data["gaps"]:
        cells = [
            r["dataset"],
            str(r["data_date"]),
            KINDS.get(r["kind"], "待核查") + ("；" + r["recovery_reason"] if r.get("recovery_reason") else ""),
            r.get("impact") or "相关数据展示",
            STATES.get(r["status"], "待核查"),
        ]
        rows.append("<tr>" + "".join("<td>" + escape(str(cell)) + "</td>" for cell in cells) + "</tr>")
    mode = "只检测，不自动补数" if data["detect_only"] else "自动补数已开启，异常价格仅告警"
    stamp = data.get("checked_at") or "尚无记录"
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>数据状态</title>'
        '<link rel="stylesheet" href="/investor.css"><style>table{width:100%;border-collapse:collapse;'
        "background:white}th,td{text-align:left;vertical-align:top;padding:14px;border-bottom:1px solid #e7e2d8}"
        ".table-wrap{overflow-x:auto}h1{font-size:28px} .status-meta{color:#4e5958;margin:20px 0}</style></head>"
        '<body><header class="top"><div class="top-in"><a href="/">市场研究</a> / 数据状态</div></header>'
        "<main><h1>数据状态</h1><p>"
        + escape(summary)
        + '</p><div class="status-meta">'
        + escape(mode)
        + " · "
        + escape(data["mail_status"])
        + "<br>最近核查（北京时间）："
        + escape(str(stamp))
        + "</div>"
        '<div class="table-wrap"><table><thead><tr><th>数据</th><th>日期</th><th>问题</th><th>影响</th>'
        "<th>处理状态</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
        + revision_notice(data.get("revisions", []))
        + '<p class="muted">补数后会重新核查。可疑价格不会自动修正。页面仅展示数据状态，不改变交易规则。</p>'
        '<p><a href="/trust">查看可靠性说明</a> · <a href="/">返回市场</a></p></main></body></html>'
    )


def register(app, call):
    from starlette.responses import HTMLResponse

    @app.get("/api/pages/data-status")
    def data_status_api():
        return call(payload, None)

    @app.get("/data-status")
    def data_status_page():
        return HTMLResponse(render_status(call(payload, None)))


def revision_notice(rows):
    if not rows:
        return ""
    parts = []
    for row in rows:
        record = row["record"]
        stamp = row["revised_at"].astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
        quality = "仍有缺失，请结合数据状态查看" if record.get("missing") else "计算输入核查通过"
        line = (
            f"{row['data_date']} · 事后修订：恐慌 {record.get('fear')}，贪婪 {record.get('greed')}；"
            f"修订于 {stamp}（北京时间）；{quality}"
        )
        parts.append("<li>" + escape(line.replace("None", "缺失")) + "</li>")
    return (
        '<aside role="status" style="padding:16px 32px;background:#eef3f1">'
        "<strong>晴雨表事后修订</strong><p>下方图表保留原读数。此处另列补数后的修订结果，"
        "不代表当时已知信息，不用于改写历史交易。</p><ul>" + "".join(parts) + "</ul></aside>"
    )
