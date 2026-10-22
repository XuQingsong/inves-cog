"""B-029: the morning command reads what it already knew and writes the page."""

import json
import re
from datetime import datetime, timezone

import pytest

from inves_cog.perception.attribution.morning import main

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
DAY = "2026-10-15"
KNOWN = datetime.fromisoformat("2026-10-15T21:00:00+08:00")
EARLY = datetime(2026, 10, 15, 13, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)
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


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def now_utc(self):
        return self.moment


class Quiet:
    def __init__(self):
        self.calls = 0

    def call(self, task, payload):
        self.calls += 1
        if task != "move_card":
            raise AssertionError(task)
        return {"没有": True}


class Boom:
    def __init__(self):
        self.calls = 0

    def call(self, task, payload):
        self.calls += 1
        raise RuntimeError("Timeout: model down")


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
    def __init__(self, anomalies=None, news=None, ranges=None, bars=None, ledgers=None, plans=None):
        self.anomalies = list(anomalies or [])
        self.news = list(news or [])
        self.ranges = list(ranges or [])
        self.bars = list(bars or [])
        self.ledgers = list(ledgers or [])
        self.plans = list(plans or [])
        self.jobs = []
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        compact = " ".join(statement.split())
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {
                "id": len(self.jobs) + 1,
                "status": "failed",
                "error_summary": None,
                "processed_count": 0,
                "task_name": params[0],
                "trade_date": params[1],
                "params_version": params[3],
            }
            self.jobs.append(row)
            return Cursor([{"id": row["id"]}])
        if compact.startswith("UPDATE ingest.job_runs"):
            ended, status, count, error, row_id = params
            found = next(job for job in self.jobs if job["id"] == row_id)
            found.update(status=status, processed_count=count, error_summary=error, ended_at=ended)
            return Cursor([])
        if "perception.anomalies" in compact:
            rows = [row for row in self.anomalies if _day(row["trade_date"]) == _day(params[0])]
            rows.sort(key=lambda row: (row["session"], row["anomaly_id"]))
            return Cursor(rows)
        if "ingest.info_items" in compact:
            rows = self.news
            if "sec_8k" in compact:
                rows = [row for row in rows if row["kind"] in {"news", "sec_8k"}]
            when, start, until = params
            rows = [row for row in rows if row["first_seen_at"] <= when and start <= row["published_at"] <= until]
            return Cursor(rows)
        if "valuation_v1.ranges" in compact:
            day, cutoff = params
            latest = {}
            for row in self.ranges:
                if _day(row["trade_date"]) != _day(day) or row["observed_at"] > cutoff:
                    continue
                current = latest.get(row["ticker"])
                if current is None or row["observed_at"] > current["observed_at"]:
                    latest[row["ticker"]] = row
            return Cursor(list(latest.values()))
        if "ingest.bars_daily" in compact:
            day, tickers = params
            rows = [row for row in self.bars if _day(row["trade_date"]) == _day(day) and row["ticker"] in tickers]
            return Cursor(rows)
        if "trading.ledger" in compact:
            return Cursor(self._book(self.ledgers, params, "trade_date", "observed_at", compact))
        if "trading.plan" in compact:
            rows = self.plans
            if "published" in compact:
                rows = [row for row in rows if row.get("published") is True]
            return Cursor(self._book(rows, params, "signal_date", "generated_at", compact))
        if compact.startswith("INSERT INTO perception.") or compact.startswith("SELECT "):
            return Cursor([])
        raise AssertionError(compact)

    def _book(self, rows, params, day_key, stamp_key, compact):
        portfolio, through, cutoff = params[0], params[1], params[2]
        chosen = []
        for row in rows:
            if row.get("portfolio_id") != portfolio or _day(row[day_key]) > _day(through):
                continue
            if "extractor='fixed'" in compact and row.get("extractor") != "fixed":
                continue
            if "rule_set='A'" in compact and row.get("rule_set") != "A":
                continue
            if row[stamp_key] > cutoff:
                continue
            chosen.append(row)
        chosen.sort(key=lambda row: (_day(row[day_key]), row[stamp_key]), reverse=True)
        return chosen[:1]


def _news(info_id, published, seen, headline, *, kind="news", tickers=None, level=None, raw=False):
    card = {"说了什么": headline, "名单内": [], "钟点清楚": True}
    if level:
        card["名单内"] = [{"代码": "JNJ", "方向": "不确定", "重要程度": level}]
    source = {"news_card": card}
    return {
        "info_id": info_id,
        "kind": kind,
        "published_at": published,
        "first_seen_at": seen,
        "headline": headline,
        "flags": [],
        "tickers": ["JNJ"] if tickers is None else tickers,
        "entities": [],
        "extraction_source": json.dumps(source, ensure_ascii=False) if raw else source,
    }


