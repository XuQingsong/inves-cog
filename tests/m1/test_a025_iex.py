"""Recorded free IEX response, original timestamps and no actual network/model."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.runtime import due_tasks

pytestmark = pytest.mark.phase1_blocking
CLOCK = FrozenClock(datetime.fromisoformat("2026-10-27T10:24:46.890580+00:00"))


def sample():
    return json.loads((Path(__file__).parent / "fixtures/a025/iex_latest.json").read_text())


def test_iex_last_print_may_be_previous_day_without_fabricating_freshness():
    from inves_cog.ingest.intraday import parse_iex_trades

    previous = {"SPY": 766.56, "NVDA": 215.9, "IWM": 277.01}
    rows = parse_iex_trades(sample(), previous, sorted(previous), CLOCK)
    assert len(rows) == 3
    for r in rows:
        trade = sample()["trades"][r["ticker"]]
        assert r["source"] == "Alpaca:iex" and r["delay_minutes"] == 0
        assert r["as_of"] == datetime.fromisoformat(trade["t"].replace("Z", "+00:00"))
        assert r["last"] == trade["p"] and r["prev_close"] == previous[r["ticker"]]
        assert r["fetched_at"] == CLOCK.now_utc() and r["as_of"] < CLOCK.now_utc() - timedelta(hours=12)
    assert {r["session"] for r in rows} == {"regular", "post"}


@pytest.mark.parametrize(
    "moment,expected",
    [
        ("2026-10-27T03:59:00-04:00", False),
        ("2026-10-27T04:01:00-04:00", True),
        ("2026-10-27T08:01:00-04:00", True),
        ("2026-10-27T17:01:00-04:00", True),
        ("2026-10-27T20:00:00-04:00", False),
        ("2026-10-24T12:00:00-04:00", False),
    ],
)
def test_iex_polls_same_minute_windows_as_sip_even_when_exchange_closed(moment, expected):
    c = FrozenClock(datetime.fromisoformat(moment))
    tasks = due_tasks(c, {"iex_intraday": c.now_utc() - timedelta(minutes=1)})
    assert ("iex_intraday" in tasks) == expected
    assert "iex_intraday" not in due_tasks(c, {"iex_intraday": c.now_utc()})


def test_iex_batch_scope_uses_same_sip_previous_cache_and_never_updates_duplicate():
    from inves_cog.ingest.intraday import ETF_TICKERS, collect_iex_intraday

    repo, http = Mock(), Mock()
    repo.holding_tickers.return_value = ["OUTSIDE"]
    # Existing adjusted full-market closes cached by SIP, not IEX prevDailyBar.
    repo.get_cursor.return_value = {t: 100 for t in ETF_TICKERS | {"NVDA", "OUTSIDE"}}
    http.get.return_value = sample()
    p = SimpleNamespace(clock=CLOCK, repo=repo, stocks=["NVDA"], alpaca=SimpleNamespace(headers={}))
    result = collect_iex_intraday(p, http=http)
    assert result["processed_count"] == 3
    assert http.get.call_count == 1
    call = http.get.call_args
    assert call.args[0].endswith("/v2/stocks/trades/latest") and call.kwargs["params"]["feed"] == "iex"
    assert set(call.kwargs["params"]["symbols"].split(",")) == ETF_TICKERS | {"NVDA", "OUTSIDE"}
    for call in repo.write.call_args_list:
        assert call.args[0] == "intraday_snapshots" and call.args[1]["source"] == "Alpaca:iex"
        assert call.args[1]["prev_close"] == 100 and not call.kwargs.get("update")


@pytest.mark.parametrize("mutation", ["future", "old", "bad_price", "no_time", "wrong_exchange"])
def test_iex_rejects_unusable_public_trade(mutation):
    from inves_cog.ingest.intraday import parse_iex_trades

    raw = sample()
    trade = raw["trades"]["SPY"]
    if mutation == "future":
        trade["t"] = (CLOCK.now_utc() + timedelta(minutes=1)).isoformat()
    if mutation == "old":
        trade["t"] = (CLOCK.now_utc() - timedelta(days=31)).isoformat()
    if mutation == "bad_price":
        trade["p"] = float("nan")
    if mutation == "no_time":
        trade.pop("t")
    if mutation == "wrong_exchange":
        trade["x"] = "Q"
    assert parse_iex_trades(raw, {}, ["SPY"], CLOCK) == []


def test_pipeline_registers_iex_with_independent_source_health(monkeypatch):
    from inves_cog.ingest.pipeline import Pipeline

    operation = Mock(return_value={"processed_count": 3})
    monkeypatch.setattr("inves_cog.ingest.intraday.collect_iex_intraday", operation)
    repo = Mock()
    repo.health_rows.return_value = {}
    repo.graph_entities.return_value = []
    repo.monitored_entities.return_value = []
    p = Pipeline(clock=CLOCK, repository=repo, values={}, llm=Mock(), sec=Mock())
    source, collect = p.runtime().tasks["iex_intraday"]
    assert source == "AlpacaIEX" and collect()["processed_count"] == 3
    operation.assert_called_once_with(p)


def check_iex_database(c):
    from inves_cog.ingest.intraday import parse_iex_trades
    from inves_cog.ingest.repository import Repository

    repo = Repository(c)
    c.execute("SET LOCAL ROLE role_ingest")
    row = parse_iex_trades(sample(), {"SPY": 766.56}, ["SPY"], CLOCK)[0]
    row["ticker"] = "A025_IEX_ONLY"
    assert repo.write("intraday_snapshots", row) == 1
    assert (
        repo.write("intraday_snapshots", {**row, "last": 999, "fetched_at": CLOCK.now_utc() + timedelta(minutes=1)})
        == 0
    )
    assert repo.write("intraday_snapshots", {**row, "source": "Alpaca:delayed_sip", "delay_minutes": 15}) == 1
    actual = c.execute(
        "SELECT source,as_of,last,prev_close,delay_minutes,fetched_at "
        "FROM ingest.intraday_snapshots WHERE ticker='A025_IEX_ONLY' ORDER BY source"
    ).fetchall()
    assert len(actual) == 2
    iex = next(r for r in actual if r["source"] == "Alpaca:iex")
    assert iex["as_of"] == row["as_of"] and float(iex["last"]) == 765.225 and iex["delay_minutes"] == 0
    assert iex["fetched_at"] == row["fetched_at"] and all(float(r["prev_close"]) == 766.56 for r in actual)
    c.execute("RESET ROLE")


def test_iex_real_pg_separate_source_and_duplicate_trade_time():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row
    ) as c:
        try:
            check_iex_database(c)
        finally:
            c.rollback()
