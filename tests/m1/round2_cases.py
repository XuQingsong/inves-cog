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
