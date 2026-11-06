"""UD-A-57 preview: mask inside the server, render screenshots only on the Mac."""

import argparse
import importlib.util
import json
import re
import signal
import sys
import urllib.request
from html import escape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

STRUCTURE = {
    "纸面账户",
    "市场总览",
    "我的标的",
    "复盘与数据",
    "持仓与关键价位",
    "股票 / 持仓类型",
    "成本 → 现价 / 盈亏",
    "适用价位",
    "下一步 / 估值",
    "全部持仓",
    "下行风险",
    "止盈提示",
    "核心仓",
    "观察波段仓",
    "排序",
    "风险优先",
    "盈亏",
    "当日涨跌",
    "总资产",
    "当日损益",
    "距历史高点",
    "现金",
}


class Redactor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output, self.drop, self.in_style = [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "iframe", "object", "svg", "canvas"}:
            self.drop += 1
        if self.drop:
            return
        if tag in {"link", "meta", "img", "input", "video", "audio", "source"}:
            return
        self.in_style = tag == "style" or self.in_style
        classes = next((v for k, v in attrs if k == "class"), "") or ""
        classes = " ".join(
            c
            for c in classes.split()
            if re.fullmatch(r"[a-z][a-z0-9_-]*", c)
            and c
            not in {
                "hi",
                "mid",
                "ok",
                "tp",
                "pos",
                "neg",
                "up",
                "dn",
                "red",
                "green",
                "orange",
            }
        )
        self.output.append("<" + tag + (f' class="{escape(classes)}"' if classes else "") + ">")

    def handle_endtag(self, tag):
        if self.drop:
            if tag in {"script", "iframe", "object", "svg", "canvas"}:
                self.drop -= 1
            return
        if tag == "style":
            self.in_style = False
        if tag not in {"link", "meta", "img", "input", "video", "audio", "source"}:
            self.output.append("</" + tag + ">")

    def handle_data(self, data):
        if self.drop:
            return
        if self.in_style:
            self.output.append(data)
            return
        value = data.strip()
        if not value:
            return
        if value in STRUCTURE:
            self.output.append(escape(value))
        elif any(phrase in value for phrase in ("现价隐含利润约涨到现在的", "隐含天花板", "长期回报大概率偏低")):
            labels = [
                label for label in ("可信", "偏高", "严重透支", "不适用", "周期股", "金融股", "亏损") if label in value
            ]
            safe = "隐含天花板（数值已遮盖）" + ("：" + "、".join(labels) if labels else "")
            if "长期回报大概率偏低" in value:
                safe += "；长期回报大概率偏低（隐含天花板处于严重透支档）"
            self.output.append(escape(safe))
        else:
            self.output.append("已遮盖")


def redact_html(html):
    redactor = Redactor()
    redactor.feed(html)
    return "".join(redactor.output)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--port", type=int, default=18094)
    a = p.parse_args()
    root = a.directory.resolve()
    signal.alarm(50)
    sys.path.insert(0, "/home/claudeuser/inves-cog/src")
    load("inves_cog.web.ceiling", root / "ceiling.py")
    renderer = load("a030_account_renderer", root / "investor_html.py")
    with urllib.request.urlopen("http://127.0.0.1:8080/api/pages/brief/account?date=2026-11-04", timeout=15) as r:
        private = json.load(r)
    if private.get("page") != "/account" or not private.get("holdings"):
        raise ValueError("expected a real non-empty production account payload")
    ceilings = {r["ticker"]: r for r in json.loads((root / "ceilings.json").read_text())["rows"]}
    for holding in private["holdings"]:
        holding.setdefault("valuation", {})["ceiling"] = ceilings.get(holding["ticker"], {})
    # Raw payload and rendered raw HTML remain in memory on this server only.
    masked = redact_html(renderer.render_brief(private))
    del private
    assert "<script" not in masked and not re.search(r"\sdata-[\w-]+=", masked) and "href=" not in masked
    note = (
        '<div class="banner">服务器端完全遮盖的生产结构预览；身份、数值及交易内容不导出。'
        "新增估值说明保留，数值遮盖。</div>"
    )
    masked = masked.replace("<body>", "<body>" + note)

    # Production runs no browser. A loopback preview serves only already-masked HTML.
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/redacted":
                self.send_error(404)
                return
            body = masked.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", a.port), Handler)
    server.timeout = 25
    print(json.dumps({"ready": True, "port": a.port, "redacted_only": True, "browser_on_server": False}), flush=True)
    try:
        server.handle_request()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
