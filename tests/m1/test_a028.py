"""A028 real-shaped source contracts and deterministic pre-earnings sampling."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from inves_cog.clock import FrozenClock

pytestmark = pytest.mark.phase1_blocking
NY = ZoneInfo("America/New_York")


def clock(day="2026-11-16", hour=15, minute=50):
    return FrozenClock(
        datetime.combine(date.fromisoformat(day), datetime.min.time(), NY).replace(hour=hour, minute=minute)
    )


def test_consensus_scope_and_raw_quarter_currency():
    from inves_cog.ingest.earnings_data import consensus_fields, target_tickers

    assert target_tickers(["AAPL"], ["IBM"], ["NVDA"]) == ["AAPL", "IBM", "NVDA"]
    assert consensus_fields({"raw": {"revenue_estimate": {"0q": {"avg": 123, "revenueCurrency": "USD"}}}}) == {
        "rev_cq": 123,
        "rev_cq_currency": "USD",
    }
    assert consensus_fields({"rev_cy": 999, "raw": {}}) == {"rev_cq": None, "rev_cq_currency": None}


def test_calendar_horizon_includes_45_days_and_holidays():
    from inves_cog.ingest.resilience import calendar_days

    days = calendar_days(date(2026, 10, 30))
    assert max(days) >= date(2026, 12, 14)
    assert date(2026, 11, 17) in days


def test_implied_capture_pre_post_weekend_and_dedupe():
    from inves_cog.ingest.implied_moves import capture_targets

    rows = [
        {"ticker": "NVDA", "report_date": date(2026, 11, 17), "time": "post"},
        {"ticker": "INTC", "report_date": date(2026, 11, 16), "time": "pre"},
    ]
    assert [r["ticker"] for r in capture_targets(clock("2026-11-13"), rows, {"NVDA", "INTC"})] == ["INTC", "NVDA"]
    assert capture_targets(clock("2026-11-14"), rows, {"NVDA", "INTC"}) == []
    assert capture_targets(clock("2026-11-16", 15, 49), rows, {"NVDA", "INTC"}) == []
    assert [r["ticker"] for r in capture_targets(clock(), rows * 2, {"NVDA", "INTC"})] == ["NVDA"]


def snapshots():
    out = {}
    for expiry in ["261117", "261120"]:
        for strike in [210, 212.5, 215]:
            for side, bid, ask in [("C", 9.8, 10.0), ("P", 8.1, 8.3)]:
                out[f"NVDA{expiry}{side}{int(strike * 1000):08d}"] = {
                    "latestQuote": {"t": "2026-11-16T20:49:59Z", "bp": bid, "ap": ask},
                    "greeks": {"delta": 0.5},
                }
    return {"snapshots": out, "next_page_token": None}


@pytest.mark.parametrize(
    "slot,expiry", [("pre", date(2026, 11, 17)), ("post", date(2026, 11, 20)), ("unknown", date(2026, 11, 20))]
)
def test_expiry_strike_missing_iv_and_aligned_spot(slot, expiry):
    from inves_cog.ingest.implied_moves import select_move

    row = select_move(
        "NVDA",
        date(2026, 11, 17),
        slot,
        snapshots()["snapshots"],
        clock().now_utc(),
        lambda at: {"last": 213.7, "as_of": at, "source": "AlpacaIEX"},
    )
    assert row["expiry"] == expiry and row["strike"] == 212.5
    assert row["spot_source"] == "IEX" and row["iv_call"] is None and row["iv_put"] is None
    assert row["straddle_pct"] == pytest.approx(18.1 / 213.7)
    assert row["feed"] == "indicative"


def test_mismatched_session_or_stale_quotes_not_fabricated():
    from inves_cog.ingest.implied_moves import select_move

    def spot(at):
        return {"last": 213.7, "as_of": at - timedelta(minutes=16), "source": "AlpacaIEX"}

    assert select_move("NVDA", date(2026, 11, 17), "post", snapshots()["snapshots"], clock().now_utc(), spot) is None
    assert (
        select_move(
            "NVDA",
            date(2026, 11, 17),
            "post",
            snapshots()["snapshots"],
            clock("2026-11-17").now_utc(),
            lambda at: {"last": 213.7, "as_of": at, "source": "AlpacaIEX"},
        )
        is None
    )


def test_consensus_daily_no_models_and_retry_only_next_day():
    from inves_cog.ingest.earnings_data import collect_consensus

    repo = SimpleNamespace(
        snapshot_today=Mock(return_value=False), annual_years=Mock(return_value=(None, None)), put_snapshot=Mock()
    )
    provider = SimpleNamespace(
        collect=Mock(return_value={"ticker": "NVDA", "raw": {"earnings_estimate": {"0q": {"avg": 2}}}})
    )
    llm = Mock()
    result = collect_consensus(clock=clock(), repository=repo, tickers=["NVDA"], provider=provider)
    assert result["processed_count"] == 1
    repo.put_snapshot.assert_called_once()
    repo.snapshot_today.return_value = True
    assert (
        collect_consensus(clock=clock(), repository=repo, tickers=["NVDA"], provider=provider)["processed_count"] == 0
    )
    assert provider.collect.call_count == 1 and llm.mock_calls == []


def test_option_pagination_http_429_and_reference_feed():
    from inves_cog.ingest.http import HTTPClient, Response, SourceError
    from inves_cog.ingest.implied_moves import option_chain

    send = Mock(
        side_effect=[
            Response(200, {"snapshots": {"a": {}}, "next_page_token": "p2"}),
            Response(200, {"snapshots": {"b": {}}, "next_page_token": None}),
        ]
    )
    assert set(option_chain(HTTPClient(send=send), {}, "NVDA", date(2026, 11, 17), "post")) == {"a", "b"}
    assert send.call_args_list[0].kwargs["params"]["feed"] == "indicative"
    assert send.call_args_list[1].kwargs["params"]["page_token"] == "p2"
    send = Mock(return_value=Response(429, {}))
    with pytest.raises(SourceError):
        option_chain(HTTPClient(send=send), {}, "NVDA", date(2026, 11, 17), "post")
    assert send.call_count == 1


def test_stock_trade_alignment_uses_iex_and_real_response_shape():
    from inves_cog.ingest.implied_moves import aligned_spot

    at = clock().now_utc() - timedelta(seconds=1)
    db = Mock()
    db.execute.return_value.fetchone.return_value = None
    http = Mock()
    http.get.return_value = {"trades": {"NVDA": [{"t": at.isoformat(), "p": 213.7, "s": 100}]}, "next_page_token": None}
    assert aligned_spot(db, http, {}, "NVDA", at) == {"last": 213.7, "as_of": at, "source": "IEX"}
    assert http.get.call_args.kwargs["params"]["feed"] == "iex"
    assert http.get.call_args.kwargs["params"]["symbols"] == "NVDA"


def test_calendar_missing_90_days_and_nasdaq_nvda_shape():
    from inves_cog.ingest.earnings_data import calendar_missing
    from inves_cog.ingest.resilience import parse_earnings

    rows = parse_earnings(
        {
            "data": {
                "rows": [
                    {
                        "symbol": "NVDA",
                        "name": "NVIDIA Corporation",
                        "time": "time-after-hours",
                        "epsForecast": "$2.49",
                        "noOfEsts": "13",
                        "marketCap": "$5,149,206,000,000",
                    }
                ]
            }
        },
        date(2026, 11, 17),
        clock(),
    )
    assert rows[0]["time"] == "post" and rows[0]["eps_forecast"] == 2.49
    assert calendar_missing(rows, date(2026, 10, 30), {"NVDA", "MU"}) == ["MU"]


def test_consensus_snapshot_reader_has_cutoff_and_raw_fields():
    from inves_cog.ingest.earnings_data import Repository

    db = Mock()
    db.execute.return_value.fetchone.return_value = {
        "ticker": "NVDA",
        "raw": {"revenue_estimate": {"0q": {"avg": 5, "revenueCurrency": "USD"}}},
    }
    row = Repository(db).latest_snapshot("NVDA", clock().now_utc())
    assert row["rev_cq"] == 5 and row["rev_cq_currency"] == "USD"
    assert "captured_at<=%s" in db.execute.call_args.args[0]


def test_unaligned_and_missing_quotes_record_degraded_health(monkeypatch):
    from inves_cog.ingest.implied_moves import collect_moves
    from inves_cog.ingest.jobs import HealthBook, JobRunner

    db = Mock()
    event = {"ticker": "NVDA", "report_date": date(2026, 11, 17), "time": "post"}
    db.execute.return_value.fetchall.return_value = [event]
    db.execute.return_value.fetchone.return_value = None
    http = Mock()
    http.get.return_value = {"snapshots": {}, "next_page_token": None}
    health = HealthBook(clock=clock())
    model_calls = Mock()
    monkeypatch.setattr("inves_cog.llm.client.Client.from_environment", model_calls)
    result = JobRunner(clock=clock(), health=health, persist=Mock()).run(
        "earnings_implied_moves",
        "AlpacaIndicative",
        lambda: collect_moves(
            clock=clock(), db=db, values={"APCA_API_KEY_ID": "offline", "APCA_API_SECRET_KEY": "offline"}, http=http
        ),
    )
    assert result["processed_count"] == 0 and result["status"] == "degraded"
    assert health.rows["AlpacaIndicative"]["status"] == "degraded"
    assert model_calls.call_count == 0
    assert not any("INSERT" in call.args[0] for call in db.execute.call_args_list)


@pytest.mark.parametrize("code", [401, 403, 429])
def test_daily_estimates_uses_existing_free_page_when_json_requires_auth(code):
    import json

    from inves_cog.ingest.fundamentals.providers import YFinance
    from inves_cog.ingest.http import SourceError

    data = {
        "earningsTrend": {
            "trend": [
                {
                    "period": "0q",
                    "earningsEstimate": {"avg": {"raw": 2}},
                    "revenueEstimate": {"avg": {"raw": 100}, "revenueCurrency": "USD"},
                }
            ]
        }
    }
    page = '<script type="application/json">' + json.dumps(data) + "</script>"
    http = Mock()
    http.get.side_effect = [SourceError("unavailable json", status_code=code), page]
    row = YFinance(clock=clock(), http=http).collect("NVDA", fy_cy=None, fy_ny=None)
    assert row["source"] == "yahoo_page" and row["eps_cq"] == 2
    assert len(http.get.call_args_list) == 2


def test_daily_scheduler_scope_health_restart_and_options_slot(monkeypatch):
    from unittest.mock import MagicMock

    from inves_cog.ingest import earnings_data

    db = MagicMock()
    db.__enter__.return_value = db
    db.execute.return_value.fetchone.return_value = {"ok": True}
    db.execute.return_value.fetchall.return_value = [{"ticker": "HELD"}]
    ops = Mock()
    ops.last_runs.return_value = {}
    ops.health_rows.return_value = {}
    ops.write_job.return_value = 1
    monkeypatch.setattr(earnings_data, "Operations", lambda db: ops)
    monkeypatch.setattr(earnings_data, "Repository", lambda db: Mock())
    consensus = Mock(return_value={"processed_count": 1})
    options = Mock(return_value={"processed_count": 1})
    model_calls = Mock()
    monkeypatch.setattr(earnings_data, "collect_consensus", consensus)
    monkeypatch.setattr("inves_cog.ingest.implied_moves.collect_moves", options)
    monkeypatch.setattr("inves_cog.llm.client.Client.from_environment", model_calls)
    earnings_data.scheduled(clock=clock(hour=6, minute=0), values={}, connect=lambda values: db)
    assert {"HELD", "NVDA", "INTC"} <= set(consensus.call_args.kwargs["tickers"])
    ops.last_runs.return_value = {"earnings_consensus": clock().now_utc()}
    earnings_data.scheduled(clock=clock(), values={}, connect=lambda values: db)
    assert options.call_count == 1 and consensus.call_count == 1
    ops.last_runs.return_value["earnings_implied_moves"] = clock().now_utc()
    earnings_data.scheduled(clock=clock(), values={}, connect=lambda values: db)
    assert options.call_count == 1 and model_calls.call_count == 0
    assert any(c.args[0]["source"] == "AlpacaIndicative" for c in ops.write_health.call_args_list)


def test_capture_window_1550_to_1557():
    """First pass inside 15:50-15:57 captures; 15:58 does not (复核一 fix)."""
    from inves_cog.ingest.implied_moves import capture_targets

    rows = [{"ticker": "NVDA", "report_date": date(2026, 11, 17), "timing": "post"}]
    assert [r["ticker"] for r in capture_targets(clock("2026-11-16", 15, 53), rows, {"NVDA"})] == ["NVDA"]
    assert [r["ticker"] for r in capture_targets(clock("2026-11-16", 15, 57), rows, {"NVDA"})] == ["NVDA"]
    assert capture_targets(clock("2026-11-16", 15, 58), rows, {"NVDA"}) == []


def test_long_jobs_not_started_1510_1558():
    """earnings_consensus must not start inside 15:10-15:58 (复核一)."""
    from unittest.mock import MagicMock
    from inves_cog.ingest import earnings_data as ed

    for minute in (10, 20, 50):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        Ops = MagicMock()
        Ops.return_value.last_runs.return_value = {}
        Ops.return_value.health_rows.return_value = []
        runs = []
        Runner = MagicMock()
        Runner.return_value.run.side_effect = lambda name, src, fn: runs.append(name)
        from unittest.mock import patch

        with (
            patch.object(ed, "Operations", Ops),
            patch.object(ed, "Fundamentals"),
            patch.object(ed, "HealthBook"),
            patch.object(ed, "JobRunner", Runner),
            patch.object(ed.yaml, "safe_load", return_value={"stocks": []}),
        ):
            out = ed.scheduled(clock=clock(minute=minute), values={}, connect=lambda v: conn)
        assert "consensus" not in out and "earnings_consensus" not in runs, f"consensus started at 15:{minute}"
