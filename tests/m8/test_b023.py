"""B-023: the news card names its fields and keeps the aliases already seen."""

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
        self.payloads = []

    def call(self, task, payload):
        self.payloads.append((task, payload))
        if task == "news_card":
            return self.news_reply
        if task == "info_fields_extraction":
            return {"is_guidance": False, "is_rating_change": False}
        raise AssertionError(task)


def _card(reply, script=None):
    script = script or Script(reply)
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
        llm=script,
        embed=None,
        entities=[{"entity_id": "amd", "name": "Advanced Micro Devices", "aliases": [], "tickers": ["AMD"]}],
        clock=Clock(),
        close_read=True,
    )
    return result["extraction_source"]["news_card"]


@pytest.mark.phase1_blocking
def test_third_field_names_fill_the_card():
    reply = {
        "summary": "供应变化",
        "affected_industries": ["半导体"],
        "tracked_companies": [
            {
                "code": "AMD",
                "name": "Advanced Micro Devices",
                "impact": "利好",
                "relation": "新闻点了名",
                "importance": "高",
            }
        ],
        "outside_companies": [{"name": "某公司"}],
    }
    card = _card(reply)
    assert card["说了什么"] == "供应变化"
    assert "半导体" in card["行业"]
    company = card["名单内"][0]
    assert company["代码"] == "AMD"
    assert company["方向"] == "利好"
    assert company["关系"] == "新闻点了名"
    assert company["重要程度"] == "高"
    assert card["名单外"][0]["名称"] == "某公司"
    assert "原因" not in card


@pytest.mark.phase1_blocking
def test_industry_object_keeps_the_name_key():
    card = _card({"行业": [{"行业": "半导体", "影响": "利好", "理由": "需求"}]})
    assert card["行业"] == ["半导体 利好 需求"]


@pytest.mark.phase1_blocking
def test_question_names_the_card_fields():
    script = Script({})
    _card({}, script)
    question = next(payload["问法"] for task, payload in script.payloads if task == "news_card")
    assert "说了什么" in question
    assert "名单内" in question
    assert "方向" in question
