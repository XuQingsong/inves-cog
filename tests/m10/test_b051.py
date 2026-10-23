"""B-051 HTML pages render the page JSON and add no numbers of their own."""

import inspect
import json
import re
from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inves_cog.clock import FrozenClock
from inves_cog.web import html_page
from inves_cog.web.html_page import latest_visible_session, render_page
from inves_cog.web.pages import (
    COMPLETENESS_MISSING,
    MISSING,
    PAPER_LABEL,
    STALE,
    UNCONNECTED,
    VALUATION_LABEL,
)
from inves_cog.web.public import create_app
from tests.m10.test_b048 import AFTER, BEFORE, DAY, DAY2, DEADLINE, FORBIDDEN_FIELDS

pytestmark = pytest.mark.phase1_blocking

CLOSED_DAY = date(2031, 4, 19)
PAIRS = (
    ("/", "/api/pages/home"),
    ("/market", "/api/pages/market"),
    ("/linkage/b048-e2", "/api/pages/linkage/b048-e2"),
    ("/stock/NVDA", "/api/pages/stock/NVDA"),
    ("/graph", "/api/pages/graph"),
    ("/settings/data", "/api/pages/settings/data"),
    ("/paper/plan", "/api/pages/paper/plan"),
    ("/paper/portfolio", "/api/pages/paper/portfolio"),
    ("/paper/universe", "/api/pages/paper/universe"),
    ("/paper/stock/NVDA", "/api/pages/paper/stock/NVDA"),
    ("/paper/health", "/api/pages/paper/health"),
    ("/paper/ledger", "/api/pages/paper/ledger"),
    ("/review", "/api/pages/review"),
)
RESEARCH = ("/", "/market", "/linkage/b048-e2", "/stock/NVDA", "/graph", "/settings/data", "/review")
PAPER = tuple(path for path, _ in PAIRS if path.startswith("/paper"))
COUNT_LABELS = ("异常数", "各状态数", "高优先级信息数", "交易动作数", "决定不动数", "影子分歧数")
MEANINGS = ("原因未明", "已归因·不需要行动", "已行动", "截止日已结", "事后确认漏检")
FIELD_LABELS = {
    "orders": "订单",
    "order": "订单",
    "order_id": "订单编号",
    "cancels": "撤单",
    "positions": "仓位",
    "position": "仓位",
    "qty": "数量",
    "quantity": "数量",
    "shares": "股数",
    "fill_price": "成交价",
    "cash": "现金",
    "equity": "权益",
    "peak_equity": "权益高点",
    "bear": "看空",
    "neutral": "中性",
    "bull": "看多",
    "holdings": "持仓",
    "cost": "成本",
    "side": "买卖方向",
    "notional": "名义金额",
    "notional_est": "名义金额估计",
    "position_panel": "仓位面板",
    "valuation_range": "估值区间",
    "valuation_ranges": "估值区间",
    "tier_usage": "档位占用",
    "tier_budget": "档位预算",
    "portfolio": "组合",
}
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z0-9_]+")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"style", "script"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _visible(html):
    parser = _Text()
    parser.feed(html)
    text = "".join(parser.parts)
    for phrase in (PAPER_LABEL, VALUATION_LABEL):
        text = text.replace(phrase, "")
    return text


def _numbers_in(text):
    return {Decimal(match) for match in _NUMBER.findall(text)}


def _json_numbers(value, found):
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        found.update(_numbers_in(json.dumps(value)))
        return
    if isinstance(value, str):
        found.update(_numbers_in(value))
        return
    if isinstance(value, dict):
        for item in value.values():
            _json_numbers(item, found)
    elif isinstance(value, list):
        for item in value:
            _json_numbers(item, found)


@pytest.fixture(scope="module")
def pages():
    from tests.m10.test_b048 import pages as opened

    yield from opened.__wrapped__()


def _app(pages, clock=AFTER, monotonic=None):
    return create_app(dsn=pages["dsn"], clock=clock, monotonic=monotonic)


def test_render_page_takes_only_the_payload():
    assert list(inspect.signature(render_page).parameters) == ["payload"]
    source = Path(html_page.__file__).read_text()
    assert "connection" not in source
    assert "open_reader" not in source
    assert "psycopg" not in source


def test_rendered_numbers_are_already_in_the_payload():
    payload = {
        "page": "/",
        "date": "2031-04-17",
        "summary_oneliner": "今日异常 2 个，详见下方",
        "counts": {
            "anomaly_count": 2,
            "status_counts": {"已发现": 2},
            "high_priority_info_count": 0,
            "trade_action_count": 1,
            "no_action_count": 3,
            "shadow_divergence_count": 4,
        },
        "unhandled": [{"anomaly_id": "b048-a1", "disposition": "①", "highlighted": True}],
    }
    html = render_page(payload)
    found = set()
    _json_numbers(payload, found)
    assert _numbers_in(_visible(html)) <= found
    assert "标红" in html and "原因未明" in html


def test_dynamic_text_is_escaped():
    payload = {"page": "/market", "date": "2031-04-17", "note": '<script>alert("x")</script> &'}
    html = render_page(payload)
    assert "<script>" not in html
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in html
    assert "&amp;" in html
    assert "http://" not in html and "https://" not in html


