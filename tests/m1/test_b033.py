"""B-033: wide daily bars keep a verified split factor, or NULL when unverified."""

from datetime import date, datetime

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.http import SourceError
from inves_cog.ingest.pipeline import Pipeline
from inves_cog.ingest.providers import Alpaca

DAY = date(2026, 10, 21)
EARLIER = date(2026, 10, 20)
CLOCK = FrozenClock(datetime.fromisoformat("2026-10-21T20:00:00Z"))

pytestmark = pytest.mark.phase1_blocking


def _bar(ticker, day, close):
    return {"t": f"{day.isoformat()}T19:00:00Z", "o": close, "h": close, "l": close, "c": close, "v": 100}


class Books:
    def __init__(self):
        self.rows = {}
        self.writes = []

    def write(self, table, row, *, update=()):
        self.writes.append((table, tuple(update)))
        if table != "bars_daily":
            return
        key = (row["ticker"], row["trade_date"])
        if key not in self.rows:
            self.rows[key] = dict(row)
            return
        for field in update:
            self.rows[key][field] = row.get(field)

    def latest_wide(self):
        return []

    def set_cursor(self, key, value, stamp):
        return None

    def first_bar_date(self):
        return None

    def post_close(self, ticker, day):
        return None


class Sec:
    def get(self, url):
        if url.endswith("company_tickers_exchange.json"):
            return {"fields": ["ticker", "cik"], "data": []}
        if "/frames/" in url:
            return {"data": []}
        raise AssertionError(url)


class Feed:
    def __init__(self, symbols, *, actions, fail=None):
        self.symbols = list(symbols)
        self.actions = actions
        self.fail = fail
        self.action_calls = []

    def get(self, url, params=None, headers=None, **kwargs):
        if url.endswith("/v2/assets"):
            return [
                {"symbol": symbol, "exchange": "NASDAQ", "class": "us_equity", "status": "active", "name": symbol}
                for symbol in self.symbols
            ]
        if url.endswith("/v2/stocks/bars"):
            symbols = params["symbols"].split(",")
            return {
                "bars": {symbol: [_bar(symbol, EARLIER, 20), _bar(symbol, DAY, 10)] for symbol in symbols},
                "next_page_token": None,
            }
        if url.endswith("/v1/corporate-actions"):
            self.action_calls.append(dict(params))
            if self.fail == "raise":
                raise SourceError("corporate actions incomplete")
            if self.fail == "page":
                return {"corporate_actions": {"forward_splits": [], "reverse_splits": []}, "next_page_token": "again"}
            if self.fail == "batch" and "FAIL" in params["symbols"].split(","):
                raise SourceError("batch corporate actions failed")
            return {"corporate_actions": self.actions, "next_page_token": None}
        raise AssertionError(url)


def _wide(symbols, actions, fail=None):
    books = Books()
    alpaca = Alpaca(clock=CLOCK, key="fixture", secret="fixture", http=Feed(symbols, actions=actions, fail=fail))
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.alpaca = alpaca
    pipeline.sec = Sec()
    pipeline.repo = books
    pipeline.clock = CLOCK
    pipeline.day_override = None
    report = pipeline.wide()
    return books, report, alpaca.http


def _stored(books, ticker, day):
    return books.rows[(ticker, day)]


def test_forward_split_uses_the_existing_factor_rule():
    actions = {
        "forward_splits": [{"symbol": "FWD", "old_rate": 1, "new_rate": 2, "ex_date": DAY.isoformat()}],
        "reverse_splits": [],
    }
    books, report, feed = _wide(["FWD"], actions)
    assert _stored(books, "FWD", EARLIER)["adj_factor"] == 0.5
    assert _stored(books, "FWD", DAY)["adj_factor"] == 1.0
    assert _stored(books, "FWD", DAY)["close"] == 10
    assert report["status"] == "ok"
    assert report["adj_factor_split"] == 2
    assert feed.action_calls[0]["types"] == "forward_split,reverse_split"


def test_reverse_split_divides_by_the_rate():
    actions = {
        "forward_splits": [],
        "reverse_splits": [{"symbol": "REV", "old_rate": 2, "new_rate": 1, "ex_date": DAY.isoformat()}],
    }
    books, report, _feed = _wide(["REV"], actions)
    assert _stored(books, "REV", EARLIER)["adj_factor"] == 2.0
    assert _stored(books, "REV", DAY)["adj_factor"] == 1.0
    assert report["adj_factor_split"] == 2 and report["adj_factor_null"] == 0


