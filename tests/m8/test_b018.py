"""B-018: one morning page per trading day, with valuation, plan, and date-only clocks."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled

MORNING = datetime.fromisoformat("2026-10-15T09:15:00+08:00")
START = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)
DAY = "2026-10-14"


class Script:
    def __init__(self):
        self.tasks = []

    def call(self, task, payload):
        self.tasks.append(task)
        if task != "move_card":
            raise AssertionError(task)
        cited = payload["新闻"][0]["编号"]
        name = payload["波动"]["股票"][0]
        return {"解释": [{"编号": cited, "怎么影响": f"{name} 供应变化", "强弱": "中"}]}


def _anomaly(anomaly_id, ticker):
    return {
        "anomaly_id": anomaly_id,
        "started_at": START,
        "trade_date": DAY,
        "session": "open",
        "universe": "pool",
        "direction": "涨",
        "幅度": "11%",
        "members": [{"ticker": ticker}],
        "baskets": [],
    }


def _card(said="这条新闻", level="高", count=1, ticker="META"):
    companies = []
    for index in range(count):
        code = ticker if count == 1 else f"T{index:02d}"
        companies.append(
            {
                "代码": code,
                "名称": code if count == 1 else f"公司{index:02d}",
                "方向": "利好",
                "理由": "同日",
                "重要程度": level,
            }
        )
    return {"说了什么": said, "名单内": companies, "名单外": []}


def _item(identifier, published, card, ticker, *, date_only=False):
    item = {
        "info_id": identifier,
        "published_at": published,
        "first_seen_at": published,
        "headline": card.get("说了什么") or identifier,
        "tickers": [ticker],
        "entities": [ticker],
        "source_root": identifier,
        "extraction_source": {"news_card": card},
    }
    if date_only:
        item["flags"] = ["published_at_date_only"]
    return item


def _valuation():
    return [
        {
            "trade_date": DAY,
            "ticker": "META",
            "status": "ok",
            "bear": 424,
            "neutral": 478,
            "bull": 531,
            "payload": {},
        },
        {
            "trade_date": DAY,
            "ticker": "INTC",
            "status": "unvalued",
            "bear": None,
            "neutral": None,
            "bull": None,
            "payload": {"reason": "亏损且无增长"},
        },
    ]


def _plan():
    return [
        {
            "trade_date": DAY,
            "payload": {
                "orders": [{"ticker": "META", "action": "buy_to", "qty": None, "fraction": 0.05, "value": 1000}]
            },
        }
    ]


def _run(anomalies, items, client=None, valuation=None, plan=None, when=None):
    return run_scheduled(
        when or MORNING,
        anomalies=anomalies,
        items=items,
        client=client or Script(),
        valuation=valuation,
        plan=plan,
    )


def _page(result, trade_date=DAY):
    matched = [page for page in result["daily_pages"] if page["trade_date"] == trade_date]
    assert len(matched) == 1
    return matched[0]["text"]


@pytest.mark.phase1_blocking
def test_one_morning_page_lists_both_tracked_moves():
    meta = _item("news:meta", START - timedelta(hours=2), _card("Meta 新闻"), "META")
    nvda = _item("news:nvda", START - timedelta(hours=3), _card("NVDA 新闻", ticker="NVDA"), "NVDA")
    client = Script()
    result = _run([_anomaly("meta-up", "META"), _anomaly("nvda-up", "NVDA")], [meta, nvda], client)
    assert client.tasks == ["move_card", "move_card"]
    assert "anomaly_candidates" not in client.tasks
    assert "claim_extraction" not in client.tasks
    assert len(result["daily_pages"]) == 1
    text = _page(result)
    assert "META 供应变化" in text
    assert "NVDA 供应变化" in text
    assert text.count("提前看到") >= 2


@pytest.mark.phase1_blocking
def test_morning_page_prints_one_valuation_and_one_plan_order():
    news = _item("news:meta", START - timedelta(hours=2), _card(), "META")
    valuation, plan = _valuation(), _plan()
    before_valuation, before_plan = deepcopy(valuation), deepcopy(plan)
    text = _page(_run([_anomaly("meta-up", "META")], [news], valuation=valuation, plan=plan))
    assert "META 424 / 478 / 531" in text
    assert "INTC 不估：亏损且无增长" in text
    assert "META buy_to 0.05" in text
    assert "{}" not in text
    assert valuation == before_valuation
    assert plan == before_plan


@pytest.mark.phase1_blocking
def test_morning_page_names_a_missing_valuation_and_plan():
    text = _page(_run([_anomaly("meta-up", "META")], []))
    assert "估值没有拿到" in text
    assert "计划没有拿到" in text
    assert "{}" not in text


@pytest.mark.phase1_blocking
def test_same_day_date_only_news_is_not_already_seen():
    published = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)
    news = _item("news:meta", published, _card("只有日期"), "META", date_only=True)
    result = _run([_anomaly("meta-up", "META")], [news])
    text = _page(result)
    assert "同一天，发布钟点不清楚" in text
    assert "提前看到" not in text
    explanation = result["rows"][0]["move_card"]["解释"][0]
    assert explanation["当时已经知道"] is False


@pytest.mark.phase1_blocking
def test_earlier_date_only_news_was_already_known():
    published = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    news = _item("news:meta", published, _card("更早只有日期"), "META", date_only=True)
    result = _run([_anomaly("meta-up", "META")], [news])
    assert "提前看到" in _page(result)
    explanation = result["rows"][0]["move_card"]["解释"][0]
    assert result["rows"][0]["move_card"]["归类"] == "提前看到"
    assert explanation["当时已经知道"] is True


@pytest.mark.phase1_blocking
def test_quiet_day_still_prints_high_news_valuation_and_plan():
    published = datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)
    news = _item("news:meta", published, _card("这条新闻"), "META")
    client = Script()
    result = _run([], [news], client, valuation=_valuation(), plan=_plan())
    assert client.tasks == []
    text = _page(result)
    assert "没有不寻常波动" in text
    assert "这条新闻" in text
    assert "META 424 / 478 / 531" in text
    assert "META buy_to 0.05" in text


@pytest.mark.phase1_blocking
def test_wide_medium_list_folds_without_a_move_card():
    published = datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc)
    news = _item("news:cpi", published, _card("CPI", level="中", count=9), "META")
    client = Script()
    text = _page(_run([], [news], client))
    assert client.tasks == []
    assert "标了名单里的一大片（9 家）" in text


@pytest.mark.phase1_blocking
def test_later_slots_do_not_return_a_daily_page():
    tracks = _run([], [], when=MORNING.replace(hour=9, minute=30))
    labels = _run([], [], when=MORNING.replace(hour=12, minute=30))
    assert tracks["task_name"] == "attribution_tracks"
    assert labels["task_name"] == "attribution_labels"
    assert "daily_pages" not in tracks
    assert "daily_pages" not in labels
