"""Round-two assertions called from the original M1 test names."""

from datetime import timedelta


def assert_short_roots(clock):
    from inves_cog.ingest.info import make_item, source_root

    template = "Calendar placeholder " * 8
    first = make_item("news", "Benzinga", "5", headline="Earnings Scheduled For October 5", body=template, clock=clock)
    second = make_item(
        "news", "Benzinga", "12", headline="Earnings Scheduled For October 12", body=template, clock=clock
    )
    assert first["source_root"] != second["source_root"]
    assert source_root("<p>ＡＢＣ 10</p>", headline="Same Ｔitle") == source_root("ABC 10", headline="Same Title")
    assert source_root("a" * 299, headline="first") != source_root("a" * 299, headline="second")
    assert source_root("a" * 300, headline="first") == source_root("a" * 300, headline="second")
    assert source_root("short", headline="first", provider="Reuters", upstream_id="1") == source_root(
        "other", headline="second", provider="Reuters", upstream_id="1"
    )
    assert source_root("", headline="A title") is None


def assert_trend_isolation(clock):
    from inves_cog.ingest.jobs import HealthBook
    from inves_cog.ingest.signals import collect_trends

    today = clock.now_utc().date()
    history = [{"date": today - timedelta(days=i), "value": 10} for i in range(1, 91)]
    calls = []

    def fetch(keyword):
        calls.append(keyword)
        if keyword == "bad":
            raise TimeoutError("handwritten keyword timeout")
        return {"history": history, "today": 31}

    health = HealthBook(clock=clock)
    result = collect_trends(["good", "bad", "also-good"], fetch=fetch, health=health, clock=clock)
    assert len(result) == 2 and calls == ["good", "bad", "also-good"]
    assert health.rows["GoogleTrends"]["status"] == "degraded"
    assert "bad" in health.rows["GoogleTrends"]["note"] and "TimeoutError" in health.rows["GoogleTrends"]["note"]

    from inves_cog.ingest.jobs import JobRunner
    from inves_cog.ingest.pipeline import Pipeline

    class Repository:
        def set_cursor(self, *args):
            pass

    class Trends:
        def get(self, keyword):
            return fetch(keyword)

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.clock = clock
    pipeline.repo = Repository()
    pipeline.trends = Trends()
    pipeline.monitored = [{"trends_keywords": ["bad"]}]
    pipeline.info = lambda rows: None
    health = HealthBook(clock=clock)
    runner = JobRunner(clock=clock, health=health, persist=lambda row: None)
    runner.run("trends", "GoogleTrends", pipeline.trends_task)
    assert health.rows["GoogleTrends"]["status"] == "degraded"
    assert health.rows["GoogleTrends"]["last_success_at"] is None
    pipeline.monitored = [{"trends_keywords": ["good", "bad", "also-good"]}]
    runner.run("trends", "GoogleTrends", pipeline.trends_task)
    assert health.rows["GoogleTrends"]["last_success_at"] == clock.now_utc()
    assert health.rows["GoogleTrends"]["items_last_run"] == 2


def assert_site_isolation(clock):
    from inves_cog.ingest.http import SourceError
    from inves_cog.ingest.pipeline import Pipeline

    class Repository:
        def __init__(self):
            self.health = {}
            self.snapshots = []

        def health_rows(self):
            return self.health

        def write_health(self, row):
            self.health[row["source"]] = row

        def latest_website(self, url):
            return None

        def write(self, table, row):
            self.snapshots.append(row)

    class Sites:
        def get(self, url):
            if "bad" in url:
                raise SourceError("handwritten HTTP 403", status_code=403, confirmed_unavailable=True)
            return "<html><body>Original site update</body></html>"

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.clock = clock
    pipeline.repo = Repository()
    pipeline.websites = Sites()
    items = []
    pipeline.info = lambda rows: items.extend(rows)
    pipeline.monitored = [
        {"urls": [f"https://{name}.example.invalid/news"]} for name in ["good", "bad", "third", "fourth", "fifth"]
    ]
    result = pipeline.websites_task()
    assert result["processed_count"] == 4 and result["status"] == "degraded"
    assert len(pipeline.repo.snapshots) == 4 and len(items) == 4
    assert len(pipeline.repo.health) == 5
    assert all(row["source"].startswith("EntitySites:") for row in pipeline.repo.health.values())
    assert all(item["source"] == "EntitySites" and item["source_level"] == 1 for item in items)