def test_confirmed_absence_of_splits_writes_one():
    actions = {"forward_splits": [], "reverse_splits": []}
    books, report, _feed = _wide(["FLAT"], actions)
    assert _stored(books, "FLAT", EARLIER)["adj_factor"] == 1.0
    assert _stored(books, "FLAT", DAY)["adj_factor"] == 1.0
    assert report["status"] == "ok"
    assert report["adj_factor_unity"] == 2
    assert report["adj_factor_null"] == 0


def test_failed_corporate_actions_stay_null_and_degraded():
    books, report, _feed = _wide(["GAP"], {"forward_splits": [], "reverse_splits": []}, fail="raise")
    assert _stored(books, "GAP", DAY)["adj_factor"] is None
    assert _stored(books, "GAP", EARLIER)["adj_factor"] is None
    assert _stored(books, "GAP", DAY)["close"] == 10
    assert report["status"] == "degraded"
    assert report["adj_factor_null"] == 2
    assert report["adj_factor_unity"] == 0
    assert "corporate actions incomplete" in report["note"]


def test_repeated_corporate_action_page_is_not_a_unit_factor():
    books, report, feed = _wide(["GAP"], {"forward_splits": [], "reverse_splits": []}, fail="page")
    assert _stored(books, "GAP", DAY)["adj_factor"] is None
    assert report["status"] == "degraded"
    assert report["adj_factor_null"] == 2
    assert "Repeated corporate actions pagination token" in report["note"]
    assert [call.get("page_token") for call in feed.action_calls] == [None, "again"]


def test_upsert_updates_the_factor_and_leaves_raw_prices_and_post_close():
    seeded = Books()
    seeded.rows[("FLAT", DAY)] = {
        "ticker": "FLAT",
        "trade_date": DAY,
        "open": 10,
        "high": 10,
        "low": 10,
        "close": 10,
        "volume": 100,
        "post_close": 9.5,
        "adj_factor": None,
        "source": "Alpaca",
    }
    alpaca = Alpaca(
        clock=CLOCK,
        key="fixture",
        secret="fixture",
        http=Feed(["FLAT"], actions={"forward_splits": [], "reverse_splits": []}),
    )
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.alpaca = alpaca
    pipeline.sec = Sec()
    pipeline.repo = seeded
    pipeline.clock = CLOCK
    pipeline.day_override = None
    first = pipeline.wide()
    second = pipeline.wide()
    stored = seeded.rows[("FLAT", DAY)]
    assert stored["close"] == 10 and stored["open"] == 10 and stored["high"] == 10 and stored["low"] == 10
    assert stored["volume"] == 100
    assert stored["adj_factor"] == 1.0
    assert stored["post_close"] == 9.5
    updates = [update for table, update in seeded.writes if table == "bars_daily"]
    assert "adj_factor" in updates[0]
    assert "post_close" not in updates[0]
    assert first["status"] == second["status"] == "ok"
    assert first["adj_factor_unity"] == second["adj_factor_unity"] == 2


def test_one_failed_batch_does_not_erase_a_verified_batch():
    symbols = [f"T{i:03d}" for i in range(200)] + ["FAIL"]
    books, report, _feed = _wide(symbols, {"forward_splits": [], "reverse_splits": []}, fail="batch")
    assert _stored(books, "T000", DAY)["adj_factor"] == 1.0
    assert _stored(books, "FAIL", DAY)["adj_factor"] is None
    assert report["status"] == "degraded"
    assert report["adj_factor_unity"] == 400
    assert report["adj_factor_null"] == 2
    assert report["adj_factor_split"] == 0


def test_pool_bars_still_record_post_close_and_split_factors():
    books = Books()
    actions = {
        "forward_splits": [{"symbol": "POOL", "old_rate": 1, "new_rate": 2, "ex_date": DAY.isoformat()}],
        "reverse_splits": [],
    }
    alpaca = Alpaca(clock=CLOCK, key="fixture", secret="fixture", http=Feed(["POOL"], actions=actions))
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.alpaca = alpaca
    pipeline.repo = books
    pipeline.clock = CLOCK
    pipeline.day_override = None
    pipeline.codes = ["POOL"]
    pipeline.bars()
    updates = [update for table, update in books.writes if table == "bars_daily"]
    assert "post_close" in updates[0] and "adj_factor" in updates[0]
    assert books.rows[("POOL", EARLIER)]["adj_factor"] == 0.5
    assert books.rows[("POOL", DAY)]["adj_factor"] == 1.0
    assert books.rows[("POOL", DAY)]["close"] == 10
