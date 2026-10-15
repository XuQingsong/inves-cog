"""M1 v2 contracts: both boundary rejection and valid-input preservation."""

import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from inves_cog.clock import FrozenClock
from tests.harness.tools.golden import load_golden

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/phase1"


def instant(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def frozen(text="2026-10-29T00:30:00Z"):
    return FrozenClock(instant(text))


class FakeTime:
    def __init__(self):
        self.value = 0.0
        self.waits = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        assert seconds >= 0
        self.waits.append(seconds)
        self.value += seconds


def test_bar_window_to_20et():
    from inves_cog.ingest.runtime import due_tasks

    before = frozen("2026-10-28T00:19:00Z")
    ready = frozen("2026-10-28T00:20:00Z")
    assert "bars_full" not in due_tasks(before, {})
    assert "bars_full" in due_tasks(ready, {})
    assert "bars_full" not in due_tasks(ready, {"bars_full": ready.now_utc()})
    # A manual run before the scheduled slot must not consume that day's slot.
    for name in ("bars_full", "wide_universe"):
        assert name in due_tasks(ready, {name: instant("2026-10-27T07:08:37Z")})
        assert name in due_tasks(ready, {name: instant("2026-10-28T00:19:59Z")})
        assert name not in due_tasks(ready, {name: ready.now_utc()})
    winter = frozen("2026-11-03T01:20:00Z")
    assert "bars_full" in due_tasks(winter, {"bars_full": instant("2026-11-02T08:00:00Z")})
    assert "bars_full" not in due_tasks(winter, {"bars_full": winter.now_utc()})
    prefill = frozen("2026-10-28T12:00:00Z")
    assert "bars_prefill" in due_tasks(prefill, {"bars_prefill": instant("2026-10-28T11:59:59Z")})
    assert "bars_prefill" not in due_tasks(prefill, {"bars_prefill": prefill.now_utc()})
    assert "bars_prefill" in due_tasks(frozen("2026-10-28T12:00:00Z"), {})
    assert "sec_submissions" not in due_tasks(frozen("2026-10-28T01:16:00Z"), {})
    # M1 v3: historical collection has no current-day deadline assertion.
    from inves_cog.ingest.pipeline import bar_run_mode

    assert bar_run_mode(frozen("2026-10-14T10:00:00Z"), date(2026, 10, 13)) == "historical_backfill"
    assert bar_run_mode(frozen("2026-10-15T00:46:00Z"), date(2026, 10, 14)) == "current_day"
    with pytest.raises(ValueError, match="future"):
        bar_run_mode(frozen("2026-10-14T10:00:00Z"), date(2026, 10, 15))
    from inves_cog.ingest.jobs import HealthBook
    from inves_cog.ingest.runtime import Runtime

    clock = frozen("2026-10-14T10:00:00Z")
    jobs = []
    runner = Runtime(
        clock=clock,
        health=HealthBook(clock=clock),
        persist_job=jobs.append,
        tasks={"bars_full": ("Alpaca", lambda: {"processed_count": 1})},
        trade_date=lambda: date(2026, 10, 13),
    )
    runner.run(["bars_full"])
    assert jobs[0]["trade_date"] == date(2026, 10, 13) and runner.runner.timeout_seconds == 1500
    from inves_cog.ingest.cli import schedule_once

    class ScheduleRepo:
        def __init__(self):
            self.rows = [(date(2026, 10, 27), instant("2026-10-29T00:15:00Z"))]

        def last_runs(self, *, trade_date=None):
            stamps = [stamp for day, stamp in self.rows if trade_date is None or day == trade_date]
            return {"bars_full": max(stamps)} if stamps else {}

    class ScheduledPipeline:
        repo = ScheduleRepo()
        clock = frozen("2026-10-29T00:20:00Z")

    class ScheduledRuntime:
        tasks = {"bars_full": None, "wide_universe": None}

        def run(self, names):
            return names

    assert schedule_once(ScheduledPipeline(), ScheduledRuntime(), names=["bars_full"]) == ["bars_full"]
    ScheduledPipeline.repo.rows.append((date(2026, 10, 28), instant("2026-10-29T00:20:00Z")))
    assert schedule_once(ScheduledPipeline(), ScheduledRuntime(), names=["bars_full"]) == {}
    with pytest.raises(ValueError, match="Unknown"):
        schedule_once(ScheduledPipeline(), ScheduledRuntime(), names=["wrong"])
    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.market import MarketCollector, market_window, schedule_times
    from inves_cog.ingest.sec_client import SECClient
    from inves_cog.llm.client import Client, LLMUnavailable

    settings = yaml.safe_load((ROOT / "config/params/p-2026.10/m1.yaml").read_text())["m1"]
    assert settings["minute_window"] == {"start": "04:00", "end": "20:00", "timezone": "America/New_York"}
    assert market_window(date(2026, 10, 28))[1] == instant("2026-10-29T00:00:00Z")
    assert market_window(date(2026, 11, 2))[1] == instant("2026-11-03T01:00:00Z")
    from inves_cog.ingest.providers import Alpaca

    for day, clock in (
        (date(2026, 10, 28), frozen("2026-10-29T00:20:00Z")),
        (date(2026, 11, 2), frozen("2026-11-03T01:20:00Z")),
    ):
        requests = []

        def daily_send(method, url, requests=requests, **kwargs):
            requests.append(kwargs["params"])
            return Response(200, {"bars": {}, "next_page_token": None})

        daily_client = Alpaca(clock=clock, key="fixture", secret="fixture", http=HTTPClient(daily_send))
        assert daily_client.daily_bars(["AAPL"], day - timedelta(days=30), day) == []
        assert instant(requests[0]["end"]) == market_window(day)[1]
        assert instant(requests[0]["end"]) <= clock.now_utc() - timedelta(minutes=15)
        assert requests[0]["feed"] == "sip" and requests[0]["adjustment"] == "raw"
    assert schedule_times(date(2026, 10, 28))["full_start"] == instant("2026-10-29T00:20:00Z")
    assert schedule_times(date(2026, 11, 2))["full_deadline"] == instant("2026-11-03T01:45:00Z")
    pages = [
        Response(
            200,
            {
                "bars": {"AAPL": [{"t": "2026-10-28T13:30:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 3}]},
                "next_page_token": "next",
            },
        ),
        Response(200, {"bars": {}, "next_page_token": None}),
    ]
    calls = []

    def send(method, url, **kwargs):
        calls.append(kwargs)
        return pages.pop(0)

    collector = MarketCollector(HTTPClient(send), clock=frozen())
    result = collector.minute_bars(["AAPL"], date(2026, 10, 28))
    assert result.exhausted and len(result.rows) == 1
    assert all(call["params"]["feed"] == "sip" for call in calls)
    assert calls[1]["params"]["page_token"] == "next"
    assert result.coverage["AAPL"] == pytest.approx(1 / 390)
    iex = MarketCollector(
        HTTPClient(lambda *a, **k: Response(200, {"bars": {}, "next_page_token": None})), clock=frozen(), feed="iex"
    )
    assert iex.minute_bars(["AAPL"], date(2026, 10, 28)).status == "degraded"
    timer, requests = FakeTime(), []

    def sec_send(method, url, **kwargs):
        requests.append((timer.value, kwargs))
        return Response(200, {"ok": True})

    client = SECClient(
        HTTPClient(sec_send), user_agent="fixture-contact.invalid", monotonic=timer.monotonic, sleep=timer.sleep
    )
    for _ in range(6):
        client.get("https://data.sec.gov/submissions/CIK0000320193.json")
    assert requests[5][0] - requests[0][0] >= 1
    assert all(req[1]["headers"]["User-Agent"] == "fixture-contact.invalid" for req in requests)
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        SECClient(HTTPClient(sec_send), user_agent="")
    registry = ROOT / "config/llm_tasks.yaml"
    llm = Client(registry=registry, recordings=FIXTURES / "recordings")
    assert llm.call("entity_tagging", {"headline": "Apple introduces a product", "body": "AAPL"}) == {
        "entities": ["apple"]
    }
    with pytest.raises(ValueError, match="unregistered"):
        llm.call("unknown", {})
    with pytest.raises(LLMUnavailable):
        llm.call("entity_tagging", {"unrecorded": True})


def test_bar_window_from_04et():
    from inves_cog.ingest.market import bar_session, market_window, schedule_times

    assert market_window(date(2026, 10, 28))[0] == instant("2026-10-28T08:00:00Z")
    assert schedule_times(date(2026, 11, 2))["prefill"] == instant("2026-11-02T13:00:00Z")
    assert bar_session(instant("2026-11-27T17:59:00Z")) == "intraday"
    assert bar_session(instant("2026-11-27T18:00:00Z")) == "post"
    assert bar_session(instant("2026-10-28T13:30:00Z")) == "intraday"
    assert bar_session(instant("2026-10-28T07:59:00Z")) is None
    assert bar_session(instant("2026-10-29T00:00:00Z")) is None
    assert bar_session(instant("2026-11-26T15:00:00Z")) is None


def test_post_close_null_when_no_trade():
    from inves_cog.ingest.market import post_close, split_factors

    bars = [{"ts_utc": instant("2026-10-28T19:59:00Z"), "close": 100, "volume": 3}]
    assert post_close(bars, date(2026, 10, 28)) is None
    bars += [
        {"ts_utc": instant("2026-10-29T00:00:00Z"), "close": 130, "volume": 5},
        {"ts_utc": instant("2026-10-28T22:00:00Z"), "close": 110, "volume": 0},
    ]
    assert post_close(bars, date(2026, 10, 28)) is None
    bars += [{"ts_utc": instant("2026-10-28T21:00:00Z"), "close": 105, "volume": 2}]
    assert post_close(bars, date(2026, 10, 28)) == 105
    mixed = [
        {"ticker": "ONE", "ts_utc": instant("2026-10-28T21:00:00Z"), "close": 105, "volume": 2},
        {"ticker": "TWO", "ts_utc": instant("2026-10-28T23:59:00Z"), "close": 999, "volume": 2},
    ]
    assert post_close(mixed, date(2026, 10, 28), ticker="ONE") == 105
    assert post_close(mixed, date(2026, 10, 28), ticker="MISSING") is None
    assert split_factors([date(2026, 10, 27), date(2026, 10, 28)], [{"date": date(2026, 10, 28), "ratio": 2}]) == [
        0.5,
        1.0,
    ]


def test_wide_universe_rules():
    from inves_cog.ingest.providers import Alpaca

    calls = []

    class Assets:
        def get(self, url, **kwargs):
            calls.append(url)
            return []

    Alpaca(clock=frozen(), key="fixture", secret="fixture", http=Assets()).assets()
    assert calls[-1] == "https://paper-api.alpaca.markets/v2/assets"
    Alpaca(
        clock=frozen(), key="fixture", secret="fixture", http=Assets(), assets_base_url="https://api.alpaca.markets"
    ).assets()
    assert calls[-1] == "https://api.alpaca.markets/v2/assets"
    with pytest.raises(ValueError):
        Alpaca(clock=frozen(), key="fixture", secret="fixture", assets_base_url="https://evil.invalid")

    from inves_cog.ingest.pipeline import select_membership

    candidate = {
        "ticker": "FIXTURE",
        "status": "active",
        "asset_class": "us_equity",
        "exchange": "NASDAQ",
        "name": "Fixture Common Stock",
        "cik": "1",
        "shares": 200_000_000,
        "close": 10,
        "history": [{"close": 10, "volume": 2_000_000} for _ in range(20)],
    }
    initial = select_membership([candidate], [], {"FIXTURE": 20_000_000}, date(2026, 10, 13), monthly=False)
    assert initial[0]["included"] and "startup_baseline" in initial[0]["notes"]
    removed = select_membership([candidate], initial, {"FIXTURE": 1}, date(2026, 10, 14), monthly=False)
    assert not removed[0]["included"]
    assert not select_membership([candidate], removed, {"FIXTURE": 30_000_000}, date(2026, 10, 15), monthly=False)[0][
        "included"
    ]
    refreshed = select_membership([candidate], removed, {"FIXTURE": 30_000_000}, date(2026, 11, 2), monthly=True)
    assert refreshed[0]["included"] and "startup_baseline" not in refreshed[0]["notes"]
    from inves_cog.ingest.runtime import complete_adv20

    sessions = [date(2026, 1, 1) + timedelta(days=i) for i in range(20)]
    rows = [{"trade_date": day, "close": 10, "volume": 2_000_000} for day in sessions]
    assert complete_adv20(rows, sessions) == 20_000_000
    assert complete_adv20(rows[:-1], sessions) is None
    assert complete_adv20(rows[:-1] + [rows[0]], sessions) is None
    assert complete_adv20([dict(row, volume=None) for row in rows], sessions) is None
    from inves_cog.ingest.universe import build_universe, daily_liquidity

    candidates = json.loads((FIXTURES / "m1/wide_candidates.json").read_text())
    rows = build_universe(candidates, date(2026, 10, 1))
    by_name = {r["ticker"]: r for r in rows}
    assert by_name["GOOD"]["included"]
    for ticker, reason in {
        "ETF": "non_common",
        "ADR": "non_common",
        "SMALL": "below_mktcap",
        "THIN": "below_adv",
        "MISSING": "no_shares",
        "NOCIK": "no_cik",
        "NOPRICE": "no_price",
        "SHORT": "insufficient_history",
    }.items():
        assert by_name[ticker]["exclude_reason"] == reason
        assert not by_name[ticker]["included"]
    assert "multi_class_approx" in by_name["CLASS.A"]["notes"]
    assert by_name["ETF"]["notes"]
    first = daily_liquidity(rows, {"GOOD": 19_999_999}, date(2026, 10, 2))
    second = daily_liquidity(first, {"GOOD": 100_000_000}, date(2026, 10, 5))
    assert not next(r for r in second if r["ticker"] == "GOOD")["included"]
    assert next(r for r in rows if r["ticker"] == "GOOD")["included"]


def test_news_dedupe_and_times():
    from tests.m1.round2_cases import assert_short_roots

    assert_short_roots(frozen())
    from inves_cog.ingest.info import source_root

    assert source_root("") is None and source_root("<p> </p>") is None
    assert source_root("", provider="Reuters", upstream_id="wire") == "Reuters:wire"
    assert source_root("0") is not None

    from inves_cog.ingest.jobs import HealthBook, JobRunner

    ticks = iter([0, 1901, 1901])
    ledger = []
    runner = JobRunner(
        clock=frozen(), health=HealthBook(clock=frozen()), persist=ledger.append, monotonic=lambda: next(ticks, 1901)
    )
    result = runner.run("fixture_timeout", "Fixture", lambda: {"processed_count": 3})
    assert result["status"] == "failed" and ledger[0]["processed_count"] == 3

    from inves_cog.ingest.http import SourceError
    from inves_cog.ingest.jobs import HealthBook
    from inves_cog.ingest.runtime import Runtime

    jobs, health = [], HealthBook(clock=frozen())

    def unavailable():
        raise SourceError("confirmed missing source", confirmed_unavailable=True)

    runtime = Runtime(
        clock=frozen(),
        health=health,
        persist_job=jobs.append,
        tasks={"bad": ("Broken", unavailable), "good": ("Healthy", lambda: {"processed_count": 2})},
    )
    output = runtime.run(["bad", "good"])
    assert output["bad"]["status"] == "failed" and output["good"]["processed_count"] == 2
    assert health.rows["Broken"]["status"] == "未接通"
    assert health.rows["Healthy"]["status"] == "ok" and len(jobs) == 2
    from inves_cog.ingest.info import InfoStore, make_item, source_root

    clock = frozen()
    store = InfoStore()
    item = make_item(
        "news",
        "Reuters",
        "a",
        headline="Growth",
        body="<p>Sales 10, not 20.</p>",
        clock=clock,
        published_at=instant("2026-10-28T17:00:00Z"),
    )
    assert store.put(item) == "inserted"
    assert store.put(deepcopy(item)) == "deduped"
    changed = deepcopy(item)
    changed.update(body="Sales 11, not 20.", published_at=instant("2026-10-28T18:00:00Z"))
    assert store.put(changed) == "deduped"
    assert len(store.items) == 1 and len(store.versions) == 1
    saved = store.items[item["info_id"]]
    assert saved["published_at"] == item["published_at"] and saved["first_seen_at"] == clock.now_utc()
    assert saved["source_root"] == item["source_root"]
    assert saved["body"] == changed["body"]
    assert source_root("<p>ＡＢＣ\n Sales 10, not 20.</p>") == source_root("ABC Sales 10, not 20.")
    assert source_root("Sales 10") != source_root("Sales 20")
    assert source_root("not increased") != source_root("increased")
    assert source_root("x", provider="Reuters", upstream_id="1") == "Reuters:1"
    assert source_root("different", provider="Reuters", upstream_id="1") == "Reuters:1"
    store.compact(instant("2027-02-01T00:00:00Z"))
    assert saved["body"] is None and saved["summary"] == changed["body"][:500]
    assert store.counts == {"collected": 3, "inserted": 1, "deduped": 2}


def test_earnings_reaction_day():
    from inves_cog.ingest.http import SourceError
    from inves_cog.ingest.sec import accepted_from_index, collect_submissions, earnings_event, parse_acceptance_et

    for case in load_golden("m1_earnings_sessions.json")["cases"]:
        accepted = parse_acceptance_et(case["accepted_at_et"])
        assert accepted == instant(case["accepted_at_utc"])
        event = earnings_event(
            {"ticker": "AAPL", "accession": "fixture", "form": "8-K", "items": ["2.02"], "accepted_at": accepted},
            closes={},
            clock=frozen(),
        )
        assert event["session"] == case["session"]
        assert event["reaction_day"] == date.fromisoformat(case["reaction_day"])
    assert earnings_event({"form": "10-Q", "items": ["2.02"]}, closes={}, clock=frozen()) is None
    assert earnings_event({"form": "8-K", "items": ["7.01"]}, closes={}, clock=frozen()) is None
    verified = json.loads((FIXTURES / "m1/sec_acceptance_conflict.json").read_text())
    assert verified["complete"] and len(verified["samples"]) == 3
    assert any(row["session_from_index"] == "post" for row in verified["samples"])
    for sample in verified["samples"]:
        html = f'<div class="infoHead">Accepted</div><div class="info">{sample["index_accepted_et"]}</div>'
        assert accepted_from_index(html) == instant(sample["accepted_at_utc_from_index"]), sample["accession"]
        with pytest.raises(ValueError):
            parse_acceptance_et(sample["submissions_acceptanceDateTime"])
    with pytest.raises(SourceError, match="Accepted"):
        accepted_from_index("<div>No acceptance field</div>")
    sample = verified["samples"][0]

    class RecordedSEC:
        def submissions(self, cik):
            return {
                "cik": cik,
                "filings": {
                    "recent": {
                        "accessionNumber": [sample["accession"], "0000320193-26-000017"],
                        "form": ["8-K", "8-K"],
                        "items": ["2.02,9.01", "2.02"],
                        "filingDate": ["2026-07-30", "2026-07-29"],
                        "acceptanceDateTime": [
                            sample["submissions_acceptanceDateTime"],
                            sample["submissions_acceptanceDateTime"],
                        ],
                    }
                },
            }

        def get(self, url):
            if sample["accession"] in url:
                return f'<div class="infoHead">Accepted</div><div class="info">{sample["index_accepted_et"]}</div>'
            raise SourceError("Recorded index unavailable", status_code=503)

    rows = collect_submissions(RecordedSEC(), cik="0000320193", ticker="AAPL", clock=frozen())
    assert rows[0]["accepted_at"] == instant(sample["accepted_at_utc_from_index"])
    assert rows[0]["raw"]["acceptanceDateTime"] == sample["submissions_acceptanceDateTime"]
    assert rows[0]["raw"]["accepted_index_source"]["verified"] is True
    assert rows[1]["accepted_at"] is None
    assert rows[1]["raw"]["accepted_index_source"]["verified"] is False
    assert rows[1]["raw"]["accepted_index_source"]["http_status"] == 503
    with pytest.raises(SourceError, match="acceptance"):
        earnings_event(rows[1], closes={}, clock=frozen())


def test_earnings_fallback_flag():
    from inves_cog.ingest.pipeline import Pipeline

    calls = []

    class SEC:
        def get(self, url):
            calls.append(url)
            return (
                "8-K Fixture Corporation 1 2026-10-29 edgar/data/1/0000000001-26-000001.txt"
                if url.endswith(".idx")
                else "Full filing: guidance raised."
            )

    class Repo:
        def info_signature(self, identifier):
            return ("Atom title", "Atom metadata summary")

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.clock = frozen()
    pipeline.day_override = date(2026, 10, 30)
    pipeline.sec = SEC()
    pipeline.repo = Repo()
    captured = []
    pipeline.info = lambda items: captured.extend(items)
    pipeline.index()
    assert captured[0]["body"] == "Full filing: guidance raised." and any(url.endswith(".txt") for url in calls)

    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.sec_client import SECClient

    client = SECClient(
        user_agent="fixture test@example.invalid", http=HTTPClient(lambda *a, **k: Response(200, "fixture schema"))
    )
    assert client.get("https://xbrl.sec.gov/dei/2025/dei.xsd") == "fixture schema"
    with pytest.raises(ValueError):
        client.get("https://xbrl.sec.gov.evil.invalid/dei.xsd")
    with pytest.raises(ValueError):
        client.get("http://xbrl.sec.gov/dei.xsd")
    from inves_cog.ingest.sec import earnings_fallback

    uncertain = earnings_fallback("AAPL", {"reportDate": "2026-10-29"}, clock=frozen())
    assert uncertain["fallback"] and uncertain["session"] is None and uncertain["reaction_day"] is None
    assert {"earnings_event_fallback", "earnings_event_time_unknown"} <= set(uncertain["flags"])
    assert earnings_fallback("AAPL", {"reportDate": "2026-10-30", "session": "post"}, clock=frozen())[
        "reaction_day"
    ] == date(2026, 11, 2)


def test_form4_parse_code_p(tmp_path):
    import gzip
    import hashlib

    from inves_cog.ingest.history import form4_record, history_item, read_exports

    body = (
        b"ticker,filed,txn_date,code,shares,price,owner,is_officer,is_director\n"
        b"AAPL,2026-10-07,2026-10-06,P,100,10.5,Fixture,t,f\n"
    )
    archive = tmp_path / "insider.csv.gz"
    archive.write_bytes(gzip.compress(body))
    manifest = {
        "tables": [
            {
                "table": "data.insider_transactions",
                "file": archive.name,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "rows": 1,
            }
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    records = list(read_exports(tmp_path))
    assert len(records) == 1
    archived = history_item(records[0], clock=frozen())
    assert archived["kind"] == "form4" and archived["published_at"] is None
    assert {"published_at_missing", "visibility_time_unknown", "accession_missing"} <= set(archived["flags"])

    row = form4_record(records[0], clock=frozen())
    assert row["transaction_code"] == "P" and row["is_officer"] is True
    assert row["filed_at"] is None and row["accession"] is None
    assert row["raw"]["filed"] == "2026-10-07" and "visibility_time_unknown" in row["raw"]["import_flags"]
    assert row["event_id"] == form4_record(records[0], clock=frozen())["event_id"]
    manifest["tables"][0]["rows"] = 2
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="row count"):
        list(read_exports(tmp_path))
    manifest["tables"][0]["rows"] = 1
    manifest["tables"][0]["file"] = "../outside.csv.gz"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="filename"):
        list(read_exports(tmp_path))

    from inves_cog.ingest.sec import parse_form4

    text = (FIXTURES / "m1/form4_synthetic.xml").read_text()
    rows = parse_form4(text, accession="fixture-form4", filed_at=instant("2026-10-28T15:00:00Z"))
    assert len(rows) == 2
    assert rows[0]["transaction_code"] == "P" and rows[0]["is_officer"] is True
    assert rows[0]["shares"] == 100 and rows[0]["price"] == 10.5
    assert rows[0]["filed_at"] == instant("2026-10-28T15:00:00Z")
    assert rows[1]["price"] is None and rows[1]["transaction_code"] == "S"
    evidence = json.loads((FIXTURES / "m1/form4_official.json").read_text())
    actual = parse_form4(
        (FIXTURES / "m1/form4_official.xml").read_text(),
        accession=evidence["accession"],
        filed_at=instant(evidence["accepted_at"]),
    )
    assert len(actual) == 1 and actual[0]["transaction_code"] == "S" and actual[0]["is_officer"] is True
    assert actual[0]["shares"] == 2399 and actual[0]["price"] == 332.01
    assert actual[0]["filed_at"] == instant("2026-10-08T22:30:32Z")


def test_app_rank_jump():
    from inves_cog.ingest.signals import rank_jumps

    rows = rank_jumps({"app": 45}, {"app": 24}, chart="free", clock=frozen())
    assert len(rows) == 1 and rows[0]["kind"] == "app_rank"
    assert rank_jumps({"app": 45}, {"app": 25}, chart="free", clock=frozen()) == []
    assert len(rank_jumps({}, {"app": 80}, chart="grossing", clock=frozen())) == 1
    assert rank_jumps({}, {"app": 81}, chart="grossing", clock=frozen()) == []


def test_trends_unavailable_marked():
    from tests.m1.round2_cases import assert_trend_isolation

    assert_trend_isolation(frozen())
    from inves_cog.ingest.live import validate_smoke

    bars = {"daily_codes": 73}
    validate_smoke(bars, {"processed_count": 1}, {"Fixture": {"status": "ok"}}, required_sources={"Fixture"})
    with pytest.raises(RuntimeError):
        validate_smoke(bars, {"processed_count": 1}, {}, required_sources={"Fixture"})
    with pytest.raises(RuntimeError):
        validate_smoke({"daily_codes": 72}, {"processed_count": 1}, {"Fixture": {}}, required_sources={"Fixture"})
    with pytest.raises(RuntimeError):
        validate_smoke(bars, {"processed_count": 0}, {"Fixture": {}}, required_sources={"Fixture"})

    from inves_cog.ingest.jobs import HealthBook
    from inves_cog.ingest.signals import collect_trends, trend_event

    health = HealthBook(clock=frozen())

    def broken(*args):
        from inves_cog.ingest.http import SourceError

        raise SourceError("confirmed source unusable", confirmed_unavailable=True)

    rows = collect_trends(["fixture"], fetch=broken, health=health, clock=frozen())
    assert rows == [] and health.rows["GoogleTrends"]["status"] == "未接通"
    days = [{"date": date(2026, 10, 28) - timedelta(days=i), "value": 10} for i in range(1, 91)]
    assert trend_event("fixture", days, 31, clock=frozen("2026-10-28T15:00:00Z"))["kind"] == "trend"
    assert trend_event("fixture", days, 30, clock=frozen("2026-10-28T15:00:00Z")) is None
    assert trend_event("fixture", days[:59], 100, clock=frozen("2026-10-28T15:00:00Z")) is None
    assert trend_event("fixture", [dict(day, value=0) for day in days], 1, clock=frozen("2026-10-28T15:00:00Z")) is None
    health.record("source", success=True, count=3)
    assert health.rows["source"]["status"] == "ok"
    health.record("source", success=False)
    assert health.rows["source"]["status"] == "ok"
    health.record("source", success=False)
    assert health.rows["source"]["status"] == "degraded"
    health.clock = frozen("2026-10-31T00:30:00Z")
    health.record("source", success=False)
    assert health.rows["source"]["status"] == "unavailable"
    health.record("source", success=True)
    assert health.rows["source"]["status"] == "ok"


def test_source_level_mapping():
    from tests.m1.round2_cases import assert_public_rss

    assert_public_rss(frozen())
    from inves_cog.ingest.repository import normalize_entity

    row = normalize_entity(
        {
            "entity_id": "fixture",
            "name": "Fixture",
            "aliases": ["F"],
            "ticker": "AAPL",
            "app_store_ids": ["app"],
            "trend_keywords": ["Fixture"],
            "official_urls": ["https://example.invalid"],
        }
    )
    assert row["tickers"] == ["AAPL"] and row["app_ids"] == ["app"] and row["trends_keywords"] == ["Fixture"]
    restricted = normalize_entity(
        {
            "entity_id": "fixture",
            "name": "Fixture",
            "channels": ["site"],
            "app_store_ids": ["app"],
            "trend_keywords": ["Fixture"],
            "official_urls": ["https://example.invalid"],
        }
    )
    assert restricted["app_ids"] == [] and restricted["trends_keywords"] == [] and restricted["urls"]
    with pytest.raises(ValueError):
        normalize_entity({"entity_id": "", "name": "Invalid"})
    from inves_cog.ingest.info import source_level

    for source in ("SEC", "CompanyIR", "Government", "CentralBank"):
        assert source_level(source) == 1
    for source in ("Reuters", "Bloomberg", "WSJ", "FT", "CNBC", "AP"):
        assert source_level(source) == 2
    assert source_level("SellSide") == 3 and source_level("unknown") == 4
    entities = yaml.safe_load((ROOT / "config/monitored_entities.yaml").read_text())["entities"]
    assert entities and all(
        {"entity_id", "name", "aliases", "tickers", "app_ids", "trends_keywords", "urls"} <= row.keys()
        for row in entities
    )
    universe = yaml.safe_load((ROOT / "config/universe.yaml").read_text())
    assert len(universe["stocks"]) == 59 and len(universe["etfs"]) == 14


def test_info_item_contract(tmp_path):
    from tests.m1.triage_cases import assert_news_triage

    assert_news_triage(tmp_path / "triage-recordings", frozen())
    from tests.m1.round2_cases import assert_site_isolation

    assert_site_isolation(frozen())
    from inves_cog.ingest.info import make_item
    from inves_cog.ingest.pipeline import Pipeline

    calls = []
    from inves_cog.llm.client import Client

    recorded = Client(registry=ROOT / "config/llm_tasks.yaml", recordings=FIXTURES / "recordings")

    class LLM:
        def call(self, task, payload):
            calls.append(task)
            return recorded.call(task, payload)

    class Queue:
        def __init__(self):
            self.rows = {}
            self.collected = 0

        def info_signature(self, identifier):
            row = self.rows.get(identifier)
            return (row["headline"], row["body"]) if row else None

        def put_info(self, row):
            self.rows[row["info_id"]] = row
            self.collected += 1

        def count_duplicate(self):
            self.collected += 1

        def pending_info(self, limit, *, as_of):
            return [row for row in self.rows.values() if row["extraction_status"] == "pending"][:limit]

        def apply_enrichment(self, row):
            self.rows[row["info_id"]] = row
            return True

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.repo = Queue()
    pipeline.clock = frozen()
    pipeline.llm = LLM()
    pipeline.embed = lambda *args, **kw: [0.1] * 1024
    pipeline.entities = []
    from inves_cog.ingest.triage import NewsTriage

    pipeline.triage = NewsTriage(
        llm=pipeline.llm,
        embed=pipeline.embed,
        entities=[],
        monitored_ids=set(),
        pool_tickers={"AAPL"},
        clock=pipeline.clock,
    )
    raw = make_item(
        "news",
        "Fixture",
        "queued",
        headline="Apple raises guidance",
        body="AAPL raises guidance; a broker raises its rating. Published 2026-10-28T16:00:00Z.",
        tickers=["AAPL"],
        clock=frozen(),
    )
    pipeline.info([raw])
    assert not calls
    assert pipeline.repo.rows[raw["info_id"]]["extraction_status"] == "pending"
    result = pipeline.enrich_pending()
    assert result["processed_count"] == 1 and pipeline.repo.rows[raw["info_id"]]["extraction_status"] == "ok"
    assert pipeline.repo.collected == 1 and len(calls) == 2
    pipeline.info([raw])
    assert pipeline.repo.collected == 2 and len(calls) == 2

    from inves_cog.ingest.info import InfoStore, enrich, make_item
    from inves_cog.ingest.sources import fred_observations, parse_cboe, parse_finra, website_change

    item = make_item("news", "unknown", "1", headline="Unimportant update", body="x" * 600, clock=frozen())
    assert item["info_id"] == "news:unknown:1"
    assert item["published_at"] is None and "published_at_missing" in item["flags"]
    assert item["summary"] == "x" * 500 and item["embedding"] is None and item["extraction_status"] == "pending"
    assert item["first_seen_at"].utcoffset().total_seconds() == 0
    with pytest.raises(ValueError):
        make_item("not-a-kind", "unknown", "1", headline="x", body="x", clock=frozen())
    from inves_cog.ingest.adapters import cboe_statistics

    class CBOE:
        def get(self, *args, **kw):
            return (
                '<input value="2026-10-28"><table><tr><th colspan="4">SUM OF ALL PRODUC'
                "TS</th></tr><tr><th>Name</th><th>Call</th><th>Put</th><th>Total</th></"
                "tr><tr><td>VOLUME</td><td>100</td><td>50</td><td>150</td></tr><tr><td>"
                "OPEN INTEREST</td><td>200</td><td>100</td><td>300</td></tr></table>"
            )

    from inves_cog.ingest.http import SourceError

    with pytest.raises(SourceError, match="date"):
        cboe_statistics(CBOE(), date(2026, 10, 29))
    statistics = cboe_statistics(CBOE(), date(2026, 10, 28))
    assert statistics[0]["category"] == "total" and statistics[0]["call_volume"] == 100
    assert statistics[0]["put_call_ratio"] == 0.5 and statistics[0]["open_interest"] == 300

    class Rounded(CBOE):
        def get(self, *args, **kwargs):
            return "<table><tr><td>TOTAL PUT/CALL RATIO</td><td>0.33</td></tr></table>" + super().get(
                *args, **kwargs
            ).replace("<td>100</td>", "<td>3</td>").replace("<td>50</td>", "<td>1</td>")

    assert cboe_statistics(Rounded(), date(2026, 10, 28))[0]["put_call_ratio"] == 0.33

    from inves_cog.ingest.providers import finra_short_interest

    class FINRA:
        def request(self, method, url, *, json, headers):
            assert json["domainFilters"] == [{"fieldName": "symbolCode", "values": ["AAPL"]}]
            assert headers["Accept"] == "application/json"
            return [
                {
                    "symbolCode": "AAPL",
                    "marketClassCode": "NASDAQ",
                    "settlementDate": "2026-10-15",
                    "currentShortPositionQuantity": 10,
                    "averageDailyVolumeQuantity": 2,
                }
            ]

    listed = finra_short_interest(FINRA(), tickers=["AAPL"])
    assert parse_finra(listed, allowed_tickers={"AAPL"})[0]["days_to_cover"] == 5
    assert parse_finra([{"symbolCode": "AAPL", "marketClassCode": "OTC"}], allowed_tickers={"AAPL"}) == []

    class OTC:
        def request(self, *args, **kw):
            return [{"symbolCode": "AAPL", "marketClassCode": "OTC"}]

    with pytest.raises(SourceError, match="coverage"):
        finra_short_interest(OTC(), tickers=["AAPL"])

    data = {
        "observations": [
            {"date": "2026-10-01", "realtime_start": "2026-10-02", "value": "."},
            {"date": "2026-10-01", "realtime_start": "2026-10-03", "value": "2.5"},
        ]
    }
    observations = fred_observations("DGS2", data, units="Percent", clock=frozen())
    assert observations[0]["value"] is None and observations[1]["value"] == 2.5
    assert observations[0]["realtime_start"] != observations[1]["realtime_start"]
    assert (
        parse_finra(
            [{"symbolCode": "AAPL", "issueExchange": "OTC", "currentShortPositionQuantity": 10}],
            allowed_tickers={"AAPL"},
        )
        == []
    )
    assert (
        parse_finra(
            [
                {
                    "symbolCode": "AAPL",
                    "issueExchange": "NASDAQ",
                    "currentShortPositionQuantity": 10,
                    "averageDailyVolumeQuantity": 0,
                }
            ],
            allowed_tickers={"AAPL"},
        )[0]["days_to_cover"]
        is None
    )
    assert (
        parse_cboe("category,call_volume,put_volume,open_interest\nequity,100,50,\n", date(2026, 10, 28))[0][
            "open_interest"
        ]
        is None
    )
    assert website_change("https://example.invalid", "<p>unchanged</p>", "<p>unchanged</p>", clock=frozen()) is None
    assert (
        website_change("https://example.invalid", "<p>old 1</p>", "<p>new 2</p>", clock=frozen())["kind"]
        == "site_change"
    )
    calls = []

    class Embed:
        def __call__(self, text, **kwargs):
            calls.append((text, kwargs))
            return [0.1] * 1024

    class LLM:
        def call(self, task, payload):
            return {"entities": []} if task == "entity_tagging" else {"is_guidance": False, "is_rating_change": False}

    enriched = enrich(item, llm=LLM(), embed=Embed(), entities=[], clock=frozen())
    assert len(enriched["embedding"]) == 1024 and calls[0][1]["dimensions"] == 1024
    assert calls[0][1]["model"] == "text-embedding-v3"
    assert enriched["is_guidance"] is False and enriched["is_rating_change"] is False
    store = InfoStore()
    assert store.put(enriched) == "inserted"
    from inves_cog.ingest.settings import read_environment, source_configuration

    configuration = tmp_path / "credentials.env"
    configuration.write_text(
        "ALPACA_API_KEY_ID=fixture-key\n"
        'ALPACA_API_SECRET_KEY="fixture-secret"\n'
        'SEC_EDGAR_USER_AGENT="fixture contact@example.invalid"\n'
        "ALPACA_DATA_FEED=iex\n"
        "FRED_API_KEY=fixture-fred # local comment\n"
        'LLM_STANDARD_API_KEY="$(not-executed)"\n'
    )
    values = read_environment(configuration, environ={})
    assert values["APCA_API_KEY_ID"] == "fixture-key"
    assert values["APCA_API_SECRET_KEY"] == "fixture-secret"
    assert values["SEC_USER_AGENT"] == "fixture contact@example.invalid"
    assert values["FRED_API_KEY"] == "fixture-fred"
    assert values["LLM_STANDARD_API_KEY"] == "$(not-executed)"
    report = source_configuration(values)
    assert report["Alpaca"]["configured"] and report["Alpaca"]["feed"] == "sip"
    assert report["SEC"]["configured"]
    assert not report["DashScope"]["configured"]
    assert report["DashScope"]["missing"] == ["DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"]
    assert "fixture-secret" not in json.dumps(report)
    assert "fixture-key" not in json.dumps(report)
    from inves_cog.ingest.http import HTTPClient, Response
    from inves_cog.ingest.providers import FRED

    requests = []

    def fred_response(method, url, **kwargs):
        requests.append(kwargs["params"])
        if url.endswith("/series"):
            return Response(200, {"realtime_end": "2026-10-13", "seriess": [{"units": "Percent"}]})
        assert kwargs["params"]["output_type"] == 1
        offset = kwargs["params"].get("offset", 0)
        return Response(
            200,
            {
                "count": 2,
                "observations": [{"date": "2026-10-01", "realtime_start": f"2026-10-{12 + offset}", "value": "2.5"}],
            },
        )

    fred = FRED(key="fixture-key", clock=frozen("2026-10-14T04:03:00Z"), http=HTTPClient(fred_response))
    records = fred.collect("DGS2")
    assert all(request["realtime_end"] == "2026-10-13" for request in requests[1:])
    assert len(records) == 2 and records[0]["realtime_start"] != records[1]["realtime_start"]
    assert requests[-1]["offset"] == 1
    requests.clear()
    fred.clock = frozen("2026-10-10T12:00:00Z")
    fred.collect("DGS2")
    assert all(request["realtime_end"] == "2026-10-10" for request in requests[1:])
    requests = []
    from inves_cog.ingest.http import SourceError

    class ManyVintages:
        def get(self, url, params):
            requests.append(dict(params))
            if url.endswith("/series"):
                return {"realtime_end": "2026-10-13", "seriess": [{"units": "Percent"}]}
            if url.endswith("/vintagedates"):
                return {"count": 4, "vintage_dates": ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-14"]}
            assert params["output_type"] == 1
            if params["realtime_end"] == "2026-10-13":
                raise SourceError("too many vintage dates", status_code=400)
            values = {"2026-10-01": "2.0", "2026-10-02": ".", "2026-10-03": "2.2"}
            rows = [
                {"date": "2026-09-30", "realtime_start": d, "value": value}
                for d, value in values.items()
                if params["realtime_start"] <= d <= params["realtime_end"]
            ]
            return {"count": len(rows), "observations": rows}

    vintage = FRED(key="fixture", clock=frozen("2026-10-14T04:03:00Z"), http=ManyVintages())
    vintage.vintage_batch_size = 2
    observations = vintage.collect("DGS2")
    assert [r["realtime_start"] for r in observations] == [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]
    assert [r["value"] for r in observations] == [2.0, None, 2.2]
    configuration.write_text("APCA_API_KEY_ID=a\nALPACA_API_KEY_ID=b\n")
    with pytest.raises(ValueError, match="conflicting.*APCA_API_KEY_ID"):
        read_environment(configuration, environ={})
    configuration.write_text("not an assignment\n")
    with pytest.raises(ValueError, match="line 1"):
        read_environment(configuration, environ={})


def test_info_fields_extraction(tmp_path):
    from tests.m1.usage_cases import assert_usage_accounting

    assert_usage_accounting(tmp_path / "usage-recordings", frozen())
    from inves_cog.ingest.info import enrich, make_item
    from inves_cog.llm.client import Client

    llm = Client(registry=ROOT / "config/llm_tasks.yaml", recordings=FIXTURES / "recordings")
    item = make_item(
        "news",
        "Reuters",
        "fixture",
        headline="Apple raises guidance",
        body="AAPL raises guidance; a broker raises its rating. Published 2026-10-28T16:00:00Z.",
        clock=frozen(),
    )
    result = enrich(item, llm=llm, embed=None, entities=[], clock=frozen())
    assert result["is_guidance"] is True and result["guidance_direction"] == "up" and result["is_rating_change"] is True
    assert result["published_at"] == instant("2026-10-28T16:00:00Z")
    assert "published_at_extracted" in result["flags"] and "published_at_missing" not in result["flags"]
    assert result["extraction_source"]["is_guidance"] == "llm"
    assert result["entities"] == ["apple"]
    wrapped = dict(
        item,
        body="<style>" + ("irrelevant CSS " * 500) + "</style><script>ignored code</script><p>" + item["body"] + "</p>",
    )
    assert enrich(wrapped, llm=llm, embed=None, entities=[], clock=frozen())["is_guidance"] is True


def test_llm_extraction_failure_degrades():
    from tests.m1.round2_cases import assert_embedding_auth_isolation

    assert_embedding_auth_isolation()
    from fastapi.testclient import TestClient

    from inves_cog.ingest.health import create_app, extraction_counts

    assert extraction_counts([{"flags": ["embedding_failed"]}, {"flags": []}]) == {
        "total": 2,
        "embedding_failed": 1,
        "entity_tagging_failed": 0,
        "embedding_failure_rate": 0.5,
        "entity_tagging_failure_rate": 0.0,
    }
    assert extraction_counts([])["embedding_failure_rate"] is None
    assert extraction_counts([{"flags": [], "extraction_status": "pending"}])["embedding_failure_rate"] is None
    assert (
        extraction_counts(
            [{"flags": [], "extraction_status": "pending"}, {"flags": ["embedding_failed"], "extraction_status": "ok"}]
        )["embedding_failure_rate"]
        == 1
    )

    from contextlib import contextmanager

    class Connection:
        def execute(self, sql, *args):
            return self

        def fetchall(self):
            return [{"flags": ["embedding_failed", "entity_tagging_failed"]}]

    @contextmanager
    def connection():
        yield Connection()

    with TestClient(create_app(connection)) as probe:
        result = probe.get("/health/extraction")
        assert result.status_code == 200 and result.json()["embedding_failed"] == 1

    from inves_cog.ingest.info import InfoStore, enrich, make_item
    from inves_cog.llm.client import Client, LLMUnavailable

    item = make_item(
        "news", "Reuters", "failure", headline="Fixture failure", body="Retain all information", clock=frozen()
    )
    llm = Client(registry=ROOT / "config/llm_tasks.yaml", recordings=FIXTURES / "recordings")
    result = enrich(item, llm=llm, embed=lambda *a, **k: None, entities=[], clock=frozen())
    from tests.m1.round2_cases import assert_failure_reasons

    assert_failure_reasons(result)
    assert result["extraction_status"] == "failed"
    assert result["is_guidance"] is None and result["is_rating_change"] is None
    assert result["embedding"] is None and "embedding_failed" in result["flags"]
    store = InfoStore()
    assert store.put(result) == "inserted" and result["body"] == item["body"]
    calls = []

    def fails(spec, payload):
        calls.append(spec)
        raise LLMUnavailable("fixture timeout")

    client = Client(registry=ROOT / "config/llm_tasks.yaml", transport=fails)
    with pytest.raises(LLMUnavailable):
        client.call("entity_tagging", {})
    assert len(calls) == 3 and calls[0].timeout_seconds == 120
    assert calls[0].task == "entity_tagging"
    calls.clear()
    with pytest.raises(LLMUnavailable):
        client.call("segment_mapping_draft", {})
    assert len(calls) == 1 and calls[0].timeout_seconds == 900
    assert calls[0].task == "segment_mapping_draft"
    from inves_cog.ingest.settings import source_configuration

    configuration = {}
    for prefix in ("LLM_HARD", "LLM_STANDARD"):
        configuration.update(
            {
                prefix + "_PROVIDER": "aliyun",
                prefix + "_BASE_URL": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
                prefix + "_API_STYLE": "openai-compatible",
                prefix + "_API_KEY": "fixture-not-a-key",
            }
        )
    assert source_configuration(configuration)["LLM_hard"]["configured"]
    assert source_configuration(configuration)["LLM_standard"]["configured"]
    attempts = []
    from inves_cog.ingest.http import Response

    def denied(*args, **kwargs):
        attempts.append(1)
        return Response(401, {})

    auth = Client.from_environment(configuration, send=denied)
    with pytest.raises(LLMUnavailable):
        auth.call("entity_tagging", {})
    assert len(attempts) == 1

    from inves_cog.llm.transport import OpenAICompatibleTransport

    recorded_payload = {"headline": "Apple introduces a product", "body": "AAPL"}
    recorded = llm.call("entity_tagging", recorded_payload)
    requests = []

    def recorded_response(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return Response(200, {"choices": [{"message": {"content": json.dumps(recorded)}}]})

    connected = Client(transport=OpenAICompatibleTransport(configuration, send=recorded_response))
    assert connected.call("entity_tagging", recorded_payload) == recorded
    assert connected.call("segment_mapping_draft", recorded_payload) == recorded
    assert [row[2]["json"]["model"] for row in requests] == ["deepseek-v4.1-flash", "glm-5.3"]
    assert [row[2]["timeout"] for row in requests] == [120, 900]
    assert all(row[1].endswith("/compatible-mode/v1/chat/completions") for row in requests)
    assert all("fixture-not-a-key" not in json.dumps(row[2]["json"]) for row in requests)
    requests.clear()

    def rate_limited(method, url, **kwargs):
        requests.append((method, url, kwargs))
        return Response(429, {"error": {"message": "recorded rate limit"}})

    connected = Client(transport=OpenAICompatibleTransport(configuration, send=rate_limited))
    with pytest.raises(LLMUnavailable):
        connected.call("entity_tagging", recorded_payload)
    assert len(requests) == 3
    requests.clear()
    with pytest.raises(LLMUnavailable):
        connected.call("segment_mapping_draft", recorded_payload)
    assert len(requests) == 1
