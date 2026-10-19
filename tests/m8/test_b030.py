"""B-030: keep a move reply under the field names already seen, and write Saturday."""

import re
from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.chain import run_scheduled
from inves_cog.perception.attribution.morning import main

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
DAY = "2026-10-15"
EARLY = datetime(2026, 10, 15, 13, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc)
KNOWN = datetime.fromisoformat("2026-10-15T21:00:00+08:00")
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
        if callable(self.body):
            return self.body(payload)
        return self.body


def _move(anomaly_id, *, session="close", direction="down", ret="-0.0573"):
    return {
        "anomaly_id": anomaly_id,
        "trade_date": DAY,
        "session": session,
        "universe": "pool",
        "direction": direction,
        "members": [{"ticker": "JNJ", "ret": ret}],
        "baskets": [],
    }


def _item(info_id, published, headline):
    return {
        "info_id": info_id,
        "published_at": published,
        "first_seen_at": published,
        "headline": headline,
        "tickers": ["JNJ"],
        "entities": ["JNJ"],
        "source_root": info_id,
        "extraction_source": {"news_card": {"说了什么": headline, "名单内": [], "钟点清楚": True}},
    }


def _page(anomalies, items, client):
    result = run_scheduled(MORNING, anomalies=anomalies, items=items, client=client)
    assert [page["trade_date"] for page in result["daily_pages"]] == [DAY]
    return result["daily_pages"][0]["text"]


def _assert_plain(text):
    for word in FORBIDDEN:
        assert word not in text
    assert re.search(r"-\d+(?:\.\d+)?%", text) is None
    assert re.search(r"\d+\.\d{3,}", text) is None
    assert re.search(r"[a-z]+_[a-z0-9_]+", text) is None


@pytest.mark.phase1_blocking
def test_matches_keeps_the_sentence_and_the_strength():
    client = Reply(
        lambda payload: {"matches": [{"编号": payload["新闻"][0]["编号"], "理由": "试验好于预期", "强度": "强"}]}
    )
    text = _page([_move("jnj")], [_item("a1", EARLY, "强生公布试验")], client)
    assert "试验好于预期（强）" in text
    assert "没找到能解释这次波动的新闻" not in text


@pytest.mark.phase1_blocking
def test_answer_keeps_a_medium_sentence():
    client = Reply(
        lambda payload: {"answer": [{"编号": payload["新闻"][0]["编号"], "影响": "需求比预期强", "强度": "中"}]}
    )
    text = _page([_move("jnj")], [_item("a1", EARLY, "需求变化")], client)
    assert "需求比预期强（中）" in text
    assert "没找到能解释这次波动的新闻" not in text


@pytest.mark.phase1_blocking
def test_cards_translate_english_field_names():
    client = Reply(
        lambda payload: {
            "cards": [{"news_id": payload["新闻"][0]["编号"], "relation": "供应比预期紧", "strength": "strong"}]
        }
    )
    text = _page([_move("jnj")], [_item("a1", EARLY, "供应变化")], client)
    assert "供应比预期紧（强）" in text
    assert "没找到能解释这次波动的新闻" not in text


@pytest.mark.phase1_blocking
def test_a_no_is_not_printed_and_does_not_count_as_already_seen():
    def reply(payload):
        ids = [item["编号"] for item in payload["新闻"]]
        return {
            "解释": [
                {"编号": ids[0], "怎么影响": "第一条对得上", "强弱": "强", "能解释": "是"},
                {"编号": ids[1], "怎么影响": "这条解释不了", "强弱": "弱", "能解释": "否"},
                {"编号": ids[2], "怎么影响": "第二条也对得上", "强弱": "中"},
            ]
        }

    text = _page(
        [_move("jnj")],
        [_item("a1", EARLY, "第一条"), _item("a2", EARLY, "第二条"), _item("a3", EARLY, "第三条")],
        Reply(reply),
    )
    assert "第一条对得上（强）" in text
    assert "第二条也对得上（中）" in text
    assert "这条解释不了" not in text

    def only_no(payload):
        cited = payload["新闻"][0]["编号"]
        return {
            "解释": [
                {"编号": cited, "怎么影响": "这条解释不了", "能解释": "否"},
                {"编号": "late-1", "怎么影响": "晚的一条", "能解释": "是"},
                {"编号": "late-2", "怎么影响": "另一条晚的", "能解释": "是"},
            ]
        }

    quiet = _page(
        [_move("jnj-quiet")],
        [
            _item("early-no", EARLY, "解释不了的那条"),
            _item("late-1", LATE, "晚的一条"),
            _item("late-2", LATE, "另一条晚的"),
        ],
        Reply(only_no),
    )
    assert "这条解释不了" not in quiet
    assert "晚的一条" not in quiet
    assert "波动前已经看到这条新闻" not in quiet


