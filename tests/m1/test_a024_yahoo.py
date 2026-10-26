"""A024 extension: recorded public Yahoo responses, offline clocks, no LLM."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.jobs import HealthBook, JobRunner
from inves_cog.ingest.runtime import Runtime, due_tasks

pytestmark = pytest.mark.phase1_blocking
FIXTURES = Path(__file__).parent / "fixtures/a024/yahoo"
CLOCK = FrozenClock(datetime(2026, 10, 26, 15, 25, 5, tzinfo=timezone.utc))
SYMBOLS = [
    "ES=F",
    "NQ=F",
    "RTY=F",
    "YM=F",
    "^FVX",
    "^TNX",
    "^TYX",
    "CL=F",
    "BZ=F",
    "GC=F",
    "DX-Y.NYB",
    "BTC-USD",
    "^VIX",
]
ETFS = {"DIA", "SMH", "SOXX", "IGV", "XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLI", "XLU", "XLC", "XLRE", "XLB"}


def sample(symbol):
    return json.loads((FIXTURES / (symbol.replace("^", "").replace("=", "_") + ".json")).read_text())


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_recorded_yahoo_original_time_previous_close_and_actual_delay(symbol):
    from inves_cog.ingest.intraday import parse_yahoo_snapshot

    raw = sample(symbol)
    meta = raw["chart"]["result"][0]["meta"]
    row = parse_yahoo_snapshot(raw, symbol, CLOCK)
    assert row["ticker"] == symbol and row["source"] == "Yahoo"
    assert row["last"] == meta["regularMarketPrice"]
    assert row["prev_close"] == meta["chartPreviousClose"]
    assert row["as_of"] == datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc)
    assert row["session"] == "regular" and row["fetched_at"] == CLOCK.now_utc()
    assert row["delay_minutes"] == math.ceil((CLOCK.now_utc() - row["as_of"]).total_seconds() / 60)


@pytest.mark.parametrize(
    "symbol,last,previous,bps", [("^FVX", 4.814, 4.805, 0.9), ("^TNX", 4.98, 4.988, -0.8), ("^TYX", 5.298, 5.315, -1.7)]
)
def test_yahoo_yields_are_direct_percentage_points_not_tenfold(symbol, last, previous, bps):
    from inves_cog.ingest.intraday import parse_yahoo_snapshot

    row = parse_yahoo_snapshot(sample(symbol), symbol, CLOCK)
    assert row["last"] == last and row["prev_close"] == previous
    assert (row["last"] - row["prev_close"]) * 100 == pytest.approx(bps)


def test_minute_fallback_pairs_timestamp_with_its_nonnull_close():
    from inves_cog.ingest.intraday import parse_yahoo_snapshot

    raw = sample("CL=F")
    result = raw["chart"]["result"][0]
    result["meta"].pop("regularMarketTime")
    result["meta"].pop("regularMarketPrice")
    result["indicators"]["quote"][0]["close"][-1] = None
    row = parse_yahoo_snapshot(raw, "CL=F", CLOCK)
    assert row["as_of"] == datetime.fromtimestamp(result["timestamp"][-2], timezone.utc)
    assert row["last"] == result["indicators"]["quote"][0]["close"][-2]
    result["meta"].pop("chartPreviousClose")
    assert parse_yahoo_snapshot(raw, "CL=F", CLOCK)["prev_close"] == result["meta"]["previousClose"]
    result["meta"].pop("previousClose")
    assert parse_yahoo_snapshot(raw, "CL=F", CLOCK)["prev_close"] is None


@pytest.mark.parametrize("mutation", ["yesterday", "future", "symbol", "error", "bad_price"])
def test_yahoo_rejects_stale_future_mismatched_or_invalid_snapshot(mutation):
    from inves_cog.ingest.intraday import parse_yahoo_snapshot

    raw = sample("^TNX")
    meta = raw["chart"]["result"][0]["meta"]
    if mutation == "yesterday":
        meta["regularMarketTime"] -= 3 * 86400
    if mutation == "future":
        meta["regularMarketTime"] += 86400
    if mutation == "symbol":
        meta["symbol"] = "^TYX"
    if mutation == "error":
        raw["chart"] = {"result": None, "error": {"code": "Not Found"}}
    if mutation == "bad_price":
        meta["regularMarketPrice"] = float("nan")
    with pytest.raises(ValueError):
        parse_yahoo_snapshot(raw, "^TNX", CLOCK)


@pytest.mark.parametrize(
    "moment,expected",
    [
        ("2026-10-26T03:59:00-04:00", False),
        ("2026-10-26T04:00:00-04:00", True),
        ("2026-10-26T09:30:00-04:00", True),
        ("2026-10-26T16:00:00-04:00", True),
        ("2026-10-26T20:00:00-04:00", False),
        ("2026-10-24T12:00:00-04:00", False),
        ("2026-12-25T12:00:00-05:00", False),
        ("2026-11-02T04:00:00-05:00", True),
    ],
)
def test_yahoo_same_stock_windows_no_overnight_or_nontrading_expansion(moment, expected):
    clock = FrozenClock(datetime.fromisoformat(moment))
    tasks = due_tasks(clock, {})
    assert ("yahoo_intraday" in tasks) == expected
    assert ("yahoo_intraday" in tasks) == ("intraday_snapshots" in tasks)


def test_partial_yahoo_failure_continues_other_symbols_and_degrades_own_health():
    from inves_cog.ingest.intraday import collect_yahoo_intraday

    repo = Mock()
    p = SimpleNamespace(clock=CLOCK, repo=repo)
    http = Mock()

    def get(url, **kwargs):
        from urllib.parse import unquote

        symbol = unquote(url.rsplit("/", 1)[1])
        if symbol == "^TNX":
            raise ConnectionError("private details must not leak")
        return sample(symbol)

    http.get.side_effect = get
    health = HealthBook(clock=CLOCK, persist=repo.write_health)
    runner = JobRunner(clock=CLOCK, health=health, persist=repo.write_job)
    result = runner.run("yahoo_intraday", "YahooIntraday", lambda: collect_yahoo_intraday(p, http=http))
    assert result["processed_count"] == 12 and result["status"] == "degraded"
    assert http.get.call_count == 13 and repo.write.call_count == 12
    assert "private details" not in str(result)
    assert health.rows["YahooIntraday"]["status"] == "degraded"
    assert all(c.args[1]["source"] == "Yahoo" for c in repo.write.call_args_list)


def test_alpaca_failure_does_not_prevent_yahoo_in_same_runtime():
    from inves_cog.ingest.intraday import collect_intraday, collect_yahoo_intraday

    repo = Mock()
    repo.holding_tickers.return_value = []
    p = SimpleNamespace(clock=CLOCK, repo=repo, stocks=[], alpaca=None)
    http = Mock()
    http.get.side_effect = lambda url, **kwargs: sample(
        __import__("urllib.parse", fromlist=["unquote"]).unquote(url.rsplit("/", 1)[1])
    )
    health = HealthBook(clock=CLOCK, persist=repo.write_health)
    runtime = Runtime(
        clock=CLOCK,
        health=health,
        persist_job=repo.write_job,
        tasks={
            "intraday_snapshots": ("AlpacaIntraday", lambda: collect_intraday(p)),
            "yahoo_intraday": ("YahooIntraday", lambda: collect_yahoo_intraday(p, http=http)),
        },
    )
    result = runtime.run(["intraday_snapshots", "yahoo_intraday"])
    assert result["intraday_snapshots"]["source_success"] is False
    assert result["yahoo_intraday"]["processed_count"] == 13
    assert health.rows["YahooIntraday"]["status"] == "ok"
    assert health.rows["AlpacaIntraday"]["status"] != "ok"


def test_all_extended_etfs_and_original_pool_holdings_union():
    from inves_cog.ingest.intraday import collect_intraday

    repo = Mock()
    repo.holding_tickers.return_value = ["OUTSIDE"]
    p = SimpleNamespace(clock=CLOCK, repo=repo, stocks=["GOOGL"], alpaca=SimpleNamespace(headers={}))
    http = Mock()
    http.get.side_effect = [{}, {"bars": {}}]
    collect_intraday(p, http=http)
    assert set(http.get.call_args_list[0].kwargs["params"]["symbols"].split(",")) == ETFS | {
        "SPY",
        "QQQ",
        "IWM",
        "GOOGL",
        "OUTSIDE",
    }


def test_direct_collectors_do_not_fetch_outside_authorized_window():
    from inves_cog.ingest.intraday import collect_intraday, collect_yahoo_intraday

    p = SimpleNamespace(clock=FrozenClock(datetime.fromisoformat("2026-10-26T20:01:00-04:00")), repo=Mock())
    http = Mock()
    for collect in [collect_intraday, collect_yahoo_intraday]:
        assert collect(p, http=http)["processed_count"] == 0
    http.get.assert_not_called()


def test_yahoo_all_requests_fail_once_each_and_health_marks_failure(monkeypatch):
    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.intraday import collect_yahoo_intraday

    send = Mock(return_value=Response(429, {"chart": {"result": None}}))
    made = []

    def client(**kwargs):
        made.append(kwargs)
        return HTTPClient(send=send, **kwargs)

    monkeypatch.setattr("inves_cog.ingest.intraday.HTTPClient", client)
    repo = Mock()
    p = SimpleNamespace(clock=CLOCK, repo=repo)
    health = HealthBook(clock=CLOCK, persist=repo.write_health)
    runner = JobRunner(clock=CLOCK, health=health, persist=repo.write_job)
    result = runner.run("yahoo_intraday", "YahooIntraday", lambda: collect_yahoo_intraday(p))
    assert result["processed_count"] == 0 and result["source_success"] is False
    assert send.call_count == 13 and made == [{"timeout": 10, "retries": 0}]
    assert health.rows["YahooIntraday"]["consecutive_failures"] == 1
    assert health.rows["YahooIntraday"]["status"] == "degraded"
    repo.write.assert_not_called()


@pytest.mark.parametrize("moment", ["2026-10-26T04:30:00-04:00", "2026-10-26T16:00:00-04:00"])
def test_both_sources_use_persisted_starts_to_avoid_retries_in_same_slot(moment):
    clock = FrozenClock(datetime.fromisoformat(moment))
    tasks = ["intraday_snapshots", "yahoo_intraday"]
    assert not set(tasks) & set(due_tasks(clock, dict.fromkeys(tasks, clock.now_utc())))