def test_default_date_is_the_latest_session_whose_cutoff_has_arrived():
    assert latest_visible_session(AFTER) == DAY
    assert latest_visible_session(FrozenClock(DEADLINE - timedelta(minutes=1))) == date(2031, 4, 16)


def test_html_paths_render_the_same_numbers(pages):
    with TestClient(_app(pages)) as client:
        for path, api_path in PAIRS:
            page = client.get(path, params={"date": DAY.isoformat()})
            body = client.get(api_path, params={"date": DAY.isoformat()})
            assert page.status_code == 200, path
            assert page.headers["content-type"] == "text/html; charset=utf-8"
            assert body.status_code == 200, api_path
            assert "http://" not in page.text and "https://" not in page.text
            found = set()
            _json_numbers(body.json(), found)
            extra = _numbers_in(_visible(page.text)) - found
            assert not extra, (path, sorted(extra))


def test_default_and_closed_dates(pages):
    with TestClient(_app(pages)) as client:
        opened = client.get("/")
        assert opened.status_code == 200
        assert "b048-a1" in opened.text
        assert "非交易日" not in _visible(opened.text)
    with TestClient(_app(pages, clock=FrozenClock(DEADLINE - timedelta(minutes=1)))) as client:
        earlier = client.get("/")
        assert earlier.status_code == 200
        assert "b048-a1" not in earlier.text
    with TestClient(_app(pages)) as client:
        closed = client.get("/", params={"date": CLOSED_DAY.isoformat()})
        assert closed.status_code == 200
        assert "非交易日" in closed.text
        assert "b048-a1" not in closed.text


def test_home_is_readable_and_highlights_unhandled(pages):
    with TestClient(_app(pages, clock=BEFORE)) as client:
        early = client.get("/", params={"date": DAY.isoformat()})
    with TestClient(_app(pages)) as client:
        late = client.get("/", params={"date": DAY.isoformat()})
    early_text = _visible(early.text)
    late_text = _visible(late.text)
    assert "b048-a1" in early_text and "标红" not in early_text
    assert "标红" in late_text
    with TestClient(_app(pages)) as client:
        home = client.get("/api/pages/home", params={"date": DAY.isoformat()}).json()
    assert late_text.index(home["summary_oneliner"]) < late_text.index("异常数") < late_text.index("未处置")
    for label in COUNT_LABELS:
        assert label in late_text
    for meaning in MEANINGS:
        assert meaning in late_text
    assert STALE in late_text


def test_passthrough_phrases_and_paper_labels(pages):
    with TestClient(_app(pages)) as client:
        market = client.get("/market", params={"date": DAY.isoformat()})
        settings = client.get("/settings/data", params={"date": DAY.isoformat()})
        plan = client.get("/paper/plan", params={"date": DAY2.isoformat()})
        assert market.status_code == settings.status_code == plan.status_code == 200
        assert MISSING in market.text
        assert UNCONNECTED in settings.text
        assert COMPLETENESS_MISSING in plan.text
        for path in PAPER:
            page = client.get(path, params={"date": DAY.isoformat()})
            assert PAPER_LABEL in page.text and VALUATION_LABEL in page.text


def test_research_html_hides_trading_fields(pages):
    with TestClient(_app(pages)) as client:
        for path in RESEARCH:
            page = client.get(path, params={"date": DAY.isoformat()})
            words = set(_WORD.findall(_visible(page.text)))
            assert not (words & FORBIDDEN_FIELDS), (path, sorted(words & FORBIDDEN_FIELDS))
            for label in set(FIELD_LABELS.values()):
                assert label not in page.text, (path, label)


def test_new_paths_reject_other_methods_and_unknown_urls():
    with TestClient(create_app(dsn="postgresql://unused/db")) as client:
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)("/market")
            assert response.status_code == 405
            assert response.headers["allow"] == "GET"
        for path in ("/nope", "/paper", "/linkage", "/paper/stock/", "/api/secret"):
            assert client.get(path).status_code == 404


def test_html_rate_limit_and_redacted_errors(pages, monkeypatch):
    now = [0.0]
    limited = _app(pages, monotonic=lambda: now[0])
    with TestClient(limited, client=("203.0.113.51", 51)) as client:
        for _ in range(60):
            assert client.get("/graph", params={"date": DAY.isoformat()}).status_code == 200
        blocked = client.get("/graph", params={"date": DAY.isoformat()})
        assert blocked.status_code == 429
        assert blocked.json()["detail"] == "请求过于频繁"
        now[0] = 60
        assert client.get("/graph", params={"date": DAY.isoformat()}).status_code == 200

    def boom(*args, **kwargs):
        raise RuntimeError("postgresql://secret traceback")

    monkeypatch.setattr("inves_cog.web.api.page_graph", boom)
    with TestClient(_app(pages)) as client:
        failed = client.get("/graph", params={"date": DAY.isoformat()})
    assert failed.status_code == 503
    assert failed.json() == {"detail": "页面暂不可用"}
    assert "postgresql" not in failed.text and "secret" not in failed.text and "traceback" not in failed.text
