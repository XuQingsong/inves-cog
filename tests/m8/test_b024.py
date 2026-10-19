"""B-024: one sentence of industry text does not drop the rest of the news card."""

from datetime import datetime, timezone

import pytest

from inves_cog.ingest.info import enrich, make_item

WHEN = datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)


class Clock:
    def now_utc(self):
        return WHEN


class Script:
    def __init__(self, news_reply):
        self.news_reply = news_reply

    def call(self, task, payload):
        if task == "news_card":
            return self.news_reply
        if task == "info_fields_extraction":
            return {"is_guidance": False, "is_rating_change": False}
        raise AssertionError(task)


def _card(reply):
    item = make_item(
        "news",
        "Fixture",
        "amd",
        headline="AMD supply",
        body="The company talked about supply.",
        tickers=["AMD"],
        published_at=WHEN,
        clock=Clock(),
    )
    result = enrich(
        item,
        llm=Script(reply),
        embed=None,
        entities=[{"entity_id": "amd", "name": "Advanced Micro Devices", "aliases": [], "tickers": ["AMD"]}],
        clock=Clock(),
        close_read=True,
    )
    return result["extraction_source"]["news_card"]


def _company():
    return {"代码": "AMD", "名称": "Advanced Micro Devices", "方向": "利好", "重要程度": "高"}


@pytest.mark.phase1_blocking
def test_one_industry_sentence_keeps_the_card():
    card = _card({"说了什么": "供应变化", "行业": "半导体 利好", "名单内": [_company()], "名单外": []})
    assert card["说了什么"] == "供应变化"
    assert card["行业"] == ["半导体 利好"]
    assert card["名单内"][0]["代码"] == "AMD"
    assert card["名单内"][0]["方向"] == "利好"
    assert card["名单内"][0]["重要程度"] == "高"
    assert "原因" not in card


@pytest.mark.phase1_blocking
def test_industry_list_stays_a_list():
    card = _card({"说了什么": "供应变化", "行业": ["半导体"], "名单内": [_company()], "名单外": []})
    assert "半导体" in card["行业"]
    assert "原因" not in card