@pytest.mark.phase1_blocking
def test_the_question_describes_the_move_the_way_the_page_does():
    client = Reply({"解释": "没有"})
    text = _page(
        [_move("jnj-post", session="post", direction="down", ret="0.00208")], [_item("a1", EARLY, "盘后消息")], client
    )
    asked = client.payloads[0]
    move = asked["波动"]
    assert move["方向"] == "涨"
    assert move["幅度"] == "0.2%"
    assert move["时段"] == "盘后"
    assert move["和同类比"] == "弱于同类"
    for word in ("解释", "编号", "怎么影响", "强弱", "能解释"):
        assert word in asked["问法"]
    assert "down" not in move.values() and "up" not in move.values()
    assert move["幅度"]
    assert "没找到能解释这次波动的新闻" in text


@pytest.mark.phase1_blocking
def test_none_is_a_normal_empty_reply():
    text = _page([_move("jnj")], [_item("a1", EARLY, "一条消息")], Reply({"解释": "没有"}))
    assert "没找到能解释这次波动的新闻" in text


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def now_utc(self):
        return self.moment


class Boom:
    def __init__(self):
        self.calls = 0

    def call(self, task, payload):
        self.calls += 1
        raise RuntimeError(task)


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


class Database:
    def __init__(self, plans=None):
        self.plans = list(plans or [])
        self.jobs = []
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        compact = " ".join(statement.split())
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {"id": len(self.jobs) + 1, "status": "failed", "error_summary": None}
            self.jobs.append(row)
            return Cursor([{"id": row["id"]}])
        if compact.startswith("UPDATE ingest.job_runs"):
            _ended, status, count, error, row_id = params
            found = next(job for job in self.jobs if job["id"] == row_id)
            found.update(status=status, processed_count=count, error_summary=error)
            return Cursor([])
        if "trading.plan" in compact:
            portfolio, through, cutoff = params[0], params[1], params[2]
            chosen = [
                row
                for row in self.plans
                if row.get("portfolio_id") == portfolio
                and row.get("published") is True
                and row.get("extractor") == "fixed"
                and _day(row["signal_date"]) <= _day(through)
                and row["generated_at"] <= cutoff
            ]
            chosen.sort(key=lambda row: (_day(row["signal_date"]), row["generated_at"]), reverse=True)
            return Cursor(chosen[:1])
        return Cursor([])


def _invoke(directory, data, moment, client, monkeypatch):
    monkeypatch.setenv("INVES_COG_PAGE_DIR", str(directory))
    code = main([], connection=data, clock=Clock(moment), client=client)
    files = sorted(directory.glob("daily_page_*.txt"))
    text = files[0].read_text(encoding="utf-8") if len(files) == 1 else None
    return code, text, files


@pytest.mark.phase1_blocking
def test_saturday_writes_and_sunday_monday_and_a_holiday_do_not(tmp_path, monkeypatch):
    boom = Boom()
    code, text, files = _invoke(
        tmp_path / "saturday", Database(), datetime.fromisoformat("2026-10-17T09:15:00+08:00"), boom, monkeypatch
    )
    assert code == 0 and boom.calls == 0
    assert [path.name for path in files] == ["daily_page_2026-10-16.txt"]
    assert text
    for moment in (
        datetime.fromisoformat("2026-10-18T09:15:00+08:00"),
        datetime.fromisoformat("2026-10-19T09:15:00+08:00"),
        datetime.fromisoformat("2026-11-27T10:15:00+08:00"),
    ):
        data = Database()
        idle, page, written = _invoke(tmp_path / moment.date().isoformat(), data, moment, boom, monkeypatch)
        assert idle == 0 and page is None and written == [] and data.jobs == [] and data.calls == []
    assert boom.calls == 0


