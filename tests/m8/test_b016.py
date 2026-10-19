"""B-016: the tracked-move run calls the move card and writes the daily page."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.perception.attribution.chain import attribute_all

START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)


class Script:
    def __init__(self):
        self.tasks = []
        self.payloads = []

    def call(self, task, payload):
        self.tasks.append(task)
        self.payloads.append(payload)
        if task != "move_card":
            raise AssertionError(task)
        return {"解释": [{"编号": "news:muse", "怎么影响": "产品登顶", "强弱": "强"}]}


def _item(identifier, published, card):
    return {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": "Muse tops the store",
        "tickers": ["META"],
        "entities": ["META"],
        "source_root": identifier,
        "extraction_source": {"news_card": card},
    }


@pytest.mark.phase1_blocking
def test_tracked_move_run_calls_only_move_card_and_writes_the_daily_page():
    card = {
        "说了什么": "Muse 登顶",
        "名单内": [
            {
                "代码": "META",
                "名称": "Meta Platforms",
                "方向": "利好",
                "理由": "是它的产品",
                "重要程度": "高",
            }
        ],
        "名单外": [],
    }
    early = _item("news:muse", START - timedelta(hours=2), card)
    late = _item("news:late", START + timedelta(minutes=5), card)
    anomaly = {
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
    valuation = {"META": 100}
    plan = {"weight": 0.05}
    before_value, before_weight = valuation["META"], plan["weight"]
    client = Script()
    result = attribute_all(
        [anomaly],
        [early, late],
        as_of=START + timedelta(hours=1),
        client=client,
        valuation=valuation,
        plan=plan,
    )[0]
    assert client.tasks == ["move_card"]
    assert "anomaly_candidates" not in client.tasks
    sent = [row["编号"] for row in client.payloads[0]["新闻"]]
    assert sent == ["news:muse"]
    text = result["daily_text"]
    assert "产品登顶" in text
    assert "新闻和波动不改估值，不改计划" in text
    assert (
        "daily_text(" in Path(__file__).parents[2].joinpath("src/inves_cog/perception/attribution/chain.py").read_text()
    )
    assert early["extraction_source"]["news_card"]["名单内"][0]["代码"] == "META"
    assert valuation["META"] == before_value == 100
    assert plan["weight"] == before_weight == 0.05
