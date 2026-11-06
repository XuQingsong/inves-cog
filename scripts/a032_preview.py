"""Temporary read-only A-032 preview. Server-side account redaction; no migrations or email."""

import argparse
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--port", type=int, default=18093)
    args = parser.parse_args()
    import inves_cog

    inves_cog.__path__.insert(0, str(args.code / "src/inves_cog"))
    import inves_cog.web

    inves_cog.web.__path__.insert(0, str(args.code / "src/inves_cog/web"))
    import uvicorn
    from starlette.responses import HTMLResponse, JSONResponse

    from inves_cog.clock import SystemClock
    from inves_cog.dataguard.mail import Mailer
    from inves_cog.dataguard.reader import load
    from inves_cog.dataguard.service import connect, scan
    from inves_cog.ingest.settings import read_environment
    from inves_cog.web import api, data_status

    clock = SystemClock()
    now = clock.now_utc()
    values = read_environment("/home/claudeuser/inves-cog/.env")
    _, items = load(args.code / "config/data_expectations.yaml")
    with connect(values) as reader:
        results, errors = scan(reader, items, now, budget=20)
    gaps = [
        dict(
            dataset=item.dataset,
            data_date=day,
            kind=f.kind,
            status="open",
            impact=f.detail["impact"],
            affects_barometer=f.detail.get("affects_barometer", False),
        )
        for item, days in results
        for day, found in days.items()
        for f in found
    ]
    safe = dict(
        available=True,
        fresh=True,
        gaps=gaps,
        detect_only=True,
        mail_status="邮件已配置（预览未发送）" if Mailer(values).configured else "邮件未配置",
        checked_at=now.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M"),
    )
    data_status.payload = lambda _c, _d, _clock: deepcopy(safe)
    original = api.page_brief_market
    allowed = {
        "page",
        "date",
        "title",
        "oneliner",
        "judgment",
        "headings",
        "indexes",
        "advancers",
        "decliners",
        "leaders_down",
        "leaders_up",
        "styles",
        "sector_spread_z",
        "vix",
        "vix_source",
        "put_call",
        "put_call_text",
        "vix3m",
        "vix3m_prev",
        "down_share_5d_pct",
        "spy_drawdown_252_pct",
        "index_closes",
        "freshness",
        "barometer",
        "barometer_today",
        "barometer_intraday",
    }

    def public_market(connection, day, clock):
        full = original(connection, day, clock)
        public = {key: val for key, val in full.items() if key in allowed}
        public["implication"] = "本次截图仅展示公开市场概览；账户与事件明细已在服务器隐藏"
        return public

    api.page_brief_market = public_market
    app = api.create_app(dsn=values["INVES_COG_WEB_DATABASE_URL"], clock=clock, warmup=False)

    @app.get("/__a032_preview")
    def identity():
        return {"head": args.head, "pid": os.getpid(), "mode": "read-only", "check_errors": errors, "gaps": len(gaps)}

    @app.middleware("http")
    async def boundary(request, call_next):
        allowed_paths = {
            "/",
            "/data-status",
            "/barometer",
            "/investor.css",
            "/investor.js",
            "/lightweight-charts.js",
            "/__a032_preview",
        }
        if request.method != "GET" or request.url.path not in allowed_paths:
            return JSONResponse({"detail": "Read-only redacted preview"}, status_code=404)
        response = await call_next(request)
        if "text/html" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator]).decode("utf-8")
        body = re.sub(r'<a href="/account[^\"]*"[^>]*>.*?</a>', "", body, flags=re.S)
        body = re.sub(r"账户下行风险.*?止盈提示.*?项。", "账户信息已隐藏。", body, flags=re.S)
        notice = (
            '<div style="padding:8px 32px;background:#e6f1ec;color:#23705e">'
            "只读预览：守护服务尚未安装，未发送邮件；账户数据已隐藏。</div>"
        )
        body = re.sub(r"(<body\b[^>]*>)", lambda m: m[0] + notice, body, count=1)
        return HTMLResponse(body, status_code=response.status_code)

    (args.code / "preview-summary.json").write_text(
        json.dumps({"head": args.head, "gap_count": len(gaps), "check_errors": errors, "read_only": True})
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
