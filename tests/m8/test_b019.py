"""B-019: a news card keeps the model's answer when the reply uses English keys."""

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
        self.tasks = []

    def call(self, task, payload):
        self.tasks.append(task)
        if task == "news_card":
            return self.news_reply
        if task == "info_fields_extraction":
            return {"is_guidance": False, "is_rating_change": False}
        raise AssertionError(task)


def _item(ticker="AMD"):
    return make_item(
        "news",
        "Fixture",
        ticker.lower(),
        headline=f"{ticker} supply",
        body="The company talked about supply.",
        tickers=[ticker],
        published_at=WHEN,
        clock=Clock(),
    )


def _entities(ticker, name):
    return [{"entity_id": ticker.lower(), "name": name, "aliases": [], "tickers": [ticker]}]


def _card(reply, ticker="AMD", name="Advanced Micro Devices"):
    result = enrich(
        _item(ticker),
        llm=Script(reply),
        embed=None,
        entities=_entities(ticker, name),
        clock=Clock(),
        close_read=True,
    )
    return result["extraction_source"]["news_card"]


@pytest.mark.phase1_blocking
def test_english_news_card_fields_are_kept():
    reply = {
        "summary": "苏姿丰说供应要增加",
        "industries": ["半导体"],
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
        "companies_outside_list": [],
    }
    card = _card(reply)
    assert card["说了什么"] == "苏姿丰说供应要增加"
    company = card["名单内"][0]
    assert company["代码"] == "AMD"
    assert company["重要程度"] == "高"
    assert company["关系"] == "新闻点了名"
    assert company["标明"] == "模型判断"


@pytest.mark.phase1_blocking
def test_chinese_news_card_stays_and_a_bad_reply_keeps_the_name_match():
    reply = {
        "说了什么": "Muse 登顶",
        "行业": ["软件"],
        "名单内": [
            {
                "代码": "META",
                "名称": "Meta Platforms",
                "方向": "利好",
                "理由": "是它的产品",
                "关系": "是它的产品",
                "重要程度": "高",
            }
        ],
        "名单外": [],
    }
    card = _card(reply, ticker="META", name="Meta Platforms")
    assert card["名单内"][0]["代码"] == "META"
    assert card["名单内"][0]["标明"] == "模型判断"

    broken = _card({"名单内": "坏了"}, ticker="META", name="Meta Platforms")
    assert broken["原因"]
    assert broken["名字匹配"][0]["代码"] == "META"
    assert broken["名字匹配"][0]["标明"] == "名字匹配"
