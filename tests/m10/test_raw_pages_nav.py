"""PR raw-pages-nav: main nav keeps only polished pages; raw pages carry a
dev-view banner; legacy raw URLs redirect to their polished counterparts."""

import pytest

from inves_cog.web.html_page import DEV_PAGES, NAV, render_page

pytestmark = pytest.mark.phase1_blocking

_RAW = {
    "/log",
    "/market",
    "/graph",
    "/settings/data",
    "/review",
    "/paper/plan",
    "/paper/portfolio",
    "/paper/universe",
    "/paper/health",
    "/paper/ledger",
}


def _app():
    from fastapi.testclient import TestClient

    from inves_cog.web.api import create_app

    return TestClient(create_app(dsn="postgresql://unused"))


def test_nav_keeps_only_polished_pages():
    hrefs = {href for href, _ in NAV}
    assert hrefs == {"/", "/stocks", "/account", "/trust", "/barometer", "/data-status"}
    assert not hrefs & _RAW
    assert _RAW == {href for href, _ in DEV_PAGES}


def test_raw_page_carries_dev_banner_with_polished_link():
    html = render_page({"page": "/market"})
    assert "开发视图" in html and "不作投资依据" in html
    assert 'href="/"' in html
    stock = render_page({"page": "/stock/{symbol}", "symbol": "NVDA"})
    assert "/s/NVDA" in stock
    assert "/system" in render_page({"page": "/review"})


def test_stock_and_universe_redirect_to_polished_pages():
    client = _app()
    r = client.get("/stock/NVDA?date=2026-11-06", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/s/NVDA?date=2026-11-06"
    r = client.get("/paper/universe", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/stocks"
    r = client.get("/paper/universe?date=2026-11-05", follow_redirects=False)
    assert r.headers["location"] == "/stocks?date=2026-11-05"


def test_system_page_lists_dev_links():
    html = _app().get("/system")
    assert html.status_code == 200
    body = html.text
    assert "开发视图" in body
    for href, _ in DEV_PAGES:
        assert f'href="{href}"' in body