def _full_inputs():
    anomalies = [
        {
            "anomaly_id": "jnj-close",
            "trade_date": DAY,
            "session": "close",
            "direction": "down",
            "universe": "pool",
            "members": [{"ticker": "JNJ", "ret": "-0.0025"}],
        },
        {
            "anomaly_id": "jnj-post",
            "trade_date": DAY,
            "session": "post",
            "direction": "down",
            "universe": "pool",
            "members": json.dumps([{"ticker": "JNJ", "ret": "0.00208"}], ensure_ascii=False),
        },
    ]
    news = [
        _news("early", EARLY, EARLY, "强生公布试验进展"),
        _news("later", LATER, LATER, "盘中又有一条进展", raw=True),
        _news(
            "form",
            EARLY,
            EARLY,
            "内部人表格",
            kind="form4",
            level="高",
        ),
    ]
    ranges = [
        {
            "trade_date": DAY,
            "ticker": "NVDA",
            "status": "ok",
            "bear": "100",
            "neutral": "969.66",
            "bull": "1200",
            "payload": {},
            "observed_at": KNOWN,
        },
        {
            "trade_date": DAY,
            "ticker": "JNJ",
            "status": "ok",
            "bear": "180",
            "neutral": "235.49",
            "bull": "280",
            "payload": {},
            "observed_at": KNOWN,
        },
    ]
    bars = [
        {"ticker": "NVDA", "trade_date": DAY, "close": "217.23"},
        {"ticker": "JNJ", "trade_date": DAY, "close": "253.28"},
    ]
    ledgers = [
        {
            "portfolio_id": "paper-fixed",
            "trade_date": DAY,
            "extractor": "fixed",
            "rule_set": "A",
            "observed_at": KNOWN,
            "state": {"positions": {"NVDA": {"shares": 100}, "JNJ": {"shares": 50}, "MU": {"shares": 0}}},
        },
        {
            "portfolio_id": "paper-other",
            "trade_date": DAY,
            "extractor": "fixed",
            "rule_set": "A",
            "observed_at": KNOWN,
            "state": {"positions": {"BA": {"shares": 3}}},
        },
        {
            "portfolio_id": "paper-fixed",
            "trade_date": DAY,
            "extractor": "legacy",
            "rule_set": "A",
            "observed_at": KNOWN,
            "state": {"positions": {"TSLA": {"shares": 9}}},
        },
    ]
    plans = [
        {
            "portfolio_id": "paper-fixed",
            "signal_date": DAY,
            "trade_date": "2026-10-16",
            "extractor": "fixed",
            "rule_set": "A",
            "published": True,
            "generated_at": KNOWN,
            "payload": {"orders": [{"ticker": "MU", "action": "确认加仓", "value": "22869.85"}]},
        }
    ]
    return Database(anomalies, news, ranges, bars, ledgers, plans)


