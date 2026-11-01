"""FastAPI page routes. Each request uses its own read-only transaction."""

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import HTMLResponse, Response

from inves_cog.clock import SystemClock
from inves_cog.web.brief import page_brief_account, page_brief_market, page_brief_stocks, page_brief_trust
from inves_cog.web.brief_html import render_brief
from inves_cog.web.db import open_reader
from inves_cog.web.html_page import default_session, latest_visible_session, render_page
from inves_cog.web.pages import (
    page_graph,
    page_health,
    page_home,
    page_ledger,
    page_linkage,
    page_market,
    page_paper_stock,
    page_plan,
    page_portfolio,
    page_review,
    page_settings,
    page_stock,
    page_universe,
)
from inves_cog.web.stock_brief import page_brief_stock


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def create_app(dsn=None, clock=None):
    source = dsn or os.environ["INVES_COG_WEB_DATABASE_URL"]
    clock = clock or SystemClock()
    app = FastAPI()

    def call(builder, day, **extra):
        connection = open_reader(source)
        try:
            with connection.transaction():
                connection.execute("SET LOCAL default_transaction_read_only TO on")
                return _jsonable(builder(connection, day, clock, **extra))
        finally:
            connection.close()

    @app.get("/api/pages/home")
    def home(date: date):
        return call(page_home, date)

    @app.get("/api/pages/market")
    def market(date: date):
        return call(page_market, date)

    @app.get("/api/pages/barometer")
    def barometer_api():
        from inves_cog.web.barometer import api_payload

        return call(lambda c, d, cl: api_payload(c, cl), None)

    @app.get("/barometer")
    def barometer_page():
        from inves_cog.web.barometer import api_payload, render_page

        payload = call(lambda c, d, cl: api_payload(c, cl), None)
        return HTMLResponse(render_page(payload["history"]))

    @app.get("/api/pages/linkage/{event_id}")
    def linkage(event_id: str, date: date):
        return call(page_linkage, date, event_id=event_id)

    @app.get("/api/pages/stock/{symbol}")
    def stock(symbol: str, date: date):
        return call(page_stock, date, symbol=symbol)

    @app.get("/api/pages/graph")
    def graph(date: date):
        return call(page_graph, date)

    @app.get("/api/pages/settings/data")
    def settings_data(date: date):
        return call(page_settings, date)

    @app.get("/api/pages/paper/plan")
    def plan(date: date):
        return call(page_plan, date)

    @app.get("/api/pages/paper/portfolio")
    def portfolio(date: date):
        return call(page_portfolio, date)

    @app.get("/api/pages/paper/universe")
    def universe(date: date):
        return call(page_universe, date)

    @app.get("/api/pages/paper/stock/{symbol}")
    def paper_stock(symbol: str, date: date):
        return call(page_paper_stock, date, symbol=symbol)

    @app.get("/api/pages/paper/health")
    def health(date: date):
        return call(page_health, date)

    @app.get("/api/pages/paper/ledger")
    def ledger(date: date):
        return call(page_ledger, date)

    @app.get("/api/pages/review")
    def review(date: date):
        return call(page_review, date)

    @app.get("/api/pages/brief/market")
    def brief_market(date: date):
        return call(page_brief_market, date)

    @app.get("/api/pages/brief/stocks")
    def brief_stocks(date: date):
        return call(page_brief_stocks, date)

    @app.get("/api/pages/brief/account")
    def brief_account(date: date):
        return call(page_brief_account, date)

    @app.get("/api/pages/brief/trust")
    def brief_trust(date: date):
        return call(page_brief_trust, date)

    @app.get("/api/pages/brief/stock/{symbol}")
    def brief_stock(symbol: str, date: date):
        return call(page_brief_stock, date, symbol=symbol)

    _register_html(app, call, clock)
    return app


_INVESTOR_JS = Path(__file__).with_name("investor.js")
_LWC_JS = Path(__file__).with_name("lightweight-charts.js")


def _register_html(app, call, clock):
    @app.get("/investor.js")
    def investor_script():
        return Response(_INVESTOR_JS.read_text(encoding="utf-8"), media_type="text/javascript; charset=utf-8")

    @app.get("/lightweight-charts.js")
    def lwc_script():
        return Response(_LWC_JS.read_text(encoding="utf-8"), media_type="text/javascript; charset=utf-8")

    def show(builder, requested, **extra):
        payload = call(builder, requested or latest_visible_session(clock), **extra)
        return HTMLResponse(render_page(payload))

    def show_brief(builder, requested, **extra):
        # B-064: brief pages default to today; close cards carry the prior session.
        payload = call(builder, requested or default_session(clock), **extra)
        return HTMLResponse(render_brief(payload))

    @app.get("/")
    def home_html(date: date | None = None):
        return show_brief(page_brief_market, date)

    @app.get("/stocks")
    def stocks_html(date: date | None = None):
        return show_brief(page_brief_stocks, date)

    @app.get("/account")
    def account_html(date: date | None = None):
        return show_brief(page_brief_account, date)

    @app.get("/trust")
    def trust_html(date: date | None = None):
        return show_brief(page_brief_trust, date)

    @app.get("/log")
    def log_html(date: date | None = None):
        return show(page_home, date)

    @app.get("/market")
    def market_html(date: date | None = None):
        return show(page_market, date)

    @app.get("/linkage/{event_id}")
    def linkage_html(event_id: str, date: date | None = None):
        return show(page_linkage, date, event_id=event_id)

    @app.get("/search")
    def search_html(q: str = "", date: date | None = None):
        from inves_cog.web.brief import page_search

        payload = call(page_search, date or default_session(clock), q=q)
        if payload.get("redirect"):
            from fastapi.responses import RedirectResponse

            return RedirectResponse(payload["redirect"])
        return HTMLResponse(render_brief(payload))

    @app.get("/s/{symbol}")
    def investor_stock_html(symbol: str, date: date | None = None):
        return show_brief(page_brief_stock, date, symbol=symbol)

    @app.get("/stock/{symbol}")
    def stock_html(symbol: str, date: date | None = None):
        return show(page_stock, date, symbol=symbol)

    @app.get("/graph")
    def graph_html(date: date | None = None):
        return show(page_graph, date)

    @app.get("/settings/data")
    def settings_html(date: date | None = None):
        return show(page_settings, date)

    @app.get("/paper/plan")
    def plan_html(date: date | None = None):
        return show(page_plan, date)

    @app.get("/paper/portfolio")
    def portfolio_html(date: date | None = None):
        return show(page_portfolio, date)

    @app.get("/paper/universe")
    def universe_html(date: date | None = None):
        return show(page_universe, date)

    @app.get("/paper/stock/{symbol}")
    def paper_stock_html(symbol: str, date: date | None = None):
        return show(page_paper_stock, date, symbol=symbol)

    @app.get("/paper/health")
    def health_html(date: date | None = None):
        return show(page_health, date)

    @app.get("/paper/ledger")
    def ledger_html(date: date | None = None):
        return show(page_ledger, date)

    @app.get("/review")
    def review_html(date: date | None = None):
        return show(page_review, date)
