"""B-022: a news card also keeps the other Chinese field names the model used."""

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


@pytest.mark.phase1_blocking
def test_other_chinese_field_names_fill_the_card():
    reply = {
        "新闻摘要": "供应变化",
        "受影响美股行业": [{"行业名": "半导体", "影响": "利好", "理由": "需求"}],
        "跟踪名单内受影响公司": [
            {
                "代码": "AMD",
                "名称": "Advanced Micro Devices",
                "影响": "利好",
                "与新闻关系": "新闻点了名",
                "重要程度": "高",
            }
        ],
        "名单外明显受影响公司": [{"名称": "某公司", "影响": "不确定"}],
    }
    card = _card(reply)
    assert card["说了什么"] == "供应变化"
    assert card["行业"] == ["半导体 利好 需求"]
    company = card["名单内"][0]
    assert company["代码"] == "AMD"
    assert company["方向"] == "利好"
    assert company["关系"] == "新闻点了名"
    assert company["重要程度"] == "高"
    assert company["标明"] == "模型判断"
    assert card["名单外"][0]["名称"] == "某公司"
    assert card["名单外"][0]["方向"] == "不确定"
    assert "原因" not in card


@pytest.mark.phase1_blocking
def test_english_news_card_fields_stay():
    reply = {
        "summary": "苏姿丰说供应要增加",
        "companies_affected": [
            {
                "code": "AMD",
                "name": "Advanced Micro Devices",
                "direction": "利空",
                "reason": "供应要增加",
                "relation": "新闻点了名",
                "importance": "高",
            }
        ],
    }
    card = _card(reply)
    assert card["说了什么"] == "苏姿丰说供应要增加"
    assert card["名单内"][0]["代码"] == "AMD"
    assert card["名单内"][0]["方向"] == "利空"
    assert card["名单内"][0]["标明"] == "模型判断"
