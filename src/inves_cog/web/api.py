"""FastAPI page routes. Each request uses its own read-only transaction."""

import os
from datetime import date, datetime
from decimal import Decimal

from fastapi import FastAPI

from inves_cog.clock import SystemClock
from inves_cog.web.db import open_reader
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

    return app
