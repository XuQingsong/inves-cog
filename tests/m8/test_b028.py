"""B-028: the morning move line uses the anomaly's own returns."""

import re
from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
START = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)
DAY = "2026-10-15"
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
    "up",
    "down",
    "close",
    "post",
)
NINE = ["NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "AMAT", "LRCX", "KLAC"]


class Script:
    def call(self, task, payload):
        raise AssertionError(task)


def _move(anomaly_id, members, *, direction, session="close"):
    return {
        "anomaly_id": anomaly_id,
        "started_at": START,
        "trade_date": DAY,
        "session": session,
        "universe": "pool",
        "direction": direction,
        "members": members,
        "baskets": [],
    }


def _member(ticker, ret):
    return {"ticker": ticker, "ret": ret}


def _page(anomalies, items, *, plan=None):
    result = run_scheduled(MORNING, anomalies=anomalies, items=items, client=Script(), plan=plan)
    assert [page["trade_date"] for page in result["daily_pages"]] == [DAY]
    return result["daily_pages"][0]["text"]


def _one():
    return _page([_move("jnj", [_member("JNJ", -0.0573)], direction="down")], [])


def _nine():
    members = [_member(ticker, -0.074) for ticker in NINE[:-1]]
    members.append(_member(NINE[-1], None))
    return _page([_move("chips", members, direction="down")], [])


def _after_hours():
    return _page([_move("jnj", [_member("JNJ", 0.00208)], direction="down", session="post")], [])


def _flat():
    return _page([_move("aapl", [_member("AAPL", 0.0003)], direction="up")], [])


def _blank():
    return _page([_move("amd", [_member("AMD", None)], direction="up")], [])


def _no_news():
    plan = [{"trade_date": DAY, "positions": {"NVDA": 10, "MU": 4}}]
    return _page([], [], plan=plan)


def _assert_plain(text):
    for word in FORBIDDEN:
        assert word not in text
    assert re.search(r"-\d+(?:\.\d+)?%", text) is None
    assert re.search(r"\d+\.\d{3,}", text) is None
    assert re.search(r"[a-z]+_[a-z0-9_]+", text) is None


@pytest.mark.phase1_blocking
def test_one_close_move_uses_the_member_return():
    assert "1. JNJ 跌 5.7%" in _one()


@pytest.mark.phase1_blocking
def test_nine_names_average_the_returns_that_exist():
    text = _nine()
    assert "9 只一起跌，平均跌 7.4%：" + "、".join(NINE) in text


@pytest.mark.phase1_blocking
def test_post_move_names_the_opposite_of_the_peer_direction():
    assert "JNJ 盘后涨 0.2%，明显弱于同类股票" in _after_hours()


@pytest.mark.phase1_blocking
def test_a_rounded_zero_is_called_flat():
    assert "AAPL 基本没动，明显强于同类股票" in _flat()


@pytest.mark.phase1_blocking
def test_a_blank_return_names_the_direction_without_a_percent():
    text = _blank()
    assert "1. AMD 涨" in text
    assert "AMD 涨%" not in text
    assert "%" not in text.split("1. AMD 涨", 1)[1].split("\n", 1)[0]
    assert "None" not in text


@pytest.mark.phase1_blocking
def test_a_day_with_no_news_says_nothing_arrived():
    text = _no_news()
    assert "今天一条新闻都没收到" in text
    assert "今天一条新闻都没收到，没法判断这些持仓有没有消息：MU、NVDA" in text
    assert "今天没有重要新闻" not in text


@pytest.mark.phase1_blocking
def test_the_page_has_no_english_session_words():
    for text in (_one(), _nine(), _after_hours(), _flat(), _blank(), _no_news()):
        _assert_plain(text)
