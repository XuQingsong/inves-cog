"""B-021: look the ticker up again when nothing matches or fewer than five items were sent."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)
WINDOW = START - timedelta(days=7)


class Script:
    def call(self, task, payload):
        if task != "move_card":
            raise AssertionError(task)
        cited = payload["新闻"][0]["编号"]
        return {"解释": [{"编号": cited, "怎么影响": "供应变化", "强弱": "中"}]}


class Lookup:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        return self.rows


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


def _card(said):
    return {
        "说了什么": said,
        "名单内": [{"代码": "META", "名称": "Meta Platforms", "方向": "利好", "理由": "同日", "重要程度": "高"}],
        "名单外": [],
    }


def _item(identifier, published, said):
    return {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": said,
        "tickers": ["META"],
        "entities": ["META"],
        "source_root": identifier,
        "extraction_source": {"news_card": _card(said)},
    }


def _run(anomalies, items, lookup, when=None):
    return run_scheduled(
        when or MORNING,
        anomalies=anomalies,
        items=items,
        client=Script(),
        news_lookup=lookup,
    )


def _page(result):
    assert [page["trade_date"] for page in result["daily_pages"]] == ["2026-10-14"]
    return result["daily_pages"][0]["text"]


@pytest.mark.phase1_blocking
def test_lookup_before_the_move_is_missed_not_already_seen():
    found = _item("news:found", START - timedelta(hours=3), "库里没有的这条")
    lookup = Lookup([found])
    text = _page(_run([_anomaly()], [], lookup))
    assert "当时没收到这条新闻，事后才找到" in text
    assert "news:found" not in text
    assert "提前看到" not in text
    assert text.count("库里没有的这条") == 1
    assert lookup.calls == [("META", WINDOW, MORNING)]


@pytest.mark.phase1_blocking
def test_empty_lookup_stays_no_news():
    lookup = Lookup([])
    text = _page(_run([_anomaly()], [], lookup))
    assert "没找到相关新闻" in text
    assert "没采到" not in text
    assert lookup.calls == [("META", WINDOW, MORNING)]


@pytest.mark.phase1_blocking
def test_six_matched_items_skip_the_lookup():
    items = [_item(f"news:{index}", START - timedelta(hours=index), f"第{index}条") for index in range(1, 7)]
    lookup = Lookup([_item("news:extra", START - timedelta(hours=1), "不该再查")])
    text = _page(_run([_anomaly()], items, lookup))
    assert "供应变化" in text
    assert "不该再查" not in text
    assert lookup.calls == []


@pytest.mark.phase1_blocking
def test_lookup_after_the_move_is_labeled_and_not_already_known():
    later = _item("news:after", START + timedelta(hours=2), "晚公开的这条")
    lookup = Lookup([later])
    text = _page(_run([_anomaly()], [], lookup))
    assert "（波动开始后才发布）" in text
    assert "news:after" not in text
    assert "没找到相关新闻" in text
    assert "提前看到" not in text
    assert "没采到" not in text
    assert text.count("晚公开的这条") == 1
    assert lookup.calls == [("META", WINDOW, MORNING)]


@pytest.mark.phase1_blocking
def test_three_matched_items_still_look_up():
    items = [_item(f"news:{index}", START - timedelta(hours=index), f"第{index}条") for index in range(1, 4)]
    lookup = Lookup([])
    _page(_run([_anomaly()], items, lookup))
    assert lookup.calls == [("META", WINDOW, MORNING)]


@pytest.mark.phase1_blocking
def test_half_past_nine_does_not_look_up_or_write_a_page():
    lookup = Lookup([_item("news:found", START - timedelta(hours=3), "库里没有的这条")])
    result = _run([_anomaly()], [], lookup, when=MORNING.replace(hour=9, minute=30))
    assert result["task_name"] == "attribution_tracks"
    assert "daily_pages" not in result
    assert lookup.calls == []
