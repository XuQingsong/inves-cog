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
        "extraction_status": "pending",
        "embedding": None,
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
    triage = NewsTriage(llm=None, embed=None, entities=[], monitored_ids=set(), pool_tickers=set(), clock=_clock())
    for kind in ("short_interest", "macro"):
        result = triage.rules(_item(kind, "x"))
        assert result["extraction_source"]["news_triage"]["reason"] == "rules_only_structured"


def test_filing_no_tagging_even_when_relevant():
    llm = CountingLLM()
    item = _item("sec_8k", "8-K - ACME CORP (0001234567) (Filer)", ("ACME",))
    enrich(item, llm=llm, embed=None, entities=[], clock=_clock(), close_read=True)
    assert "entity_tagging" not in llm.calls


def _engine(llm):
    return NewsTriage(
        llm=llm,
        embed=None,
        entities=[],
        monitored_ids=set(),
        pool_tickers={"AAPL", "MSFT"},
        pool_ciks={"0000320193", "0000789019"},
        clock=_clock(),
    )


def _out(triage, items):
    return triage.process(items)


def test_pool_8k_cik_gets_news_card_only():
    llm = CountingLLM()
    triage = _engine(llm)
    item = _item("sec_8k", "8-K - APPLE INC (0000320193) (Filer)")
    out = _out(triage, [item])
    assert llm.calls == ["news_card"], llm.calls
    assert "entity_tagging" not in llm.calls and "info_fields_extraction" not in llm.calls
    assert out[0]["extraction_status"] == "ok"


def test_nonpool_8k_zero_calls():
    llm = CountingLLM()
    triage = _engine(llm)
    item = _item("sec_8k", "8-K - RANDOM CORP (0009999999) (Filer)")
    out = _out(triage, [item])
    assert llm.calls == [], llm.calls
    assert out[0]["embedding"] is None
    assert out[0]["extraction_source"]["news_triage"]["reason"] == "filing_not_in_pool"


def test_short_interest_with_pool_ticker_zero_calls():
    llm = CountingLLM()
    triage = _engine(llm)
    item = _item("short_interest", "FINRA Short Interest", ("AAPL",))
    out = _out(triage, [item])
    assert llm.calls == [], llm.calls
    assert out[0]["extraction_source"]["news_triage"]["reason"] == "rules_only_structured"


def test_macro_source_level1_zero_calls():
    llm = CountingLLM()
    triage = _engine(llm)
    item = _item("macro", "FRED DGS2")
    item["source_level"] = 1
    out = _out(triage, [item])
    assert llm.calls == [], llm.calls
    assert out[0]["extraction_source"]["news_triage"]["reason"] == "rules_only_structured"


def test_holding_form4_gets_news_card():
    llm = CountingLLM()
    triage = _engine(llm)
    item = _item("form4", "Form 4 - MSFT director sale", ("MSFT",))
    _out(triage, [item])
    assert llm.calls == ["news_card"], llm.calls


def test_finish_pending_rules_only_backlog():
    from unittest.mock import MagicMock

    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"info_id": "si:1", "kind": "short_interest", "extraction_source": {}},
        {"info_id": "f4:1", "kind": "form4", "extraction_source": {}},
        {"info_id": "f4:2", "kind": "form4", "extraction_source": {}},
    ]
    from inves_cog.ingest.repository import Repository

    repo = Repository.__new__(Repository)
    repo.connection = conn
    done = repo.finish_pending_rules_only(as_of=NOW, exclude_ids={"f4:2"})
    assert done == 2
    updates = [c for c in conn.execute.call_args_list if "UPDATE" in str(c)]
    assert len(updates) == 2
