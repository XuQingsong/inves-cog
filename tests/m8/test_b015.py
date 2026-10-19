"""B-015 news card, move card, and the daily page. Injected replies only."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.ingest.info import make_item
from inves_cog.ingest.news_card import QUESTION, read_card
from inves_cog.ingest.triage import NewsTriage
from inves_cog.perception.attribution.move_card import daily_text, move_card

T0 = datetime(2026, 10, 29, 0, 30, tzinfo=timezone.utc)


class Clock:
    def now_utc(self):
        return T0


class Scripted:
    def __init__(self, news_reply):
        self.news_reply = news_reply
        self.tasks = []
        self.payloads = []

    def call(self, task, payload):
        self.tasks.append(task)
        self.payloads.append(payload)
        if task == "news_card":
            return self.news_reply
        if task == "info_fields_extraction":
            return {"is_guidance": False, "is_rating_change": False}
        if task == "entity_tagging":
            return {"items": []}
        raise AssertionError(task)


def _engine(llm):
    entities = [{"entity_id": "apple", "name": "Apple", "aliases": ["iPhone"], "tickers": ["AAPL"]}]
    return NewsTriage(
        llm=llm,
        embed=lambda *args, **kwargs: [0.1] * 1024,
        entities=entities,
        monitored_ids=set(),
        pool_tickers={"AAPL"},
        clock=Clock(),
    )


def _item(identifier, headline, *, tickers=(), days=0):
    return make_item(
        "news",
        "Fixture",
        identifier,
        headline=headline,
        body="Original fixture evidence.",
        tickers=tickers,
        published_at=T0 - timedelta(days=days),
        clock=Clock(),
    )


def _card_reply(*companies, outside=(), summary="一条新闻"):
    return {
        "说了什么": summary,
        "行业": ["软件"],
        "名单内": list(companies),
        "名单外": list(outside),
    }


def _company(code, name, *, direction="利好", reason="模型写了这家", relation="新闻点了名", level="高"):
    return {
        "代码": code,
        "名称": name,
        "方向": direction,
        "理由": reason,
        "关系": relation,
        "重要程度": level,
    }


@pytest.mark.phase1_blocking
def test_layer3_does_not_call_news_card_and_layer2_calls_it_once():
    llm = Scripted(_card_reply(summary="细读"))
    recent = _item("recent", "A company reports", tickers=["AAPL"])
    old = _item("old", "Apple historic event", days=31)
    results = _engine(llm).process([recent, old])
    assert [row["extraction_source"]["news_triage"]["layer"] for row in results] == [2, 3]
    assert llm.tasks.count("news_card") == 1
    assert llm.tasks.count("entity_tagging") == 0
    assert "anomaly_candidates" not in llm.tasks
    assert results[0]["extraction_source"]["news_card"]["说了什么"] == "细读"
    assert "news_card" not in results[1]["extraction_source"]
    sent = llm.payloads[0]
    assert sent["问法"] == QUESTION
    assert sent["正文"] == "Original fixture evidence."
    meta = next(row for row in sent["跟踪名单"] if row["名称"] == "Meta AI")
    assert meta["代码"] == "META" and "Muse" in meta["别名"]


@pytest.mark.phase1_blocking
def test_injected_replies_keep_meta_and_companies_outside_the_list():
    reply = _card_reply(
        _company("META", "Meta Platforms", direction="利好", reason="Muse 是它的产品", relation="是它的产品"),
        _company("", "店外公司", direction="不确定", reason="名单里没有", relation="同行业", level="低"),
        summary="Muse 登顶",
    )
    card = _store("muse", "Muse is the No. 1 free iPhone app", reply)
    assert [row["代码"] for row in card["名单内"]] == ["META"]
    assert [row["名称"] for row in card["名单外"]] == ["店外公司"]
    assert card["名单内"][0]["理由"] == "Muse 是它的产品"


@pytest.mark.phase1_blocking
def test_injected_coreweave_dell_and_r1_replies_keep_their_tickers():
    kept = {
        "crwv": ("CoreWeave Bond Yield Hits 15%", "CRWV", "CoreWeave"),
        "dell": ("Barclays Downgrades Dell Technologies", "DELL", "Dell Technologies"),
        "r1": ("DeepSeek R1 was released that day", "NVDA", "NVIDIA"),
    }
    for identifier, (headline, code, name) in kept.items():
        card = _store(identifier, headline, _card_reply(_company(code, name), summary=headline))
        assert [row["代码"] for row in card["名单内"]] == [code]
        assert card["名单外"] == []


def _store(identifier, headline, reply):
    llm = Scripted(reply)
    item = _item(identifier, headline)
    result = _engine(llm).process([item], on_demand=True)[0]
    assert llm.tasks.count("news_card") == 1
    return result["extraction_source"]["news_card"]


@pytest.mark.phase1_blocking
def test_short_news_id_matches_one_full_id_and_two_matches_are_dropped():
    move = {
        "股票": ["NVDA"],
        "方向": "跌",
        "幅度": "-3%",
        "日期": "2026-10-14",
        "开始": "2026-10-14T14:30:00Z",
    }
    only = {
        "编号": "news:benzinga:62345955",
        "发布时间": "2026-10-13T12:00:00Z",
        "钟点清楚": True,
        "标题": "CoreWeave",
        "说了什么": "债券收益率升高，利空",
        "当时标到": True,
    }

    class MoveLLM:
        def __init__(self, reply):
            self.reply = reply
            self.tasks = []

        def call(self, task, payload):
            self.tasks.append(task)
            self.payload = payload
            return self.reply

    unique = MoveLLM({"解释": [{"编号": "benzinga:62345955", "怎么影响": "融资变贵", "强弱": "强"}]})
    result = move_card(move, [only], unique)
    assert unique.tasks == ["move_card"]
    assert result["解释"][0]["编号"] == "news:benzinga:62345955"
    assert result["丢掉"] == 0
    assert result["解释"][0]["新闻卡原句"] == "债券收益率升高，利空"
    assert result["解释"][0]["波动卡原句"] == "融资变贵"

    ambiguous = MoveLLM({"解释": [{"编号": "benzinga:62345955", "怎么影响": "说不清", "强弱": "弱"}]})
    twin = dict(only, 编号="wire:benzinga:62345955", 标题="另一条")
    dropped = move_card(move, [only, twin], ambiguous)
    assert dropped["解释"] == []
    assert dropped["丢掉"] == 1
    assert ambiguous.tasks == ["move_card"]


@pytest.mark.phase1_blocking
def test_date_only_news_on_the_move_day_is_not_seen_ahead():
    move = {
        "股票": ["WDC", "STX"],
        "方向": "跌",
        "幅度": "-4%",
        "日期": "2026-10-02",
        "开始": "2026-10-02T14:30:00Z",
    }
    card = {
        "编号": "toshiba",
        "发布时间": "2026-10-02",
        "钟点清楚": False,
        "标题": "Toshiba expands",
        "说了什么": "扩产，对硬盘同行利好",
        "当时标到": True,
    }

    class MoveLLM:
        def call(self, task, payload):
            assert task == "move_card"
            return {"解释": [{"编号": "toshiba", "怎么影响": "供给增加所以利空", "强弱": "中"}]}

    result = move_card(move, [card], MoveLLM())
    assert result["归类"] == "同一天，发布钟点不清楚"
    assert result["归类"] != "提前看到"
    assert result["解释"][0]["当时已经知道"] is False
    assert result["解释"][0]["新闻卡原句"] == "扩产，对硬盘同行利好"
    assert result["解释"][0]["波动卡原句"] == "供给增加所以利空"


@pytest.mark.phase1_blocking
def test_move_card_path_does_not_call_anomaly_candidates():
    source = Path(__file__).parents[2].joinpath("src/inves_cog/perception/attribution/move_card.py").read_text()
    assert "anomaly_candidates" not in source
    seen = []

    class MoveLLM:
        def call(self, task, payload):
            seen.append(task)
            return {"解释": "没有"}

    result = move_card(
        {"股票": ["CRWV"], "方向": "跌", "幅度": "-5%", "日期": "2026-10-14", "开始": "2026-10-14T14:30:00Z"},
        [],
        MoveLLM(),
    )
    assert seen == ["move_card"]
    assert result["解释"] == []
    assert result["归类"] == "查过没有消息"


@pytest.mark.phase1_blocking
def test_daily_page_folds_a_wide_medium_list_and_keeps_the_card():
    companies = [
        {"代码": f"T{index:02d}", "名称": f"公司{index:02d}", "方向": "不确定", "理由": "同日", "重要程度": "中"}
        for index in range(62)
    ]
    card = {"编号": "cpi", "说了什么": "CPI 高于预期", "名单内": companies, "名单外": []}
    text = daily_text(
        moves=[{"股票": ["NVDA"], "方向": "跌", "幅度": "-2%", "解释": [], "归类": "查过没有消息"}],
        news_cards=[card],
        valuation={"NVDA": "100"},
        plan={"规则": "A"},
    )
    assert "CPI 高于预期 影响 62 家" in text
    assert "公司00" not in text and "公司61" not in text
    assert len(card["名单内"]) == 62
    assert "没找到能解释这次波动的新闻" in text
    assert "新闻和波动的解释，不会改变估值和计划。" in text
    assert text.index("NVDA") < text.index("没找到能解释这次波动的新闻")
    assert text.index("没找到能解释这次波动的新闻") < text.index("没找到相关新闻")
    assert text.index("没找到相关新闻") < text.index("CPI 高于预期 影响 62 家")
    assert text.index("CPI 高于预期 影响 62 家") < text.index("新闻和波动的解释，不会改变估值和计划。")


@pytest.mark.phase1_blocking
def test_b014_empty_company_list_examples_are_gone():
    import tests.m8.test_b014 as previous

    forbidden = {
        "test_deepseek_headline_lists_no_tracked_company",
        "test_muse_headline_does_not_mark_meta",
        "test_toshiba_headline_does_not_mark_stx_or_wdc",
    }
    assert forbidden.isdisjoint(dir(previous))
    assert read_card({"说了什么": "", "行业": [], "名单内": [], "名单外": []}, [])["名单内"] == []