def _section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def _invoke(directory, data, moment, client, argv=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("INVES_COG_PAGE_DIR", str(directory))
    code = main(argv if argv is not None else [], connection=data, clock=Clock(moment), client=client)
    files = sorted(directory.glob("daily_page_*.txt"))
    text = files[0].read_text(encoding="utf-8") if len(files) == 1 else None
    return code, text, files


def _assert_plain(text):
    for word in FORBIDDEN:
        assert word not in text
    assert re.search(r"-\d+(?:\.\d+)?%", text) is None
    assert re.search(r"\d+\.\d{3,}", text) is None
    assert re.search(r"[a-z]+_[a-z0-9_]+", text) is None


@pytest.mark.phase1_blocking
def test_a_full_day_writes_the_page_and_one_successful_run(tmp_path, monkeypatch):
    data = _full_inputs()
    code, text, files = _invoke(tmp_path, data, MORNING, Quiet(), monkeypatch=monkeypatch)
    assert code == 0
    assert [path.name for path in files] == ["daily_page_2026-10-15.txt"]
    assert "1. JNJ 跌 0.2%" in text
    assert "跌 0.3%" not in text
    assert "JNJ 盘后涨 0.2%，明显弱于同类股票" in text
    assert "NVDA 现价 217.23｜估值待复核" in text
    assert "JNJ 现价 253.28｜偏低" in text
    assert "MU 确认加仓 约 22,869.85 美元" in text
    held = _section(text, "三、你的持仓", "四、值多少")
    assert "NVDA" in held and "JNJ" in held and "MU" not in held
    assert "内部人表格" not in text and "BA" not in text and "TSLA" not in text
    assert len(data.jobs) == 1 and data.jobs[0]["status"] == "ok" and data.jobs[0]["error_summary"] is None


@pytest.mark.phase1_blocking
def test_only_what_was_already_known_is_on_the_page(tmp_path, monkeypatch):
    data = _full_inputs()
    data.news.append(
        _news(
            "seen-late",
            EARLY,
            datetime.fromisoformat("2026-10-16T09:30:00+08:00"),
            "九点半才见到",
            level="高",
        )
    )
    data.ranges.append(
        {
            "trade_date": DAY,
            "ticker": "NVDA",
            "status": "ok",
            "bear": "100",
            "neutral": "217.23",
            "bull": "300",
            "payload": {},
            "observed_at": datetime.fromisoformat("2026-10-16T09:30:00+08:00"),
        }
    )
    data.plans.append(
        {
            "portfolio_id": "paper-fixed",
            "signal_date": "2026-10-16",
            "trade_date": "2026-10-17",
            "extractor": "fixed",
            "rule_set": "A",
            "published": True,
            "generated_at": datetime.fromisoformat("2026-10-16T09:30:00+08:00"),
            "payload": {"orders": [{"ticker": "AMD", "action": "确认加仓", "value": "111.11"}]},
        }
    )
    _code, text, _files = _invoke(tmp_path, data, MORNING, Quiet(), monkeypatch=monkeypatch)
    assert "九点半才见到" not in text
    assert "NVDA 现价 217.23｜估值待复核" in text
    assert "111.11" not in text and "AMD" not in text
    assert "MU 确认加仓 约 22,869.85 美元" in text


@pytest.mark.phase1_blocking
def test_other_moments_do_nothing_and_winter_writes(tmp_path, monkeypatch):
    boom = Boom()
    for moment in (
        datetime.fromisoformat("2026-10-16T09:14:00+08:00"),
        datetime.fromisoformat("2026-10-16T09:16:00+08:00"),
        datetime.fromisoformat("2026-10-16T09:30:00+08:00"),
        datetime.fromisoformat("2026-10-16T12:30:00+08:00"),
    ):
        data = _full_inputs()
        code, text, files = _invoke(tmp_path, data, moment, boom, monkeypatch=monkeypatch)
        assert code == 0 and text is None and files == [] and data.jobs == [] and data.calls == []
    assert boom.calls == 0
    winter = datetime.fromisoformat("2026-01-16T10:15:00+08:00")
    data = Database()
    code, text, files = _invoke(tmp_path, data, winter, boom, monkeypatch=monkeypatch)
    assert code == 0 and boom.calls == 0
    assert [path.name for path in files] == ["daily_page_2026-01-15.txt"]
    assert "今天没有拿到持仓" in text
    assert "今天没有拿到估值" in text
    assert "今天没有拿到计划" in text
    assert len(data.jobs) == 1 and data.jobs[0]["status"] == "ok"


@pytest.mark.phase1_blocking
def test_a_missing_class_still_writes_the_page(tmp_path, monkeypatch):
    no_book = _full_inputs()
    no_book.ledgers = []
    _code, held, _files = _invoke(tmp_path / "held", no_book, MORNING, Quiet(), monkeypatch=monkeypatch)
    assert "今天没有拿到持仓" in held
    assert "MU 确认加仓 约 22,869.85 美元" in held

    no_value = _full_inputs()
    no_value.ranges = []
    no_value.bars = []
    _code, valued, _files = _invoke(tmp_path / "valued", no_value, MORNING, Quiet(), monkeypatch=monkeypatch)
    assert "今天没有拿到估值" in valued
    assert "1. JNJ 跌 0.2%" in valued

    no_plan = _full_inputs()
    no_plan.plans = []
    _code, planned, _files = _invoke(tmp_path / "planned", no_plan, MORNING, Quiet(), monkeypatch=monkeypatch)
    assert "今天没有拿到计划" in planned
    assert "今天没有计划单" not in planned
    positions = _section(planned, "三、你的持仓", "四、值多少")
    assert "NVDA" in positions and "JNJ" in positions


@pytest.mark.phase1_blocking
def test_a_model_failure_still_writes_a_plain_page(tmp_path, monkeypatch):
    data = Database(
        anomalies=[
            {
                "anomaly_id": "jnj-close",
                "trade_date": DAY,
                "session": "close",
                "direction": "down",
                "universe": "pool",
                "members": [{"ticker": "JNJ", "ret": "-0.0025"}],
            }
        ],
        news=[_news("early", EARLY, EARLY, "强生公布试验进展")],
    )
    boom = Boom()
    code, text, files = _invoke(tmp_path, data, MORNING, boom, monkeypatch=monkeypatch)
    assert code == 1 and files and boom.calls == 1
    assert "可能的原因：这次没问到，下次运行再试" in text
    assert "Timeout" not in text and "model" not in text and "down" not in text
    assert set(re.findall(r"[A-Za-z]+", text)) <= {"JNJ", "A"}
    assert data.jobs[0]["status"] == "failed"
    assert data.jobs[0]["error_summary"] == "Timeout: model down"


@pytest.mark.phase1_blocking
def test_rerun_uses_the_given_moment(tmp_path, monkeypatch):
    data = _full_inputs()
    data.anomalies.append(
        {
            "anomaly_id": "jnj-older",
            "trade_date": "2026-10-13",
            "session": "close",
            "direction": "down",
            "universe": "pool",
            "members": [{"ticker": "JNJ", "ret": "-0.0573"}],
        }
    )
    data.news.append(
        _news(
            "known-then",
            datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc),
            "已经公开的进展牵动大盘",
            level="高",
        )
    )
    data.news.append(
        _news(
            "known-later",
            datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc),
            datetime.fromisoformat("2026-10-14T09:30:00+08:00"),
            "补跑之后才看到的大盘消息",
            level="高",
        )
    )
    code, text, files = _invoke(
        tmp_path,
        data,
        MORNING,
        Quiet(),
        argv=["--at", "2026-10-14T09:15:00+08:00"],
        monkeypatch=monkeypatch,
    )
    assert code == 0
    assert [path.name for path in files] == ["daily_page_2026-10-13.txt"]
    assert "JNJ 跌 5.7%" in text
    assert "已经公开的进展" in text
    assert "补跑之后才看到" not in text
    assert "0.2%" not in text
    assert "22,869.85" not in text
    assert "217.23" not in text
    assert str(data.jobs[0]["trade_date"])[:10] == "2026-10-13"


