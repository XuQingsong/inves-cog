"""B-027: the morning page is written for a person, not for a programmer."""

import re
from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)
DAY = "2026-10-14"
FORBIDDEN = (
    "库",
    "入库",
    "数据库",
    "新闻卡",
    "波动卡",
    "标了高",
    "名单内",
    "名单外",
    "篮子",
    "快照",
    "编号",
    "归类",
    "news:",
    "sec_",
    "None",
)


class Script:
    def call(self, task, payload):
        if task != "move_card":
            raise AssertionError(task)
        names = payload["波动"]["股票"]
        if names == ["JNJ"] and payload["新闻"]:
            cited = payload["新闻"][0]["编号"]
            return {"解释": [{"编号": cited, "怎么影响": "试验数据好于预期", "强弱": "强"}]}
        return {"解释": []}


def _company(code, level="高"):
    return {"代码": code, "名称": code, "方向": "利好", "理由": "同日", "重要程度": level}


def _item(identifier, published, ticker, said, *, tagged=True, date_only=False):
    card = {"说了什么": said, "名单内": [_company(ticker)] if tagged else [], "名单外": []}
    item = {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": said,
        "tickers": [ticker],
        "entities": [ticker],
        "source_root": identifier,
        "extraction_source": {"news_card": card},
    }
    if date_only:
        item["flags"] = ["published_at_date_only"]
    return item


def _move(anomaly_id, tickers, magnitude="-5.7%"):
    return {
        "anomaly_id": anomaly_id,
        "started_at": START,
        "trade_date": DAY,
        "session": "open",
        "universe": "pool",
        "direction": "跌",
        "幅度": magnitude,
        "members": [{"ticker": ticker} for ticker in tickers],
        "baskets": [],
    }


def _page(anomalies, items, *, plan=None, valuation=None, lookup=None):
    result = run_scheduled(
        MORNING,
        anomalies=anomalies,
        items=items,
        client=Script(),
        plan=plan,
        valuation=valuation,
        news_lookup=lookup,
    )
    assert [page["trade_date"] for page in result["daily_pages"]] == [DAY]
    return result["daily_pages"][0]["text"]


def _two_moves():
    items = [
        _item("news:benzinga:jnj", START - timedelta(hours=3), "JNJ", "试验数据好于预期"),
        _item("news:benzinga:chips", START - timedelta(hours=2), "AMD", "芯片一起走弱"),
    ]
    moves = [_move("jnj", ["JNJ"]), _move("chips", ["AMD", "NVDA"], "-7.4%")]
    return _page(moves, items)


def _found_later():
    rows = [
        _item("news:benzinga:late", START + timedelta(hours=2), "JNJ", "晚到的说明"),
        _item("news:benzinga:a", START - timedelta(hours=5), "JNJ", "第一条补记"),
        _item("news:benzinga:b", START - timedelta(hours=4), "JNJ", "第二条补记"),
        _item("sec_8k:c", START - timedelta(hours=1), "JNJ", "第三条补记"),
    ]

    def lookup(ticker, start, end):
        return rows

    return _page([_move("jnj", ["JNJ"])], [], lookup=lookup)


def _four_labels():
    items = [
        _item("news:benzinga:aaa", START - timedelta(hours=3), "AAA", "收到但没对上", tagged=False),
        _item(
            "news:benzinga:ddd",
            datetime(2026, 10, 14, tzinfo=timezone.utc),
            "DDD",
            "同一天的消息",
            tagged=False,
            date_only=True,
        ),
    ]
    found = _item("news:benzinga:bbb", START - timedelta(hours=2), "BBB", "事后才到")

    def lookup(ticker, start, end):
        return [found] if ticker == "BBB" else []

    moves = [_move(ticker.lower(), [ticker]) for ticker in ("AAA", "BBB", "CCC", "DDD")]
    return _page(moves, items, lookup=lookup)


def _values():
    valuation = [
        {
            "trade_date": DAY,
            "ticker": "NVDA",
            "status": "ok",
            "bear": 412.16,
            "neutral": 969.66,
            "bull": 1390.10,
            "price": 217.23,
        },
        {
            "trade_date": DAY,
            "ticker": "JNJ",
            "status": "ok",
            "bear": 180.12,
            "neutral": 235.49,
            "bull": 280.00,
            "price": 253.28,
        },
        {"trade_date": DAY, "ticker": "MU", "status": "ok", "bear": 50, "neutral": 80, "bull": 120},
        {"trade_date": DAY, "ticker": "UNH", "status": "unvalued", "payload": {"reason": "金融"}},
        {"trade_date": DAY, "ticker": "AAPL", "status": "ok", "bear": 1, "neutral": 2, "bull": 3, "price": 2},
    ]
    plan = [
        {
            "trade_date": DAY,
            "positions": {"NVDA": 10, "UNH": 4},
            "payload": {"orders": [{"ticker": "MU", "action": "确认加仓", "value": 100}]},
        }
    ]
    return _page([_move("jnj", ["JNJ"])], [], plan=plan, valuation=valuation)


def _plan_amount():
    plan = [
        {
            "trade_date": DAY,
            "payload": {"orders": [{"ticker": "MU", "action": "确认加仓", "value": 22869.85093940002}]},
        }
    ]
    return _page([], [], plan=plan)


def _assert_plain(text):
    for word in FORBIDDEN:
        assert word not in text
    assert re.search(r"-\d+(?:\.\d+)?%", text) is None
    assert re.search(r"\d+\.\d{3,}", text) is None
    assert re.search(r"[a-z]+_[a-z0-9_]+", text) is None


@pytest.mark.phase1_blocking
def test_two_moves_each_keep_their_own_group():
    text = _two_moves()
    jnj, chips = text.split("2 只一起跌", 1)
    assert "可能的原因：" in jnj
    assert "波动前已经看到这条新闻" in jnj
    assert "JNJ 跌" in jnj
    assert "没找到能解释这次波动的新闻" in chips
    assert "有相关新闻，但没认出是原因" in chips
    assert "提前看到" not in text


@pytest.mark.phase1_blocking
def test_later_news_lists_three_and_counts_the_rest():
    text = _found_later()
    assert "事后找到、当时还没收到的：" in text
    assert "晚到的说明" in text
    assert "第一条补记" in text
    assert "第二条补记" in text
    assert "第三条补记" not in text
    assert "另有 1 条" in text
    assert "（波动开始后才发布）" in text


@pytest.mark.phase1_blocking
def test_the_other_four_labels_use_plain_words():
    text = _four_labels()
    assert "收到了新闻，但没认出和这只股票有关" in text
    assert "当时没收到这条新闻，事后才找到" in text
    assert "没找到相关新闻" in text
    assert "新闻和波动是同一天，分不清先后" in text


@pytest.mark.phase1_blocking
def test_valuation_prints_only_the_relevant_names():
    text = _values()
    assert "NVDA 现价 217.23｜估值待复核" in text
    assert "JNJ 现价 253.28｜偏低" in text
    assert "MU 估值待复核" in text
    assert "UNH 暂不估值：金融类公司，缺所需财务数据" in text
    assert "其余 1 只不在这一页" in text
    assert "AAPL" not in text


@pytest.mark.phase1_blocking
def test_plan_amount_is_dollars_with_cents():
    text = _plan_amount()
    assert "MU 确认加仓 约 22,869.85 美元" in text


@pytest.mark.phase1_blocking
def test_the_page_hides_internal_words():
    for text in (_two_moves(), _found_later(), _four_labels(), _values(), _plan_amount()):
        _assert_plain(text)
