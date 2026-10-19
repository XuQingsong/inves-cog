"""B-031: a move prints at most three reasons, strongest first."""

import re
from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
DAY = "2026-10-15"
EARLY = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
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


class Reply:
    def __init__(self, body):
        self.body = body
        self.payloads = []

    def call(self, task, payload):
        self.payloads.append(payload)
        if task != "move_card":
            raise AssertionError(task)
        return self.body(payload)


def _move():
    return {
        "anomaly_id": "jnj",
        "trade_date": DAY,
        "session": "close",
        "universe": "pool",
        "direction": "down",
        "members": [{"ticker": "JNJ", "ret": "-0.0573"}],
        "baskets": [],
    }


def _item(info_id, published, headline, *, date_only=False):
    card = {"说了什么": headline, "名单内": [], "钟点清楚": not date_only}
    item = {
        "info_id": info_id,
        "published_at": published,
        "first_seen_at": published,
        "headline": headline,
        "tickers": ["JNJ"],
        "entities": ["JNJ"],
        "source_root": info_id,
        "extraction_source": {"news_card": card},
    }
    if date_only:
        item["flags"] = ["published_at_date_only"]
    return item


def _when(minute):
    return datetime(2026, 10, 15, 12, minute, tzinfo=timezone.utc)


def _page(rows, client):
    items = [_item(info_id, _when(index), headline) for index, (info_id, _strength, headline) in enumerate(rows)]
    result = run_scheduled(MORNING, anomalies=[_move()], items=items, client=client)
    assert [page["trade_date"] for page in result["daily_pages"]] == [DAY]
    return result["daily_pages"][0]["text"]


def _reply(rows):
    def body(payload):
        sent = {item["编号"] for item in payload["新闻"]}
        assert sent == {info_id for info_id, _strength, _headline in rows}
        entries = []
        for info_id, strength, headline in rows:
            entry = {"编号": info_id, "怎么影响": headline}
            if strength:
                entry["强弱"] = strength
            entries.append(entry)
        return {"解释": entries}

    return Reply(body)


def _reasons(text):
    group = text.split("我们当时看到了吗", 1)[0]
    return re.findall(r"可能的原因：(\S+)", group)


def _assert_plain(text):
    for word in FORBIDDEN:
        assert word not in text
    assert re.search(r"-\d+(?:\.\d+)?%", text) is None
    assert re.search(r"\d+\.\d{3,}", text) is None
    assert re.search(r"[a-z]+_[a-z0-9_]+", text) is None


@pytest.mark.phase1_blocking
def test_ten_reasons_keep_the_three_strong_ones():
    rows = [
        ("n1", "弱", "第一条弱"),
        ("n2", "强", "第二条强"),
        ("n3", "中", "第三条中"),
        ("n4", "弱", "第四条弱"),
        ("n5", "强", "第五条强"),
        ("n6", "弱", "第六条弱"),
        ("n7", "强", "第七条强"),
        ("n8", "中", "第八条中"),
        ("n9", "弱", "第九条弱"),
        ("n10", "弱", "第十条弱"),
    ]
    text = _page(rows, _reply(rows))
    assert _reasons(text) == ["第二条强（强）", "第五条强（强）", "第七条强（强）"]
    assert "另有 7 条较弱的可能原因" in text


@pytest.mark.phase1_blocking
def test_three_reasons_sort_without_a_remainder():
    rows = [("n1", "中", "中等这条"), ("n2", "弱", "弱的这条"), ("n3", "强", "强的这条")]
    text = _page(rows, _reply(rows))
    assert _reasons(text) == ["强的这条（强）", "中等这条（中）", "弱的这条（弱）"]
    assert "另有" not in text