@pytest.mark.phase1_blocking
def test_every_page_uses_plain_words(tmp_path, monkeypatch):
    pages = []
    data = _full_inputs()
    _code, text, _files = _invoke(tmp_path / "full", data, MORNING, Quiet(), monkeypatch=monkeypatch)
    pages.append(text)
    data.news.append(
        _news("seen-late", EARLY, datetime.fromisoformat("2026-10-16T09:30:00+08:00"), "九点半才见到", level="高")
    )
    _code, text, _files = _invoke(tmp_path / "known", data, MORNING, Quiet(), monkeypatch=monkeypatch)
    pages.append(text)
    _code, text, _files = _invoke(
        tmp_path / "winter",
        Database(),
        datetime.fromisoformat("2026-01-16T10:15:00+08:00"),
        Boom(),
        monkeypatch=monkeypatch,
    )
    pages.append(text)
    for name, blank in (("ledgers", "ledgers"), ("ranges", "ranges"), ("plans", "plans")):
        sample = _full_inputs()
        setattr(sample, blank, [])
        if name == "ranges":
            sample.bars = []
        folder = tmp_path / name
        _code, text, _files = _invoke(folder, sample, MORNING, Quiet(), monkeypatch=monkeypatch)
        pages.append(text)
    failed = Database(
        anomalies=[
            {
                "anomaly_id": "jnj-close",
                "trade_date": DAY,
                "session": "close",
                "direction": "down",
                "universe": "pool",
                "members": [{"ticker": "JNJ", "ret": "-0.0025"}],
            }
        ],
        news=[_news("early", EARLY, EARLY, "强生公布试验进展")],
    )
    _code, text, _files = _invoke(tmp_path / "failed", failed, MORNING, Boom(), monkeypatch=monkeypatch)
    pages.append(text)
    older = _full_inputs()
    older.anomalies.append(
        {
            "anomaly_id": "jnj-older",
            "trade_date": "2026-10-13",
            "session": "close",
            "direction": "down",
            "universe": "pool",
            "members": [{"ticker": "JNJ", "ret": "-0.0573"}],
        }
    )
    _code, text, _files = _invoke(
        tmp_path / "rerun",
        older,
        MORNING,
        Quiet(),
        argv=["--at", "2026-10-14T09:15:00+08:00"],
        monkeypatch=monkeypatch,
    )
    pages.append(text)
    for text in pages:
        _assert_plain(text)
