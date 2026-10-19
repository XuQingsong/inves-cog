"""B-025: the morning page leads with macro news, then large position news."""

from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
PUBLISHED = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)


class Script:
    def call(self, task, payload):
        raise AssertionError(task)


def _company(code, level="高"):
    return {"代码": code, "名称": code, "方向": "利好", "理由": "同日", "重要程度": level}


def _card(identifier, said, industry, companies):
    return {"编号": identifier, "说了什么": said, "行业": industry, "名单内": companies, "名单外": []}


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


def _positions(held):
    return [{"trade_date": "2026-10-14", "positions": held}]


def _page(items, plan=None, moves=None):
    result = run_scheduled(
        MORNING,
        anomalies=moves or [],
        items=items,
        client=Script(),
        plan=plan,
    )
    assert [page["trade_date"] for page in result["daily_pages"]] == ["2026-10-14"]
    return result["daily_pages"][0]["text"]


@pytest.mark.phase1_blocking
def test_macro_leads_and_a_single_name_is_only_counted():
    items = [
        _item(_card("news:chips", "芯片需求", "半导体", [_company(code) for code in ("NVDA", "AVGO", "AMD", "AMAT")])),
        _item(_card("news:snow", "单一公司", "软件", [_company("SNOW")])),
        _item(_card("news:jnj", "持仓利空", "医药", [_company("JNJ")])),
        _item(_card("news:rates", "利率上升", "宏观 利率", [_company("META")])),
    ]
    text = _page(items, _positions({"META": 10}))
    assert text.index("利率上升") < text.index("芯片需求")
    assert "利率上升 含持仓" in text
    assert "持仓利空" not in text
    assert "单一公司" not in text
    assert "还有 2 条标了高，这里不展开" in text
    assert "再看：持仓上影响大的" in text
    assert "这档没有" in text


@pytest.mark.phase1_blocking
def test_a_position_in_a_move_leads_the_second_tier():
    items = [
        _item(_card("news:div", "分红说明", "医药", [_company("UNH")])),
        _item(_card("news:trial", "试验数据", "医药", [_company("JNJ")])),
    ]
    text = _page(items, _positions({"JNJ": 10, "UNH": 5}), [_move("JNJ")])
    assert "先看：宏观和影响面广的\n这档没有" in text
    assert text.index("试验数据") < text.index("分红说明")
    assert "试验数据 碰上不寻常波动" in text
    assert "分红说明 碰上不寻常波动" not in text
    assert "还有" not in text


@pytest.mark.phase1_blocking
def test_missing_position_snapshot_does_not_use_orders():
    orders = [{"trade_date": "2026-10-14", "payload": {"orders": [{"ticker": "JNJ", "action": "buy", "qty": 1}]}}]
    text = _page([_item(_card("news:trial", "试验数据", "医药", [_company("JNJ")]))], orders, [_move("JNJ")])
    assert "没有持仓快照" in text
    assert "试验数据" not in text
    assert "还有 1 条标了高，这里不展开" in text


@pytest.mark.phase1_blocking
def test_the_first_tier_stops_at_five():
    items = [
        _item(_card(f"news:m{index}", f"宏观{label}", "宏观", [_company("META")]))
        for index, label in enumerate(("一", "二", "三", "四", "五", "六"), start=1)
    ]
    text = _page(items)
    for label in ("一", "二", "三", "四", "五"):
        assert f"宏观{label}" in text
    assert "宏观六" not in text
    assert "还有 1 条标了高，这里不展开" in text
    assert "没有持仓快照" in text


@pytest.mark.phase1_blocking
def test_one_medium_name_is_not_counted():
    text = _page([_item(_card("news:mid", "中等一条", "软件", [_company("SNOW", "中")]))])
    assert "中等一条" not in text
    assert "还有" not in text
    assert "先看：宏观和影响面广的\n这档没有" in text
    assert "没有持仓快照" in text


@pytest.mark.phase1_blocking
def test_macro_position_move_is_shown_once_in_the_first_tier():
    text = _page(
        [_item(_card("news:rates2", "利率上升", "宏观 利率", [_company("META")]))],
        _positions({"META": 10}),
        [_move("META")],
    )
    assert text.count("利率上升") == 1
    first, second = text.split("再看：持仓上影响大的", 1)
    assert "利率上升" in first
    assert "含持仓" in first
    assert "碰上不寻常波动" in first
    assert "利率上升" not in second
    assert "这档没有" in second
    assert "还有" not in text
