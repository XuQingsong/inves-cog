"""A-022 news tiers, independent budgets, and queue priority."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.ingest.info import make_item
from inves_cog.ingest.triage import NewsTriage

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 10, 25, 15, tzinfo=timezone.utc)


class CountingModels:
    def __init__(self, *, material=()):
        self.material = set(material)
        self.calls = []
        self.embeddings = 0

    def call(self, task, payload):
        self.calls.append(task)
        if task == "entity_tagging":
            return {
                "items": [
                    {
                        "info_id": row["info_id"],
                        "entities": [],
                        "material": row["info_id"] in self.material,
                    }
                    for row in payload["items"]
                ]
            }
        if task == "news_card":
            return {"说了什么": "fixture", "行业": [], "名单内": [], "名单外": []}
        if task == "info_fields_extraction":
            return {"is_guidance": False, "is_rating_change": False}
        raise AssertionError(task)

    def embed(self, *args, **kwargs):
        self.embeddings += 1
        return [0.1] * 1024


def item(identifier, source, headline, *, tickers=(), kind="news", minutes=0, body="fixture body"):
    return make_item(
        kind,
        source,
        identifier,
        headline=headline,
        body=body,
        tickers=tickers,
        published_at=NOW - timedelta(minutes=minutes),
        clock=FrozenClock(NOW),
    )


def engine(models, *, stats=None, cached_root=None, **kwargs):
    entities = [
        {"entity_id": "openai", "name": "OpenAI", "aliases": ["ChatGPT"], "tickers": []},
        {"entity_id": "nvidia", "name": "NVIDIA", "aliases": [], "tickers": ["NVDA"]},
    ]
    return NewsTriage(
        llm=models,
        embed=models.embed,
        entities=entities,
        monitored_ids={"openai"},
        pool_tickers={"NVDA", "AAPL"},
        clock=FrozenClock(NOW),
        usage_today=lambda: stats or {"tokens": 0, "missing": 0, "full_items": 0, "screen_calls": 0},
        cached_root=cached_root,
        **kwargs,
    )


def meta(row):
    return row["extraction_source"]["news_triage"]


def test_a022_tiers_route_real_source_shapes_and_c_uses_no_model():
    fiscal_low = item("fiscal-low", "fiscal.ai", "Automated filing recap")
    fiscal_pool = item("fiscal-pool", "fiscal.ai", "NVIDIA results", tickers=["NVDA"])
    benzinga_pool = item("bz-pool", "benzinga", "Apple supplier update", tickers=["AAPL"])
    benzinga_macro = item("bz-cpi", "benzinga", "CPI surprises as Fed meets")
    benzinga_other = item("bz-other", "benzinga", "Local retail opening")
    sec = item("sec", "SEC", "Issuer files material 8-K", kind="sec_8k")
    monitored = item("monitored", "fiscal.ai", "OpenAI releases a product")
    held = item("held", "fiscal.ai", "Held company update", tickers=["XYZ"])
    held["extraction_source"] = {"news_queue": {"holding_related": True}}
    models = CountingModels(material={benzinga_other["info_id"]})

    rows = engine(models).process(
        [fiscal_low, fiscal_pool, benzinga_pool, benzinga_macro, benzinga_other, sec, monitored, held]
    )

    assert [meta(row)["tier"] for row in rows] == ["C", "A", "A", "A", "A", "A", "A", "A"]
    assert meta(rows[0])["reason"] == "rules_only_low_value"
    assert rows[0]["extraction_status"] == "ok" and rows[0]["embedding"] is None
    assert models.calls.count("entity_tagging") == 1
    assert models.calls.count("news_card") == 7
    assert models.calls.count("info_fields_extraction") == 0
    assert meta(rows[4])["screened"] and meta(rows[4])["material"]


def test_a022_b_nonmaterial_stays_rules_only_after_one_screen_call():
    row = item("bz-low", "benzinga", "Community calendar update")
    models = CountingModels()
    result = engine(models).process([row])[0]
    assert meta(result)["tier"] == "B"
    assert meta(result)["reason"] == "screening_not_material"
    assert result["extraction_status"] == "ok"
    assert models.calls == ["entity_tagging"]


def test_a022_duplicate_root_reuses_evidence_without_model_calls():
    previous = item("previous", "benzinga", "NVIDIA duplicate", tickers=["NVDA"])
    previous["extraction_status"] = "ok"
    previous["source_root"] = "provider:shared"
    previous["extraction_source"] = {"news_triage": {"tier": "C", "layer": 3, "rule_entities": ["nvidia"]}}
    duplicate = item("duplicate", "fiscal.ai", "Reposted NVIDIA duplicate", tickers=["NVDA"])
    duplicate["source_root"] = "provider:shared"
    models = CountingModels()
    result = engine(models, cached_root=lambda root: previous).process([duplicate])[0]
    assert meta(result)["tier"] == "C"
    assert meta(result)["reason"] == "rules_only_low_value"
    assert meta(result)["reused_from"] == previous["info_id"]
    assert models.calls == [] and models.embeddings == 0


@pytest.mark.parametrize(
    ("stats", "row", "reason"),
    [
        (
            {"tokens": 0, "missing": 0, "full_items": 1500, "screen_calls": 0},
            item("full-cap", "benzinga", "NVIDIA update", tickers=["NVDA"]),
            "full_daily_limit",
        ),
        (
            {"tokens": 0, "missing": 0, "full_items": 0, "screen_calls": 120},
            item("screen-cap", "benzinga", "Local event"),
            "screen_daily_limit",
        ),
        (
            {"tokens": 5_500_000, "missing": 0, "full_items": 0, "screen_calls": 0},
            item("token-cap", "benzinga", "NVIDIA update", tickers=["NVDA"]),
            "daily_budget",
        ),
    ],
)
def test_a022_independent_count_caps_and_token_fallback_defer_to_next_et_day(stats, row, reason):
    models = CountingModels()
    result = engine(models, stats=stats).process([row])[0]
    assert result["extraction_status"] == "pending"
    assert meta(result)["reason"] == reason
    assert datetime.fromisoformat(meta(result)["retry_at"]) > NOW
    assert models.calls == []


def test_a022_last_full_slot_goes_to_holding_before_pool():
    pool = item("last-pool", "fiscal.ai", "Apple pool update", tickers=["AAPL"])
    held = item("last-held", "fiscal.ai", "Outside-pool holding update", tickers=["XYZ"])
    held["extraction_source"] = {"news_queue": {"holding_related": True}}
    models = CountingModels()
    rows = engine(
        models,
        stats={"tokens": 0, "missing": 0, "full_items": 1499, "screen_calls": 0},
    ).process([pool, held])
    assert rows[0]["extraction_status"] == "pending"
    assert meta(rows[0])["reason"] == "full_daily_limit"
    assert rows[1]["extraction_status"] == "ok"
    assert models.calls == ["news_card"]


@pytest.mark.parametrize("kwargs", [{}, {"daily_budget": 1_500_000}])
def test_a022_4500000_tokens_allows_item_1500_then_defers_1501_by_count(kwargs):
    models = CountingModels()
    stats = {"tokens": 4_500_000, "missing": 0, "full_items": 1499, "screen_calls": 0}
    triage = engine(models, stats=stats, **kwargs)
    first = triage.process([item("item-1500", "benzinga", "Apple first", tickers=["AAPL"])])[0]
    assert triage.daily_budget == 5_500_000
    assert first["extraction_status"] == "ok"
    assert len(models.calls) == 1
    stats["full_items"] = 1500
    second = triage.process([item("item-1501", "benzinga", "Apple second", tickers=["AAPL"])])[0]
    assert second["extraction_status"] == "pending"
    assert meta(second)["reason"] == "full_daily_limit"
    assert len(models.calls) == 1


def test_a022_usage_query_counts_full_articles_once_and_screen_calls():
    from inves_cog.ingest.repository import Repository

    class Result:
        def fetchone(self):
            return {"tokens": 100, "missing": 0, "full_items": 1500, "screen_calls": 120}

    class Connection:
        def execute(self, sql, values):
            self.sql, self.values = sql, values
            return Result()

    connection = Connection()
    stats = Repository(connection).llm_usage(NOW)
    assert stats == {"tokens": 100, "missing": 0, "full_items": 1500, "screen_calls": 120}
    assert "unnest(info_ids)" in connection.sql
    assert "M1:layer1" in connection.sql and "M1:layer2" in connection.sql


def test_a022_queue_orders_a_then_holdings_then_newest_and_leaves_ud36_boundary():
    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.ingest.repository import Repository, json_text
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as db:
        db.execute("TRUNCATE ingest.info_items CASCADE")
        db.execute("DELETE FROM trading.ledger WHERE portfolio_id=%s", ("paper-fixed",))
        db.execute(
            """INSERT INTO trading.ledger
            (portfolio_id,trade_date,phase,extractor,rule_set,params_version,cash,equity,peak_equity,state,observed_at)
            VALUES (%s,%s,'close','fixed','A','p-2026.10',100,100,100,%s::jsonb,%s)""",
            ("paper-fixed", NOW.date(), json_text({"positions": {"XYZ": {"qty": 1}}}), NOW),
        )
        repo = Repository(db)
        rows = [
            item("held", "fiscal.ai", "Held update", tickers=["XYZ"], minutes=30),
            item("pool", "fiscal.ai", "Pool update", tickers=["AAPL"], minutes=5),
            item("macro", "benzinga", "FOMC tariff policy", minutes=1),
            item("screen", "benzinga", "Unclassified local update", minutes=0),
            item("low", "fiscal.ai", "Automated filing recap", minutes=0),
            item("old", "benzinga", "NVIDIA old", tickers=["NVDA"], minutes=60 * 24 * 5),
        ]
        for row in rows:
            repo.put_info(row)
        queued = repo.pending_info(20, as_of=NOW)
        assert [row["info_id"] for row in queued] == [
            rows[0]["info_id"],
            rows[2]["info_id"],
            rows[1]["info_id"],
            rows[3]["info_id"],
            rows[4]["info_id"],
        ]
        old = db.execute(
            "SELECT extraction_source FROM ingest.info_items WHERE info_id=%s", (rows[5]["info_id"],)
        ).fetchone()
        assert old["extraction_source"]["backfill_skip"]["decision"] == "UD-COORD-36"
        db.rollback()
