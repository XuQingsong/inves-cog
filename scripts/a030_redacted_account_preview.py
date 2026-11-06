"""UD-A-57: render and mask on the server; export only the verified PNG and safe metadata."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import urllib.request
from html import escape
from html.parser import HTMLParser
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
        elif "隐含" in value or "长期回报大概率偏低" in value:
            value = re.sub(r"[A-Za-z0-9_$%+−.,:/@=-]+", "[已遮盖]", value)
            self.output.append(escape(value))
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
    a = p.parse_args()
    root = a.directory.resolve()
    signal.alarm(55)
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
    assert "<script" not in masked and "data-" not in masked and "href=" not in masked
    note = '<div class="banner">服务器端完全遮盖的生产结构预览；身份、数值及交易内容不导出。新增估值说明保留，数值遮盖。</div>'
    masked = masked.replace("<body>", "<body>" + note)
    html_path, png_path = root / "redacted.html", root / "account-redacted.png"
    html_path.write_text(masked)
    command = [
        "/usr/bin/google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        "--host-resolver-rules=MAP * ~NOTFOUND",
        "--user-data-dir=" + str(root / "browser"),
        "--window-size=1440,7000",
        "--virtual-time-budget=1500",
        "--screenshot=" + str(png_path),
        html_path.as_uri(),
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    timed_out = False
    try:
        process.wait(timeout=22)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    if not png_path.exists() or png_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("redacted PNG was not generated")
    html_path.unlink()
    summary = dict(
        source="production 2026-11-04 account; branch renderer; server-side text/attribute/script redaction",
        authorization="UD-A-57",
        raw_payload_exported=False,
        raw_html_persisted=False,
        redacted_html_exported=False,
        output="account-redacted.png",
        browser_exit=process.returncode,
        browser_exit_timeout=timed_out,
        sha256=hashlib.sha256(png_path.read_bytes()).hexdigest(),
    )
    (root / "redaction-verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