def assert_public_rss(clock):
    from inves_cog.ingest.rss import parse_rss

    xml = (
        "<rss><channel><item><guid>original-id</guid><title>Policy update</titl"
        "e><link>https://example.invalid/original</link><description>Original p"
        "olicy statement.</description><pubDate>Wed, 14 Oct 2026 12:00:00 GMT</"
        "pubDate></item></channel></rss>"
    )
    for source in ["FederalReserveNews", "EIANews", "EIATodayInEnergy"]:
        rows = parse_rss(xml, source=source, clock=clock)
        assert len(rows) == 1 and rows[0]["source_level"] == 1 and rows[0]["kind"] == "news"
        assert rows[0]["published_at"].utcoffset() == timedelta(0)
        assert rows[0]["source_root"] == source + ":original-id"
    rows = parse_rss(
        xml.replace("<pubDate>Wed, 14 Oct 2026 12:00:00 GMT</pubDate>", ""), source="FederalReserveNews", clock=clock
    )
    assert rows[0]["published_at"] is None and "published_at_missing" in rows[0]["flags"]


def assert_failure_reasons(result):
    errors = result["extraction_source"]["errors"]
    assert errors["entity_tagging"]["type"] and errors["entity_tagging"]["message"]
    assert errors["info_fields_extraction"]["type"] and errors["info_fields_extraction"]["message"]
    assert errors["embedding"]["type"] == "ValueError"


def assert_embedding_auth_isolation():
    from inves_cog.ingest.adapters import Embedding
    from inves_cog.ingest.http import HTTPClient, Response, SourceError

    requests = []

    def denied(*args, **kwargs):
        requests.append(1)
        return Response(401, {})

    configuration = {"DASHSCOPE_API_KEY": "fixture-not-a-key", "DASHSCOPE_BASE_URL": "https://example.invalid/v1"}
    adapter = Embedding(configuration, http=HTTPClient(denied, retries=0))
    for text in ["first", "second"]:
        try:
            adapter(text, model="text-embedding-v3", dimensions=1024)
        except SourceError as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("authentication failure must remain visible")
    assert len(requests) == 1
    responses = iter([Response(503, {}), Response(200, {"data": [{"embedding": [0.1] * 1024}]})])
    adapter = Embedding(configuration, http=HTTPClient(lambda *a, **k: next(responses), retries=0))
    try:
        adapter("transient", model="text-embedding-v3", dimensions=1024)
    except SourceError:
        pass
    assert adapter("recovered", model="text-embedding-v3", dimensions=1024) == [0.1] * 1024