@pytest.mark.phase1_blocking
def test_a_missing_strength_is_printed_last_and_then_left_out():
    rows = [
        ("n1", "", "没有强弱"),
        ("n2", "弱", "第一条弱"),
        ("n3", "中", "中等这条"),
        ("n4", "弱", "第二条弱"),
    ]
    text = _page(rows, _reply(rows))
    assert _reasons(text) == ["中等这条（中）", "第一条弱（弱）", "第二条弱（弱）"]
    assert "没有强弱" not in text
    assert "另有 1 条较弱的可能原因" in text


@pytest.mark.phase1_blocking
def test_already_seen_uses_every_reason_not_only_the_printed_three():
    """The three strong cards are the same day with no clock, so they were not already known."""
    weak = _item("early", EARLY, "早看到的弱原因")
    late = [
        _item(info_id, datetime(2026, 10, 15, hour, tzinfo=timezone.utc), headline, date_only=True)
        for info_id, hour, headline in (
            ("s1", 4, "第一条强原因"),
            ("s2", 5, "第二条强原因"),
            ("s3", 6, "第三条强原因"),
        )
    ]

    def body(payload):
        sent = {item["编号"] for item in payload["新闻"]}
        assert sent == {"early", "s1", "s2", "s3"}
        return {
            "解释": [
                {"编号": "s1", "怎么影响": "第一条强原因", "强弱": "强"},
                {"编号": "s2", "怎么影响": "第二条强原因", "强弱": "强"},
                {"编号": "s3", "怎么影响": "第三条强原因", "强弱": "强"},
                {"编号": "early", "怎么影响": "早看到的弱原因", "强弱": "弱"},
            ]
        }

    text = _page_items([weak, *late], Reply(body))
    assert _reasons(text) == ["第一条强原因（强）", "第二条强原因（强）", "第三条强原因（强）"]
    assert "早看到的弱原因" not in text
    assert "另有 1 条较弱的可能原因" in text
    assert "我们当时看到了吗：波动前已经看到这条新闻" in text
    assert "分不清先后" not in text


def _page_items(items, client):
    result = run_scheduled(MORNING, anomalies=[_move()], items=items, client=client)
    assert [page["trade_date"] for page in result["daily_pages"]] == [DAY]
    return result["daily_pages"][0]["text"]


@pytest.mark.phase1_blocking
def test_every_page_uses_plain_words():
    ten = [
        ("n1", "弱", "第一条弱"),
        ("n2", "强", "第二条强"),
        ("n3", "中", "第三条中"),
        ("n4", "弱", "第四条弱"),
        ("n5", "强", "第五条强"),
        ("n6", "弱", "第六条弱"),
        ("n7", "强", "第七条强"),
        ("n8", "中", "第八条中"),
        ("n9", "弱", "第九条弱"),
        ("n10", "弱", "第十条弱"),
    ]
    three = [("n1", "中", "中等这条"), ("n2", "弱", "弱的这条"), ("n3", "强", "强的这条")]
    missing = [("n1", "", "没有强弱"), ("n2", "弱", "第一条弱"), ("n3", "中", "中等这条"), ("n4", "弱", "第二条弱")]
    pages = [_page(ten, _reply(ten)), _page(three, _reply(three)), _page(missing, _reply(missing))]
    weak = _item("early", EARLY, "早看到的弱原因")
    late = [
        _item(info_id, datetime(2026, 10, 15, hour, tzinfo=timezone.utc), headline, date_only=True)
        for info_id, hour, headline in (
            ("s1", 4, "第一条强原因"),
            ("s2", 5, "第二条强原因"),
            ("s3", 6, "第三条强原因"),
        )
    ]

    def body(_payload):
        return {
            "解释": [
                {"编号": "s1", "怎么影响": "第一条强原因", "强弱": "强"},
                {"编号": "s2", "怎么影响": "第二条强原因", "强弱": "强"},
                {"编号": "s3", "怎么影响": "第三条强原因", "强弱": "强"},
                {"编号": "early", "怎么影响": "早看到的弱原因", "强弱": "弱"},
            ]
        }

    pages.append(_page_items([weak, *late], Reply(body)))
    for text in pages:
        _assert_plain(text)
