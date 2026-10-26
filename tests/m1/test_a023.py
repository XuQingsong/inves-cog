"""A023 uses recorded public-source responses and an injected clock, offline."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inves_cog.clock import FrozenClock

pytestmark = pytest.mark.phase1_blocking
FIXTURES = Path(__file__).parent / "fixtures/a023"
CLOCK = FrozenClock(datetime(2026, 10, 26, 14, tzinfo=timezone.utc))


def sample(name):
    return json.loads((FIXTURES / name).read_text())


def test_a023_real_calendar_shapes_and_missing_numbers():
    from inves_cog.ingest.resilience import parse_earnings, parse_econ

    rows = parse_earnings(sample("earnings_2026-10-28.json"), date(2026, 10, 28), CLOCK)
    googl = next(r for r in rows if r["ticker"] == "GOOGL")
    assert googl["time"] == "post" and googl["eps_forecast"] == 2.94 and googl["n_estimates"] == 14
    assert googl["market_cap"] == 3965210590000 and rows[-1]["time"] == "pre"
    raw = sample("earnings_2026-10-28.json")
    raw["data"]["rows"][0]["epsForecast"] = "N/A"
    assert parse_earnings(raw, date(2026, 10, 28), CLOCK)[0]["eps_forecast"] is None
    econ = parse_econ(sample("econ_2026-10-28.json"), date(2026, 10, 28), CLOCK)
    assert econ and all(r["country"] == "United States" for r in econ)
    assert all(r["actual"] is None for r in econ)
    assert econ[-1]["event_time_et"] == "08:30"


def test_a023_yahoo_close_date_and_no_current_unclosed_daily_bar():
    from inves_cog.ingest.resilience import parse_yahoo_vix

    rows = parse_yahoo_vix(sample("vix.json"), "VIX_YAHOO", CLOCK)
    assert next(r for r in rows if r["observation_date"] == date(2026, 10, 23))["value"] == pytest.approx(19.45)
    assert all(r["fetched_at"] == CLOCK.now_utc() for r in rows)
    raw = sample("vix.json")
    raw["chart"]["result"][0]["timestamp"] = [int(CLOCK.now_utc().timestamp())]
    raw["chart"]["result"][0]["indicators"]["quote"][0]["close"] = [99]
    assert parse_yahoo_vix(raw, "VIX_YAHOO", CLOCK) == []


def test_a023_vix_priority_and_v18_cboe_unchanged():
    from inves_cog.trading.execution.repository import select_vix

    d = date(2026, 10, 23)
    rows = [
        {"series_id": s, "observation_date": d, "value": v}
        for s, v in [("VIXCLS", 17), ("VIX_YAHOO", 19.45), ("VIX_CBOE", 20)]
    ]
    assert select_vix(rows) == ({d: 20}, {d: "VIX_CBOE"})
    assert select_vix(list(reversed(rows))) == select_vix(rows)
    assert select_vix(rows[:2]) == ({d: 19.45}, {d: "VIX_YAHOO"})
    assert select_vix(rows[:1]) == ({d: 17}, {d: "VIXCLS"})
    for row in rows[:2]:
        row["value"] = None
    assert select_vix(rows) == ({d: 20}, {d: "VIX_CBOE"})


def test_a023_cboe_failure_still_collects_both_yahoo_series_and_health():
    from inves_cog.ingest.resilience import collect_vix

    repo = Mock()
    repo.health_rows.return_value = {}

    def get(url, **kw):
        if "cboe.com" in url:
            raise RuntimeError("blocked")
        return sample("vix.json")

    http = SimpleNamespace(get=get)
    result = collect_vix(SimpleNamespace(repo=repo, clock=CLOCK), http=http)
    assert result["processed_count"] > 0
    assert {c.args[1]["series_id"] for c in repo.write.call_args_list} == {"VIX_YAHOO", "VIX3M_YAHOO"}
    health = {c.args[0]["source"]: c.args[0] for c in repo.write_health.call_args_list}
    assert health["VIX_CBOE"]["consecutive_failures"] == 1
    assert health["VIX_YAHOO"]["items_last_run"] > 0
    assert "2026-10-23" in health["VIX_YAHOO"]["note"]


def test_a023_rule_only_news_preserves_content_and_never_calls_models():
    from inves_cog.ingest.info import make_item
    from inves_cog.ingest.pipeline import Pipeline

    p = Pipeline.__new__(Pipeline)
    p.news_llm_enabled = False
    p.clock = CLOCK
    p.repo = Mock()
    p.triage = Mock()
    p.repo.info_signature.return_value = None
    row = make_item(
        "news",
        "benzinga",
        "1",
        headline="Company raises outlook",
        body="original",
        clock=CLOCK,
        published_at=CLOCK.now_utc(),
        tickers=["AAPL"],
    )
    p.info([row])
    saved = p.repo.put_info.call_args.args[0]
    assert saved["extraction_status"] == "ok" and saved["extraction_source"]["news_triage"]["reason"] == "rules_only"
    assert (
        saved["body"] == "original" and saved["first_seen_at"] == row["first_seen_at"] and saved["tickers"] == ["AAPL"]
    )
    p.repo.finish_pending_news.return_value = 2
    p.repo.pending_info.return_value = []
    assert p.enrich_pending()["rules_only"] == 2
    p.triage.process.assert_not_called()


def test_a023_schedule_calendar_and_news_monitor_independent():
    from inves_cog.ingest.runtime import due_tasks

    tasks = due_tasks(CLOCK, {})
    assert {"earnings_calendar", "econ_calendar", "news_poll", "news_watchdog"} <= set(tasks)
    sunday = FrozenClock(datetime(2026, 10, 25, 14, tzinfo=timezone.utc))
    assert "news_watchdog" not in due_tasks(sunday, {})


def test_a023_no_news_gap_alert_on_weekend_or_before_10_and_alert_exactly_two_hours():
    from datetime import timedelta

    from inves_cog.ingest.service import check_news_gap

    repo = Mock()
    repo.health_rows.return_value = {}
    repo.latest_news_at.return_value = CLOCK.now_utc() - timedelta(hours=2)
    assert check_news_gap(repo, CLOCK)["healthy"] is False
    assert repo.write_health.call_args.args[0]["status"] == "unavailable"
    repo.write_health.reset_mock()
    repo.latest_news_at.return_value = CLOCK.now_utc() - timedelta(hours=1, minutes=59)
    assert check_news_gap(repo, CLOCK)["healthy"] is True
    repo.latest_news_at.return_value = None
    assert check_news_gap(repo, FrozenClock(datetime(2026, 10, 25, 14, tzinfo=timezone.utc)))["healthy"] is True
    assert check_news_gap(repo, FrozenClock(datetime(2026, 10, 26, 13, tzinfo=timezone.utc)))["healthy"] is True
    repo.write_health.assert_not_called()


def test_a023_alpha_bulk_fallback_filtered_persisted_budget_no_retry(monkeypatch):
    from inves_cog.ingest.resilience import collect_calendars

    repo = Mock()
    repo.health_rows.return_value = {}
    repo.get_cursor.return_value = {}
    repo.holding_tickers.return_value = ["HELD"]
    p = SimpleNamespace(repo=repo, clock=CLOCK, stocks=["GOOGL"], values={"ALPHA_VANTAGE_API_KEY": "offline-test"})
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if "nasdaq" in url:
            raise RuntimeError("recorded outage")
        return (
            "symbol,name,reportDate,fiscalDateEnding,estimate,currency\n"
            "GOOGL,Alphabet,2026-10-28,2026-09-30,2.94,USD\n"
            "HELD,Held,2026-10-28,2026-09-30,,USD\n"
            "OTHER,Other,2026-10-28,2026-09-30,1,USD\n"
        )

    collect_calendars(p, "earnings", http=SimpleNamespace(get=get))
    assert len([url for url, _ in calls if "alphavantage" in url]) == 1
    assert {c.args[1]["ticker"] for c in repo.write.call_args_list} == {"GOOGL", "HELD"}
    assert all(c.args[1]["time"] == "unknown" for c in repo.write.call_args_list)
    repo.get_cursor.return_value = {"day": "2026-10-26", "attempts": 25}
    calls.clear()
    assert collect_calendars(p, "earnings", http=SimpleNamespace(get=get))["processed_count"] == 0
    assert not any("alphavantage" in url for url, _ in calls)
    assert repo.set_cursor.call_count == 1


def test_a023_installer_includes_news_and_calendars():
    from scripts.install_ingest_service import configuration

    text = configuration(Path("/project"), Path("/project/.venv/bin/python"))
    for task in ["news_poll", "news_watchdog", "vix_daily", "earnings_calendar", "econ_calendar"]:
        assert task in text


def test_a023_all_frozen_v18_vix_days_keep_cboe_and_identical_replay(monkeypatch):
    from inves_cog.trading.execution import replay
    from inves_cog.trading.execution.repository import select_vix

    signals, prices, original = replay.frozen_inputs()
    rows = []
    for day, value in original.items():
        rows.extend(
            {"series_id": source, "observation_date": day, "value": quote}
            for source, quote in [("VIXCLS", 99), ("VIX_YAHOO", 99), ("VIX_CBOE", value)]
        )
    selected, sources = select_vix(rows)
    assert selected == original and set(sources.values()) == {"VIX_CBOE"}
    baseline = replay.run_frozen()
    monkeypatch.setattr(replay, "frozen_inputs", lambda: (signals, prices, selected))
    actual = replay.run_frozen()
    assert actual["trades"] == baseline["trades"]
    assert actual["return_pct"] == baseline["return_pct"]
    assert actual["comparison"]["actual_count"] == actual["comparison"]["expected_count"] == 90
    assert actual["comparison"]["differences"] == []


def test_a023_review_budget_config_restored():
    import yaml
    from inves_cog.ingest.settings import ROOT

    assert (
        yaml.safe_load((ROOT / "config/params/p-2026.10/m1.yaml").read_text())["m1"]["llm_daily_token_budget"]
        == 1500000
    )


def test_a023_calendar_refresh_only_successful_dates(monkeypatch):
    from inves_cog.ingest.resilience import collect_calendars

    repo = Mock()
    repo.health_rows.return_value = {}
    p = SimpleNamespace(repo=repo, clock=CLOCK, stocks=[], values={})
    first, moved, failed = date(2026, 10, 28), date(2026, 10, 30), date(2026, 10, 29)
    monkeypatch.setattr("inves_cog.ingest.resilience.calendar_days", lambda day: [first, failed, moved])
    raw = sample("earnings_2026-10-28.json")
    raw["data"]["rows"] = [raw["data"]["rows"][0]]

    def get(url, **kwargs):
        d = kwargs["params"]["date"]
        if d == failed.isoformat():
            raise RuntimeError("recorded outage")
        return {"data": {"rows": []}} if d == first.isoformat() else raw

    collect_calendars(p, "earnings", http=SimpleNamespace(get=get))
    calls = repo.replace_calendar_day.call_args_list
    assert [c.args[1] for c in calls] == [first, moved]
    assert calls[0].args[3] == []
    assert calls[1].args[3][0]["ticker"] == "GOOG"


def test_a023_news_health_recovers_on_successful_collection():
    from datetime import timedelta
    from collections import Counter
    from inves_cog.ingest.pipeline import Pipeline
    from inves_cog.ingest.service import check_news_gap

    rows = {}
    repo = Mock()
    repo.health_rows.side_effect = lambda: rows
    repo.write_health.side_effect = lambda row: rows.update({row["source"]: row})
    repo.latest_news_at.return_value = CLOCK.now_utc() - timedelta(hours=3)
    assert not check_news_gap(repo, CLOCK)["healthy"]
    assert rows["AlpacaNews"]["status"] == "unavailable"
    p = Pipeline.__new__(Pipeline)
    p.clock, p.repo, p.day_override = CLOCK, repo, None
    repo.processed = 0
    p.alpaca = Mock()
    p.alpaca.news.return_value = []
    repo.counts = Counter()
    repo.get_cursor.return_value = {"through": CLOCK.now_utc().isoformat()}
    repo.latest_news_at.return_value = CLOCK.now_utc()
    p.runtime().run(["news_poll"])
    assert rows["AlpacaNews"]["status"] == "ok"
    assert rows["AlpacaNews"]["consecutive_failures"] == 0
    assert rows["AlpacaNews"]["last_success_at"] == CLOCK.now_utc()