def assert_embedding_batches():
    import math

    import pytest

    from inves_cog.ingest.adapters import Embedding
    from inves_cog.ingest.http import HTTPClient, Response, SourceError

    calls = []
    configuration = {"DASHSCOPE_API_KEY": "fixture-not-a-key", "DASHSCOPE_BASE_URL": "https://example.invalid/v1"}

    def send(*args, **kwargs):
        calls.append(kwargs["json"])
        return Response(
            200, {"data": [{"index": 1, "embedding": [0.2] * 1024}, {"index": 0, "embedding": [0.1] * 1024}]}
        )

    adapter = Embedding(configuration, http=HTTPClient(send, retries=0))
    assert adapter.batch(["first", "second"], model="text-embedding-v3", dimensions=1024) == [
        [0.1] * 1024,
        [0.2] * 1024,
    ]
    assert calls[0]["input"] == ["first", "second"]
    for payload in (
        {"data": [{"index": 0, "embedding": [0.1] * 1024}]},
        {"data": [{"index": 0, "embedding": [0.1] * 1024}] * 2},
        {"data": [{"index": 0, "embedding": [0.1] * 1024}, {"index": 2, "embedding": [0.1] * 1024}]},
        {"data": [{"index": 0, "embedding": [0.1] * 1023}, {"index": 1, "embedding": [0.1] * 1024}]},
        {"data": [{"index": 0, "embedding": [math.nan] * 1024}, {"index": 1, "embedding": [0.1] * 1024}]},
    ):
        broken = Embedding(configuration, http=HTTPClient(lambda *a, payload=payload, **k: Response(200, payload)))
        with pytest.raises(SourceError, match="Embedding"):
            broken.batch(["first", "second"], model="text-embedding-v3", dimensions=1024)
    before = len(calls)
    for texts in ([], ["x"] * 11, [""], [None]):
        with pytest.raises(ValueError):
            adapter.batch(texts, model="text-embedding-v3", dimensions=1024)
    assert len(calls) == before
    paused = Embedding({**configuration, "INVES_COG_EMBEDDING_ENABLED": "0"}, http=HTTPClient(send, retries=0))
    with pytest.raises(SourceError, match="paused"):
        paused.batch(["first", "second"], model="text-embedding-v3", dimensions=1024)
    assert len(calls) == before
    enabled = Embedding({**configuration, "INVES_COG_EMBEDDING_ENABLED": "1"}, http=HTTPClient(send, retries=0))
    assert enabled.batch(["first", "second"], model="text-embedding-v3", dimensions=1024)[1] == [0.2] * 1024
    from datetime import datetime, timezone

    from inves_cog.clock import FrozenClock

    records = []
    clock = FrozenClock(datetime(2026, 10, 15, tzinfo=timezone.utc))
    audited = Embedding(configuration, http=HTTPClient(send, retries=0), clock=clock, recorder=records.append)
    audited.batch(["first", "second"], model="text-embedding-v3", dimensions=1024)
    assert records[0]["task"] == "embedding" and records[0]["item_count"] == 2
    assert records[0]["input_tokens"] is None and records[0]["output_tokens"] == 0
    assert records[0]["status"] == "usage_missing"
    assert records[0]["created_at"] == clock.now_utc()
    from inves_cog.ingest.embedding_models import MODEL_DIMENSIONS

    for model in ("text-embedding-v1", "text-embedding-v2", "text-embedding-v4"):
        dimension = MODEL_DIMENSIONS[model]
        result = {"data": [{"index": 0, "embedding": [0.1] * dimension}], "usage": {"prompt_tokens": 7}}
        adapter = Embedding(
            configuration,
            http=HTTPClient(lambda *a, result=result, **k: Response(200, result)),
            clock=clock,
            recorder=records.append,
        )
        assert len(adapter("fixture", model=model, dimensions=dimension)) == dimension
        assert records[-1]["input_tokens"] == 7 and records[-1]["task"] == "embedding"
    from inves_cog.ingest.embedding_backfill import validate_async_row

    row = {"output": {"text_index": 0, "code": 200, "embedding": [0.1] * 1536}}
    assert validate_async_row(row, 1, 1536)[0] == 0
    for invalid in ({"output": {**row["output"], "text_index": 1}},
                    {"output": {**row["output"], "embedding": [math.nan] * 1536}}):
        with pytest.raises(ValueError):
            validate_async_row(invalid, 1, 1536)


def assert_scheduler_watchdog():
    from datetime import datetime

    from inves_cog.clock import FrozenClock
    from inves_cog.ingest.jobs import HealthBook, JobRunner
    from inves_cog.ingest.service import check_bars_start

    class Repo:
        def __init__(self):
            self.health = {}
            self.runs = {}

        def last_runs(self, **kwargs):
            return self.runs

        def health_rows(self):
            return self.health

        def write_health(self, row):
            self.health[row["source"]] = row

    repo = Repo()

    def at(text):
        return FrozenClock(datetime.fromisoformat(text))

    check_bars_start(repo, at("2026-10-16T00:29:59+00:00"))
    assert not repo.health
    check_bars_start(repo, at("2026-10-16T00:30:00+00:00"))
    assert repo.health["Scheduler:bars_full"]["status"] == "unavailable"
    repo.runs["bars_full"] = datetime.fromisoformat("2026-10-15T07:00:00+00:00")
    check_bars_start(repo, at("2026-10-16T00:30:01+00:00"))
    assert repo.health["Scheduler:bars_full"]["status"] == "unavailable"
    repo.runs["bars_full"] = datetime.fromisoformat("2026-10-16T00:20:00+00:00")
    check_bars_start(repo, at("2026-10-16T00:30:02+00:00"))
    assert repo.health["Scheduler:bars_full"]["status"] == "ok"
    repo.health.clear()
    check_bars_start(repo, at("2026-10-18T00:31:00+00:00"))
    assert not repo.health  # Saturday ET: no false alarm.
    check_bars_start(repo, at("2026-11-03T01:30:00+00:00"))
    assert repo.health["Scheduler:bars_full"]["status"] == "unavailable"
    events = []

    def start(row):
        events.append(("start", dict(row)))
        return 42

    def operation():
        assert events[0][0] == "start" and events[0][1]["ended_at"] is None
        return {"processed_count": 1}

    clock = at("2026-10-16T00:20:00+00:00")
    JobRunner(
        clock=clock,
        health=HealthBook(clock=clock),
        persist=lambda row: events.append(("end", dict(row))),
        persist_start=start,
    ).run("bars_full", "Alpaca", operation)
    assert events[1][1]["id"] == 42 and events[1][1]["status"] == "ok"
