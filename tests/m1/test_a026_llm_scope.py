"""A-026: non-news LLM scope reduction."""
from datetime import datetime, timedelta, timezone

from inves_cog.ingest.info import enrich
from inves_cog.ingest.triage import NewsTriage

NOW = datetime(2036, 10, 26, 14, 0, tzinfo=timezone.utc)


class CountingLLM:
    def __init__(self):
        self.calls = []

    def call(self, task, payload):
        self.calls.append(task)
        return {"entities": [], "titles": []}


def _item(kind, headline="8-K - FOO INC (0009999999) (Filer)", tickers=()):
    return {
        "info_id": f"{kind}:x",
        "kind": kind,
        "headline": headline,
        "body": "",
        "tickers": list(tickers),
        "entities": [],
        "flags": [],
        "extraction_source": {},
        "published_at": NOW - timedelta(hours=1),
        "first_seen_at": NOW - timedelta(minutes=10),
        "source": "sec",
        "source_level": 2,
        "source_root": None,
    }


def _clock():
    from inves_cog.clock import FrozenClock

    return FrozenClock(NOW)


def test_no_info_fields_extraction():
    llm = CountingLLM()
    enrich(_item("sec_8k"), llm=llm, embed=None, entities=[], clock=_clock(), close_read=False)
    assert "info_fields_extraction" not in llm.calls
    assert "entity_tagging" not in llm.calls


def test_news_still_tags():
    llm = CountingLLM()
    enrich(_item("news", "Acme beats estimates", ("ACME",)), llm=llm, embed=None, entities=[], clock=_clock())
    assert "entity_tagging" in llm.calls


def test_structured_items_rules_only():
    triage = NewsTriage(
        llm=None, embed=None, entities=[], monitored_ids=set(), pool_tickers=set(), clock=_clock()
    )
    for kind in ("short_interest", "macro"):
        result = triage.rules(_item(kind, "x"))
        assert result["extraction_source"]["news_triage"]["reason"] == "rules_only_structured"


def test_filing_no_tagging_even_when_relevant():
    llm = CountingLLM()
    item = _item("sec_8k", "8-K - ACME CORP (0001234567) (Filer)", ("ACME",))
    enrich(item, llm=llm, embed=None, entities=[], clock=_clock(), close_read=True)
    assert "entity_tagging" not in llm.calls
