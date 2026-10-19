"""B-017: a tracked move uses the move card even when no news card is present."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.chain import attribute_all

START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)


class Script:
    def __init__(self):
        self.tasks = []

    def call(self, task, payload):
        self.tasks.append(task)
        if task != "move_card":
            raise AssertionError(task)
        cited = payload["新闻"][0]["编号"]
        return {"解释": [{"编号": cited, "怎么影响": "供应变化", "强弱": "中"}]}


def _anomaly():
    return {
        "anomaly_id": "meta-up",
        "started_at": START,
        "trade_date": "2026-10-14",
        "session": "open",
        "universe": "pool",
        "direction": "涨",
        "幅度": "11%",
        "members": [{"ticker": "META"}],
        "baskets": [],
    }


def _item(identifier, published, card=None):
    item = {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": "Muse tops the store",
        "tickers": ["META"],
        "entities": ["META"],
        "source_root": identifier,
    }
    if card is not None:
        item["extraction_source"] = {"news_card": card}
    return item


@pytest.mark.phase1_blocking
def test_tracked_move_without_a_news_card_calls_only_move_card():
    early = _item("news:plain", START - timedelta(hours=2))
    late = _item("news:late", START + timedelta(minutes=5))
    client = Script()
    result = attribute_all([_anomaly()], [early, late], as_of=START + timedelta(hours=1), client=client)[0]
    assert client.tasks == ["move_card"]
    assert "anomaly_candidates" not in client.tasks
    assert "claim_extraction" not in client.tasks
    assert "供应变化" in result["daily_text"]


@pytest.mark.phase1_blocking
def test_tracked_move_with_no_news_writes_the_daily_page_without_a_model():
    client = Script()
    result = attribute_all([_anomaly()], [], as_of=START + timedelta(hours=1), client=client)[0]
    assert client.tasks == []
    assert "查过没有消息" in result["daily_text"]


@pytest.mark.phase1_blocking
def test_tracked_move_keeps_meta_and_does_not_rewrite_numbers():
    card = {
        "说了什么": "Muse 登顶",
        "名单内": [{"代码": "META", "名称": "Meta Platforms", "方向": "利好", "理由": "是它的产品", "重要程度": "高"}],
        "名单外": [],
    }
    early = _item("news:muse", START - timedelta(hours=2), card)
    valuation = {"META": 100}
    plan = {"weight": 0.05}
    client = Script()
    result = attribute_all(
        [_anomaly()],
        [early],
        as_of=START + timedelta(hours=1),
        client=client,
        valuation=valuation,
        plan=plan,
    )[0]
    assert client.tasks == ["move_card"]
    assert early["extraction_source"]["news_card"]["名单内"][0]["代码"] == "META"
    assert valuation["META"] == 100
    assert plan["weight"] == 0.05
    assert "新闻和波动不改估值，不改计划" in result["daily_text"]
