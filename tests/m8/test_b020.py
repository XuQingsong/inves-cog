"""B-020: the morning run writes one page, for the session that just closed."""

from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
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


def _card(said, level="高"):
    return {
        "说了什么": said,
        "名单内": [{"代码": "META", "名称": "Meta Platforms", "方向": "利好", "理由": "同日", "重要程度": level}],
        "名单外": [],
    }


def _item(identifier, published, said, level="高"):
    return {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": said,
        "tickers": ["META"],
        "entities": ["META"],
        "source_root": identifier,
        "extraction_source": {"news_card": _card(said, level)},
    }


def _run(anomalies, items, when=None):
    return run_scheduled(when or MORNING, anomalies=anomalies, items=items, client=Script())


@pytest.mark.phase1_blocking
def test_morning_run_keeps_only_the_closed_session():
    items = [
        _item("news:12", datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc), "十二日的高"),
        _item("news:13", datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc), "十三日的高"),
        _item("news:14", START - timedelta(hours=2), "十四日的高"),
    ]
    result = _run([_anomaly()], items)
    assert [page["trade_date"] for page in result["daily_pages"]] == ["2026-10-14"]
    text = result["daily_pages"][0]["text"]
    assert "META" in text
    assert "十一" in text or "11%" in text
    assert "十二日的高" not in text
    assert "十三日的高" not in text


@pytest.mark.phase1_blocking
def test_section_four_keeps_high_and_drops_low():
    published = datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)
    items = [
        _item("news:high", published, "高的这条", "高"),
        _item("news:low", published, "低的这条", "低"),
    ]
    text = _run([], items)["daily_pages"][0]["text"]
    assert "高的这条" not in text
    assert "低的这条" not in text
    assert "没有持仓快照" in text
    assert "还有 1 条标了高，这里不展开" in text


@pytest.mark.phase1_blocking
def test_quiet_closed_session_does_not_print_an_older_high_card():
    older = _item("news:12", datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc), "十二日的高")
    result = _run([], [older])
    assert [page["trade_date"] for page in result["daily_pages"]] == ["2026-10-14"]
    text = result["daily_pages"][0]["text"]
    assert "没有不寻常波动" in text
    assert "十二日的高" not in text


@pytest.mark.phase1_blocking
def test_later_slots_still_omit_the_page():
    tracks = _run([], [], when=MORNING.replace(hour=9, minute=30))
    labels = _run([], [], when=MORNING.replace(hour=12, minute=30))
    assert tracks["task_name"] == "attribution_tracks"
    assert labels["task_name"] == "attribution_labels"
    assert "daily_pages" not in tracks
    assert "daily_pages" not in labels
