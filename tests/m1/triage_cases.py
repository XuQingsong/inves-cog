"""Handwritten news policy cases; dialogue is replayed from temporary recordings."""

import hashlib
import json
from datetime import timedelta


def assert_news_triage(root, clock):
    from inves_cog.ingest.info import make_item
    from inves_cog.ingest.triage import NewsTriage
    from inves_cog.llm.client import Client, canonical_payload

    entities = [
        {"entity_id": "apple", "name": "Apple", "aliases": ["iPhone"], "tickers": ["AAPL"]},
        {"entity_id": "openai", "name": "OpenAI", "aliases": ["ChatGPT"], "tickers": []},
    ]
    usage = []
    client = Client(recordings=root, clock=clock, recorder=usage.append, monotonic=lambda: 0)

    def recording(task, payload, result):
        digest = hashlib.sha256(canonical_payload(payload).encode()).hexdigest()
        folder = root / task
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (digest + ".json")).write_text(
            json.dumps(
                {
                    "task": task,
                    "payload_sha256": digest,
                    "result": result,
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                }
            )
        )

    def item(identifier, headline, *, tickers=(), days=0, source="Fixture", kind="news"):
        return make_item(
            kind,
            source,
            identifier,
            headline=headline,
            body="Original fixture evidence.",
            tickers=tickers,
            published_at=clock.now_utc() - timedelta(days=days),
            clock=clock,
        )

    def full(row):
        payload = {"headline": row["headline"], "body": row["body"]}
        recording("entity_tagging", payload, {"entities": []})
        recording("info_fields_extraction", payload, {"is_guidance": False, "is_rating_change": False})

    def engine(**kwargs):
        return NewsTriage(
            llm=client,
            embed=lambda *a, **k: [0.1] * 1024,
            entities=entities,
            monitored_ids={"openai"},
            pool_tickers={"AAPL"},
            clock=clock,
            **kwargs,
        )

    rows = [
        item("tracked", "A company reports", tickers=["AAPL"]),
        item("monitor", "OpenAI ARR grows"),
        item("product", "iPhone shipments"),
        item("official", "Central bank releases statement", source="FederalReserveNews"),
        item("sec", "Untracked filing", kind="sec_8k"),
        item("old", "Apple historic event", days=31),
    ]
    for row in rows[:-1]:
        full(row)
    results = engine().process(rows)
    assert [r["extraction_source"]["news_triage"]["layer"] for r in results] == [2, 2, 2, 2, 2, 3]
    assert len(usage) == 10 and all(r["extraction_status"] == "ok" for r in results)
    assert results[-1]["embedding"] and not results[-1]["extraction_source"]["news_triage"]["llm_full"]
    assert all(r["purpose"] == "M1:layer2" for r in usage)

    # 26 unknown articles use 25+1 title batches, never 26 full requests.
    unknown = [item("unknown:" + str(n), f"Local hobby event {n}") for n in range(26)]
    unknown[0]["headline"] = "Toshiba expands chip production"
    context = [
        {"entity_id": e["entity_id"], "name": e["name"], "aliases": e["aliases"], "tickers": e["tickers"]}
        for e in entities
    ]
    for batch in (unknown[:25], unknown[25:]):
        payload = {
            "items": [{"info_id": r["info_id"], "headline": r["headline"], "body": r["body"][:200]} for r in batch],
            "known_entities": context,
            "industry_scope": [
                "semiconductors",
                "AI",
                "software",
                "retail",
                "healthcare",
                "finance",
                "energy",
                "industrial",
                "macroeconomic policy",
            ],
        }
        recording(
            "entity_tagging",
            payload,
            {"items": [{"info_id": r["info_id"], "entities": [], "material": r is unknown[0]} for r in batch]},
        )
    full(unknown[0])
    before = len(usage)
    results = engine().process(unknown)
    assert len(usage) - before == 4
    assert results[0]["extraction_source"]["news_triage"]["layer"] == 2
    assert all(r["extraction_source"]["news_triage"]["layer"] == 3 for r in results[1:])
    assert all(r["embedding"] is not None for r in results)
    assert [len(r["info_ids"]) for r in usage[before:] if r["purpose"] == "M1:layer1"] == [25, 1]

    # Same-root articles retain identity and get independent vectors, but share dialogue.
    one = item("root-one", "Apple launch")
    two = dict(one, info_id="news:Fixture:root-two", headline="A reposted Apple launch")
    full(one)
    before = len(usage)
    results = engine().process([one, two])
    assert len(usage) - before == 2 and results[1]["info_id"] == two["info_id"]
    assert results[1]["extraction_source"]["news_triage"]["reused_from"] == one["info_id"]

    # Budget holds untracked official/material work, while tracked pool work continues.
    before = len(usage)
    budget = engine(daily_budget=10, usage_today=lambda: {"tokens": 11, "missing": 0})
    results = budget.process([rows[0], rows[1], unknown[1]])
    assert results[0]["extraction_status"] == "ok" and len(usage) - before == 2
    assert all(r["extraction_status"] == "pending" for r in results[1:])
    assert all(r["extraction_source"]["news_triage"]["retry_at"] > clock.now_utc().isoformat() for r in results[1:])
    assert all(r["embedding"] is not None for r in results)

    # Bad or absent screening replies cannot silently make an article unimportant.
    bad = item("malformed", "Unclassified story")
    results = engine().process([bad])
    assert results[0]["extraction_status"] == "pending"
    assert results[0]["extraction_source"]["news_triage"]["reason"] == "screening_failed"
    assert results[0]["embedding"] is not None
    # An old article is still eligible through the same on-demand interface.
    full(rows[-1])
    before = len(usage)
    assert engine().process([rows[-1]], on_demand=True)[0]["extraction_source"]["news_triage"]["layer"] == 2
    assert len(usage) - before == 2

    # Concurrent extraction must preserve the enclosing job accounting context.
    from inves_cog.llm.usage import usage_context

    parallel = [item("parallel:" + str(n), "Apple parallel fixture " + str(n)) for n in range(4)]
    for row in parallel:
        full(row)
    before = len(usage)
    with usage_context(job_task="parallel_probe"):
        results = engine(workers=4).process(parallel)
    assert len(usage) - before == 8
    assert all(r["purpose"] == "parallel_probe|M1:layer2" for r in usage[before:])
    assert all(r["extraction_status"] == "ok" for r in results)

    # psycopg returns unregistered pgvector values as their textual form.
    # Reprocessing must bind that value directly rather than JSON-quote it.
    from inves_cog.ingest.repository import Repository

    class Connection:
        def execute(self, sql, values):
            self.values = values
            return self

        def fetchone(self):
            return {"info_id": results[0]["info_id"]}

    connection = Connection()
    stored = dict(results[0], embedding=json.dumps([0.1] * 1024))
    assert Repository(connection).apply_enrichment(stored)
    assert connection.values[1] == stored["embedding"]

    # Empty bodies have NULL roots. The same already-enriched info_id still
    # reuses its result; a distinct NULL-root article must not borrow it.
    empty = item("empty", "Apple headline only", tickers=["AAPL"])
    empty["body"] = None
    empty["summary"] = None
    empty["source_root"] = None
    recording("entity_tagging", {"headline": empty["headline"], "body": ""}, {"entities": []})
    recording("info_fields_extraction", {"headline": empty["headline"], "body": ""}, {"is_guidance": False})
    cached = engine().process([empty])[0]
    before = len(usage)
    assert engine().process([cached])[0]["extraction_status"] == "ok"
    assert len(usage) == before
    engine().process([dict(empty, info_id="news:Fixture:other-empty")])
    assert len(usage) == before + 2