@pytest.mark.phase1_blocking
def test_plan_lines_use_labels_and_notional_estimates(tmp_path, monkeypatch):
    plan = {
        "portfolio_id": "paper-fixed",
        "signal_date": DAY,
        "trade_date": "2026-10-16",
        "extractor": "fixed",
        "rule_set": "A",
        "published": True,
        "generated_at": KNOWN,
        "payload": {
            "orders": [
                {
                    "ticker": "MU",
                    "action": "buy_to",
                    "label": "确认加仓",
                    "value": None,
                    "notional_est": 22869.85,
                    "qty": None,
                },
                {
                    "ticker": "HD",
                    "action": "buy_watch",
                    "label": "观察波段买入",
                    "value": 25000.0,
                    "notional_est": 25000.0,
                },
                {"ticker": "WDC", "action": "buy_swing", "value": 15980.54},
            ]
        },
    }
    _code, text, _files = _invoke(tmp_path, Database([plan]), MORNING, Boom(), monkeypatch)
    assert "MU 确认加仓 约 22,869.85 美元" in text
    assert "HD 观察波段买入 约 25,000.00 美元" in text
    assert "WDC 约 15,980.54 美元" in text
    assert "buy_" not in text


@pytest.mark.phase1_blocking
def test_every_page_uses_plain_words(tmp_path, monkeypatch):
    pages = [
        _page(
            [_move("jnj")],
            [_item("a1", EARLY, "强生公布试验")],
            Reply(
                lambda payload: {
                    "matches": [{"编号": payload["新闻"][0]["编号"], "理由": "试验好于预期", "强度": "强"}]
                }
            ),
        ),
        _page(
            [_move("jnj")],
            [_item("a1", EARLY, "需求变化")],
            Reply(
                lambda payload: {"answer": [{"编号": payload["新闻"][0]["编号"], "影响": "需求比预期强", "强度": "中"}]}
            ),
        ),
        _page(
            [_move("jnj")],
            [_item("a1", EARLY, "供应变化")],
            Reply(
                lambda payload: {
                    "cards": [{"news_id": payload["新闻"][0]["编号"], "relation": "供应比预期紧", "strength": "strong"}]
                }
            ),
        ),
        _page(
            [_move("jnj")],
            [_item("a1", EARLY, "第一条"), _item("a2", EARLY, "第二条"), _item("a3", EARLY, "第三条")],
            Reply(
                lambda payload: {
                    "解释": [
                        {"编号": payload["新闻"][0]["编号"], "怎么影响": "第一条对得上", "强弱": "强", "能解释": "是"},
                        {"编号": payload["新闻"][1]["编号"], "怎么影响": "这条解释不了", "强弱": "弱", "能解释": "否"},
                        {"编号": payload["新闻"][2]["编号"], "怎么影响": "第二条也对得上", "强弱": "中"},
                    ]
                }
            ),
        ),
        _page(
            [_move("jnj-quiet")],
            [
                _item("early-no", EARLY, "解释不了的那条"),
                _item("late-1", LATE, "晚的一条"),
                _item("late-2", LATE, "另一条晚的"),
            ],
            Reply(
                lambda payload: {
                    "解释": [
                        {"编号": payload["新闻"][0]["编号"], "怎么影响": "这条解释不了", "能解释": "否"},
                        {"编号": "late-1", "怎么影响": "晚的一条", "能解释": "是"},
                        {"编号": "late-2", "怎么影响": "另一条晚的", "能解释": "是"},
                    ]
                }
            ),
        ),
        _page([_move("jnj")], [_item("a1", EARLY, "一条消息")], Reply({"解释": "没有"})),
        _page(
            [_move("jnj-post", session="post", direction="down", ret="0.00208")],
            [_item("a1", EARLY, "盘后消息")],
            Reply({"解释": "没有"}),
        ),
    ]
    _code, saturday, _files = _invoke(
        tmp_path / "saturday", Database(), datetime.fromisoformat("2026-10-17T09:15:00+08:00"), Boom(), monkeypatch
    )
    pages.append(saturday)
    plan = {
        "portfolio_id": "paper-fixed",
        "signal_date": DAY,
        "trade_date": "2026-10-16",
        "extractor": "fixed",
        "rule_set": "A",
        "published": True,
        "generated_at": KNOWN,
        "payload": {
            "orders": [
                {"ticker": "MU", "action": "buy_to", "label": "确认加仓", "value": None, "notional_est": 22869.85},
                {"ticker": "HD", "action": "buy_watch", "label": "观察波段买入", "value": 25000.0},
                {"ticker": "WDC", "action": "buy_swing", "value": 15980.54},
            ]
        },
    }
    _code, planned, _files = _invoke(tmp_path / "plan", Database([plan]), MORNING, Boom(), monkeypatch)
    pages.append(planned)
    for text in pages:
        _assert_plain(text)
