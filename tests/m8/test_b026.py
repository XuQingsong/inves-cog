"""B-026: each holding gets its own line on the morning page."""

from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
PUBLISHED = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)


class Script:
    def call(self, task, payload):
        raise AssertionError(task)


def _company(code):
    return {"代码": code, "名称": code, "方向": "利好", "理由": "同日", "重要程度": "高"}


def _card(identifier, said, industry, code):
    return {"编号": identifier, "说了什么": said, "行业": industry, "名单内": [_company(code)], "名单外": []}


def _item(card):
    ticker = card["名单内"][0]["代码"]
    return {
        "info_id": card["编号"],
        "published_at": PUBLISHED,
        "first_seen_at": PUBLISHED,
        "headline": card["说了什么"],
        "tickers": [ticker],
        "entities": [ticker],
        "source_root": card["编号"],
        "extraction_source": {"news_card": card},
    }


def _move(ticker):
    return {
        "anomaly_id": ticker.lower(),
        "started_at": START,
        "trade_date": "2026-10-14",
        "session": "open",
        "universe": "pool",
        "direction": "跌",
        "幅度": "6%",
        "members": [{"ticker": ticker}],
        "baskets": [],
    }


def _page(items, positions, moves=None):
    result = run_scheduled(
        MORNING,
        anomalies=moves or [],
        items=items,
        client=Script(),
        plan=[{"trade_date": "2026-10-14", "positions": positions}],
    )
    assert [page["trade_date"] for page in result["daily_pages"]] == ["2026-10-14"]
    return result["daily_pages"][0]["text"]


def _second(text):
    return text.split("三、你的持仓", 1)[1]


@pytest.mark.phase1_blocking
def test_six_holdings_are_all_listed():
    labels = ("甲", "乙", "丙", "丁", "戊", "己")
    codes = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
    items = [
        _item(_card(f"news:h{index}", f"持仓{label}", "医药", code))
        for index, (label, code) in enumerate(zip(labels, codes, strict=True), start=1)
    ]
    text = _page(items, {code: 1 for code in codes})
    second = _second(text)
    for label in labels:
        assert f"持仓{label}" in second
    assert "另有" not in text


@pytest.mark.phase1_blocking
def test_one_holding_expands_the_earliest_id_and_counts_the_rest():
    items = [
        _item(_card("news:b2", "分红说明", "医药", "JNJ")),
        _item(_card("news:c3", "会议纪要", "医药", "JNJ")),
        _item(_card("news:a1", "试验数据", "医药", "JNJ")),
    ]
    text = _page(items, {"JNJ": 10}, [_move("JNJ")])
    assert "JNJ：试验数据 利好。另有 2 条（今天也有不寻常波动）" in text
    assert "分红说明" not in text
    assert "会议纪要" not in text


@pytest.mark.phase1_blocking
def test_holdings_without_a_high_mark_share_one_line():
    text = _page(
        [_item(_card("news:soft", "软件新闻", "软件", "META"))],
        {"META": 10, "SNOW": 4},
    )
    assert "软件新闻" in text
    assert "今天没有重要新闻：SNOW" in text
    assert "另有" not in text


@pytest.mark.phase1_blocking
def test_a_holding_stays_in_the_second_tier_after_the_first_tier():
    text = _page(
        [_item(_card("news:rates", "利率上升", "宏观 利率", "META"))],
        {"META": 10},
    )
    first, second = text.split("三、你的持仓", 1)
    assert "含你的持仓 META" in first
    assert "利率上升" in second
    assert "今天没有拿到持仓" not in text
