"""Live anomalies: model-picked cause from ingested news (task live_cause)."""

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from inves_cog.perception.live import llm_cause
from inves_cog.perception.live.link import link_causes

pytestmark = pytest.mark.phase1_blocking

DAY = date(2026, 11, 9)
UTC = timezone.utc
RULES = {
    "daily_cap": 120,
    "focus_share": 0.8,
    "max_attempts": 4,
    "min_interval_minutes": 20,
    "per_pass_calls": 6,
    "major_z": 5,
    "top_k": 30,
    "pool_limit": 400,
    "max_age_hours": 72,
    "form4_max_age_hours": 24,
    "summary_chars": 240,
}


def at(month, day, hour, minute):
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def item(info_id, headline, first_seen, published=None, tickers=("NVDA",), kind="news"):
    return {
        "info_id": info_id,
        "kind": kind,
        "source": "benzinga" if kind == "news" else "SEC",
        "source_level": 4 if kind == "news" else 1,
        "published_at": published or first_seen - timedelta(minutes=3),
        "first_seen_at": first_seen,
        "headline": headline,
        "summary": "",
        "tickers": list(tickers),
        "entities": [],
    }


SCANDAL = [
    item(
        "news:benzinga:6302060001",
        "Nvidia's Huang Admits Affair With Suspected Chinese Spy, Board Will Investigate",
        at(11, 8, 21, 27),
    ),
    item(
        "news:benzinga:6302070001",
        "NVIDIA Board Initiates Independent Investigation Into Reported Foreign Intelligence Effort",
        at(11, 8, 22, 0),
        tickers=("NVDA", "SPY"),
    ),
]
NOISE = [
    item("news:benzinga:6302210001", "NVIDIA, Rebellions And SK Telecom Collaborate On Korea AI", at(11, 9, 6, 20)),
    item(
        "news:benzinga:6301780001",
        "TSLA, AMD, MU and More: 5 Stocks Investors Buzzing",
        at(11, 7, 13, 40),
        tickers=("AMD", "NVDA", "TSLA"),
    ),
    item("form4:SEC:0001045810-1", "NVDA Form 4", at(11, 9, 1, 45), published=at(7, 8, 0, 33), kind="form4"),
    item("news:benzinga:6302460001", "Goldman Sachs Reiterates Buy on NVIDIA", at(11, 9, 11, 10)),  # after window
    item("news:benzinga:6302990001", "Dole Posts Downbeat Q3 Results", at(11, 9, 8, 0), tickers=("DOLE",)),
]


def nvda_row(**extra):
    row = {
        "trade_date": DAY,
        "session": "pre",
        "scope": "stock",
        "subject": "NVDA",
        "direction": "down",
        "first_seen_at": at(11, 9, 9, 22),
        "first_ret": -0.061,
        "last_ret": -0.07,
        "peak_ret": -0.07,
        "peak_z": -5.4,
        "last_z": -5.4,
        "members": None,
        "status": "active",
        "cause_event_id": None,
        "cause_kind": None,
        "cause_lag_minutes": None,
        "cause_source": None,
        "cause_reason": None,
        "cause_confidence": None,
        "cause_timing": None,
        "cause_info_ids": None,
        "llm_attempts": 0,
        "llm_last_at": None,
        "llm_last_major": False,
    }
    row.update(extra)
    return row


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeDB:
    """Just enough of perception.live_anomalies / ingest.info_items / news_events."""

    def __init__(self, rows, items, events=(), baskets=None):
        self.rows, self.items, self.events, self.baskets = rows, items, list(events), baskets or {}

    def _find(self, key):
        for row in self.rows:
            if (row["trade_date"], row["session"], row["scope"], row["subject"], row["direction"]) == tuple(key):
                return row
        return None

    def execute(self, sql, args=()):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT * FROM perception.live_anomalies"):
            return _Result([dict(r) for r in self.rows if r["trade_date"] == args[0] and not r["cause_event_id"]])
        if "coalesce(sum(llm_attempts)" in sql:
            return _Result([{"n": sum(r["llm_attempts"] for r in self.rows if r["trade_date"] == args[0])}])
        if sql.startswith("SELECT scope, subject, direction, first_seen_at FROM perception.live_anomalies"):
            return _Result([dict(r) for r in self.rows if r["trade_date"] == args[0] and not r["cause_event_id"]])
        if "FROM perception.news_events" in sql:
            subject, kinds, start, end = args[0], args[1], args[2], args[3]
            hits = [
                e
                for e in self.events
                if e["subject"] == subject and e["kind"] in kinds and start <= e["first_seen_at"] <= end
            ]
            return _Result(hits[:1])
        if "FROM graph.baskets" in sql:
            members = self.baskets.get(args[0])
            return _Result([{"members": members}] if members else [])
        if "min(first_seen_at)" in sql:
            found = [i["first_seen_at"] for i in self.items if i["info_id"] in args[0]]
            return _Result([{"at": min(found) if found else None}])
        if "FROM ingest.info_items" in sql:
            _, start, end, kinds, names, oldest, form4_oldest, limit = args
            out = [
                dict(i)
                for i in self.items
                if start <= i["first_seen_at"] <= end
                and i["kind"] in kinds
                and set(i["tickers"]) & set(names)
                and (i["published_at"] is None or i["published_at"] >= oldest)
                and (i["kind"] != "form4" or i["published_at"] >= form4_oldest)
            ]
            out.sort(key=lambda i: i["first_seen_at"], reverse=True)
            return _Result(out[:limit])
        if sql.startswith("UPDATE perception.live_anomalies"):
            if "cause_source='rule'" in sql:
                event_id, kind, lag, day, scope, subject, direction = args
                for row in self.rows:
                    if (row["trade_date"], row["scope"], row["subject"], row["direction"]) == (
                        day,
                        scope,
                        subject,
                        direction,
                    ):
                        row.update(cause_event_id=event_id, cause_kind=kind, cause_lag_minutes=lag, cause_source="rule")
                return _Result([])
            if "llm_attempts=llm_attempts" in sql:
                inc, now, major, *key = args
                row = self._find(key)
                row.update(llm_attempts=row["llm_attempts"] + inc, llm_last_at=now, llm_last_major=major)
                return _Result([])
            if "cause_source='llm'" in sql:
                reason, confidence, timing, ids, lag, *key = args
                row = self._find(key)
                if row["cause_event_id"] is None:
                    row.update(
                        cause_source="llm",
                        cause_reason=reason,
                        cause_confidence=confidence,
                        cause_timing=timing,
                        cause_info_ids=ids,
                        cause_lag_minutes=lag,
                    )
                return _Result([])
        raise AssertionError(f"unexpected SQL: {sql[:120]}")


class FakeClient:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def call(self, task, payload):
        self.calls.append((task, payload))
        return self.reply(payload) if callable(self.reply) else self.reply


def scandal_reply(payload):
    ids = [n["id"] for n in payload["候选新闻"] if re.search(r"Spy|Investigation", n["标题"])]
    return {
        "cause_info_ids": ids,
        "reason_zh": "黄仁勋承认与疑似中国间谍有婚外情，董事会启动独立调查，引发抛售。",
        "confidence": "high",
        "timing": "news_before_move",
    }


def run(db, client, now=None, core=("NVDA",), held=(), rules=RULES):
    return llm_cause.llm_causes(db, DAY, now or at(11, 9, 9, 25), set(core), set(held), client, rules=rules)


def test_nvda_scandal_cause_cites_scandal_items():
    db = FakeDB([nvda_row()], SCANDAL + NOISE)
    client = FakeClient(scandal_reply)
    stats = run(db, client)
    assert stats["called"] == 1 and stats["written"] == 1
    task, payload = client.calls[0]
    assert task == "live_cause"
    heads = [n["标题"] for n in payload["候选新闻"]]
    assert "NVDA Form 4" not in heads  # stale Form 4 dropped
    assert not any("Goldman" in h for h in heads)  # first seen after this pass (now)
    assert not any("Dole" in h for h in heads)  # other ticker
    row = db.rows[0]
    assert row["cause_source"] == "llm" and row["cause_confidence"] == "high"
    assert sorted(row["cause_info_ids"]) == sorted(i["info_id"] for i in SCANDAL)
    assert row["cause_event_id"] is None and row["llm_attempts"] == 1
    # earliest cited item landed 11-08 21:27Z; anomaly 11-09 09:22Z
    assert row["cause_lag_minutes"] == pytest.approx(11 * 60 + 55)
    # high confidence -> no more calls
    run(db, client, now=at(11, 9, 10, 30))
    assert len(client.calls) == 1


def test_hallucinated_id_rejected():
    db = FakeDB([nvda_row()], SCANDAL + NOISE)
    client = FakeClient({"cause_info_ids": [99], "reason_zh": "编造", "confidence": "high", "timing": "unclear"})
    stats = run(db, client)
    assert stats["rejected"] == 1 and stats["written"] == 0
    assert db.rows[0]["cause_source"] is None and db.rows[0]["llm_attempts"] == 1


def test_validate_rejects_raw_info_id_and_out_of_window():
    ranked = [dict(SCANDAL[0])]
    span = (at(11, 6, 21, 0), at(11, 9, 9, 52))
    assert llm_cause.validate({"cause_info_ids": [SCANDAL[0]["info_id"]]}, ranked, span) is None
    late = [dict(SCANDAL[0], first_seen_at=at(11, 9, 12, 0))]
    assert llm_cause.validate({"cause_info_ids": [1], "reason_zh": "x"}, late, span) is None
    empty = llm_cause.validate({"cause_info_ids": [], "reason_zh": "", "confidence": "low"}, ranked, span)
    assert empty["info_ids"] == []
    low = llm_cause.validate({"cause_info_ids": [1], "reason_zh": "可能", "confidence": "maybe"}, ranked, span)
    assert low["confidence"] == "low" and low["timing"] == "unclear"


def test_low_confidence_kept_as_tentative_and_empty_stays_unknown():
    db = FakeDB([nvda_row()], SCANDAL)
    run(db, FakeClient({"cause_info_ids": [1], "reason_zh": "或与丑闻有关", "confidence": "low", "timing": "unclear"}))
    assert db.rows[0]["cause_confidence"] == "low"
    db = FakeDB([nvda_row()], SCANDAL)
    run(db, FakeClient({"cause_info_ids": [], "reason_zh": "", "confidence": "low", "timing": "unclear"}))
    assert db.rows[0]["cause_source"] is None


def test_daily_cap_and_focus_share():
    spent = nvda_row(subject="ZZZ", session="regular", llm_attempts=120, llm_last_at=at(11, 9, 9, 0))
    db = FakeDB([nvda_row(), spent], SCANDAL)
    client = FakeClient(scandal_reply)
    assert run(db, client)["skipped_cap"] == 1 and client.calls == []
    # 100 used (>= 80% of 120): a minor non-core name waits, a major name still runs
    spent["llm_attempts"] = 100
    minor = nvda_row(subject="ABC", peak_z=-3.1, last_z=-3.1)
    items = SCANDAL + [item("news:x:1", "ABC slides", at(11, 9, 9, 0), tickers=("ABC",))]
    db = FakeDB([nvda_row(peak_z=-3.0, last_z=-3.0, subject="NVDA"), minor, spent], items)
    client = FakeClient(scandal_reply)
    stats = run(db, client, core=("NVDA",))
    assert [c[1]["异常"]["对象"] for c in client.calls] == ["NVDA"] and stats["skipped_cap"] == 1


def test_attempt_limits_interval_and_triggers():
    now = at(11, 9, 10, 0)
    rules = RULES
    row = nvda_row(llm_attempts=1, llm_last_at=now - timedelta(minutes=10), llm_last_major=False)
    assert not llm_cause.due(row, now, rules, major=True, fresh_news=True)  # < 20 min
    row["llm_last_at"] = now - timedelta(minutes=30)
    assert not llm_cause.due(row, now, rules, major=False, fresh_news=False)
    assert llm_cause.due(row, now, rules, major=True, fresh_news=False)  # upgraded to 重大
    assert llm_cause.due(row, now, rules, major=False, fresh_news=True)  # new relevant news
    row["llm_last_major"] = True
    assert not llm_cause.due(row, now, rules, major=True, fresh_news=False)
    row["llm_attempts"] = 4
    assert not llm_cause.due(row, now, rules, major=True, fresh_news=True)
    assert llm_cause.due(nvda_row(), now, rules, major=False, fresh_news=False)  # first appearance
    # end to end: a try 10 minutes ago blocks a second call
    db = FakeDB([nvda_row(llm_attempts=1, llm_last_at=now - timedelta(minutes=10))], SCANDAL)
    client = FakeClient(scandal_reply)
    run(db, client, now=now)
    assert client.calls == []


def test_rule_strong_event_skips_model():
    db = FakeDB(
        [nvda_row()],
        SCANDAL,
        events=[
            {
                "event_id": "NVDA:guidance:2026-11-09",
                "subject": "NVDA",
                "kind": "guidance",
                "first_seen_at": at(11, 9, 9, 0),
            }
        ],
    )
    assert link_causes(db, DAY, {"NVDA"}) == 1
    client = FakeClient(scandal_reply)
    run(db, client)
    assert client.calls == [] and db.rows[0]["cause_source"] == "rule"


def test_regular_row_reuses_premarket_high_cause_without_call():
    pre = nvda_row(
        cause_source="llm",
        cause_reason="丑闻",
        cause_confidence="high",
        cause_timing="news_before_move",
        cause_info_ids=[SCANDAL[0]["info_id"]],
        llm_attempts=1,
        llm_last_at=at(11, 9, 9, 25),
    )
    regular = nvda_row(session="regular", first_seen_at=at(11, 9, 14, 32), peak_z=-8.7)
    db = FakeDB([pre, regular], SCANDAL)
    client = FakeClient(scandal_reply)
    stats = run(db, client, now=at(11, 9, 14, 35))
    assert client.calls == [] and stats["copied"] == 1
    assert db.rows[1]["cause_reason"] == "丑闻" and db.rows[1]["cause_lag_minutes"] == pytest.approx(17 * 60 + 5)


LATE = item(
    "news:benzinga:6302370001",
    "NVDA Stock Falls Over 5% Pre-Market: Board Probe Into Jensen Huang",
    at(11, 9, 11, 0),  # 06:00 ET, after the 04:22 ET move
)


def late_reply(payload):
    ids = [n["id"] for n in payload["候选新闻"] if "Board Probe" in n["标题"]]
    return {"cause_info_ids": ids, "reason_zh": "董事会调查CEO。", "confidence": "high", "timing": "move_before_news"}


def test_news_after_move_is_found_with_negative_lag():
    db = FakeDB([nvda_row()], [LATE])
    client = FakeClient(late_reply)
    run(db, client, now=at(11, 9, 11, 30))  # pass at 06:30 ET
    heads = [n["标题"] for n in client.calls[0][1]["候选新闻"]]
    assert LATE["headline"] in heads
    row = db.rows[0]
    assert row["cause_info_ids"] == [LATE["info_id"]] and row["cause_timing"] == "move_before_news"
    assert row["cause_lag_minutes"] == pytest.approx(-98)  # 04:22 - 06:00 ET


def test_window_end_is_now_bounded_by_day_close():
    start, end = llm_cause.window(DAY, at(11, 9, 11, 30))
    assert end == at(11, 9, 11, 30)
    _, end = llm_cause.window(DAY, at(11, 10, 3, 0))  # after 20:00 ET (01:00Z)
    assert end == at(11, 10, 1, 0)


def test_rerun_triggers_on_fresh_item_after_interval():
    tried = dict(
        llm_attempts=1, llm_last_at=at(11, 9, 10, 30), llm_last_major=True
    )  # tried 05:30 ET, nothing found yet
    db = FakeDB([nvda_row(**tried)], [SCANDAL[0]])
    client = FakeClient(late_reply)
    run(db, client, now=at(11, 9, 11, 30))
    assert client.calls == []  # only old news, no upgrade -> no re-run
    db = FakeDB([nvda_row(**tried)], [SCANDAL[0], LATE])
    run(db, client, now=at(11, 9, 10, 45))
    assert client.calls == []  # fresh item, but inside the 20-minute interval
    run(db, client, now=at(11, 9, 11, 30))
    assert len(client.calls) == 1 and db.rows[0]["llm_attempts"] == 2
    assert db.rows[0]["cause_info_ids"] == [LATE["info_id"]]


def test_model_failure_counts_attempt_and_keeps_unknown():
    def boom(payload):
        raise RuntimeError("down")

    db = FakeDB([nvda_row()], SCANDAL)
    run(db, FakeClient(boom))
    assert db.rows[0]["llm_attempts"] == 1 and db.rows[0]["cause_source"] is None


def test_live_cause_task_registered_on_flash_model():
    from pathlib import Path

    from inves_cog.llm.registry import Registry

    spec = Registry(Path(__file__).resolve().parents[2] / "config/llm_tasks.yaml").resolve("live_cause")
    assert spec.model == "deepseek-v4.1-flash"
    assert llm_cause.params()["daily_cap"] == 120


def test_usage_recorded_through_shared_client():
    from pathlib import Path

    from inves_cog.clock import FrozenClock
    from inves_cog.llm.client import Client

    recorded = []
    client = Client(
        registry=Path(__file__).resolve().parents[2] / "config/llm_tasks.yaml",
        transport=lambda spec, payload: scandal_reply(payload),
        clock=FrozenClock(at(11, 9, 9, 25)),
        recorder=recorded.append,
    )
    db = FakeDB([nvda_row()], SCANDAL + NOISE)
    run(db, client)
    assert recorded and recorded[0]["task"] == "live_cause" and recorded[0]["model"] == "deepseek-v4.1-flash"
    assert set(i["info_id"] for i in SCANDAL) <= set(recorded[0]["info_ids"])


# ---- page ----


def _page_row(**extra):
    base = {
        "scope": "stock",
        "subject": "NVDA",
        "session": "pre",
        "direction": "down",
        "first_ret": -0.06,
        "last_ret": -0.07,
        "peak_ret": -0.07,
        "peak_z": -5.4,
        "status": "active",
        "trade_date": DAY,
        "first_seen_at": at(11, 9, 9, 22),
        "cause_event_id": None,
    }
    base.update(extra)
    return base


def test_title_follows_session():
    from inves_cog.web.investor_html import _live_module

    def title(rows):
        return re.search(r'id="live"><h2>([^<]+)', _live_module({"news_modules": {"live": rows}})).group(1)

    assert title([_page_row(session="pre")]) == "盘前异常"
    assert title([_page_row(session="regular")]) == "盘中异常"
    assert title([_page_row(session="post")]) == "盘后异常"
    assert title([_page_row(session="pre"), _page_row(session="regular", subject="AMD")]) == "今日异常"


def test_top_five_and_collapse_order():
    from inves_cog.web.investor_html import _live_module

    rows = [
        _page_row(subject="AAA", peak_z=-3.2, peak_ret=-0.09),
        _page_row(subject="BBB", peak_z=-3.1, peak_ret=-0.04),
        _page_row(subject="CCC", peak_z=-3.0, peak_ret=-0.05, is_core=True),
        _page_row(subject="DDD", peak_z=-6.0, peak_ret=-0.03),
        _page_row(subject="EEE", peak_z=-3.3, peak_ret=-0.06),
        _page_row(subject="FFF", peak_z=None, last_z=None, peak_ret=-0.10, status="faded"),
        _page_row(subject="GGG", peak_z=-3.1, peak_ret=-0.02),
    ]
    html = _live_module({"news_modules": {"live": rows}, "held_tickers": ["GGG"]})
    shown, _, rest = html.partition('<details class="live-more">')
    assert "另有 2 条" in rest
    names = {r["subject"] for r in rows}
    order = list(dict.fromkeys(m for m in re.findall(r"\b([A-G]{3})\b", shown) if m in names))
    # 重大 DDD; then focus (core CCC, held GGG); then |peak| desc AAA, EEE
    assert order[:5] == ["DDD", "CCC", "GGG", "AAA", "EEE"]
    tail = list(dict.fromkeys(m for m in re.findall(r"\b([A-G]{3})\b", rest) if m in names))
    assert tail == ["BBB", "FFF"]


def test_llm_cause_cell_and_tentative_chip():
    from inves_cog.web.investor_html import _live_module

    reason = "黄仁勋承认与疑似中国间谍有婚外情，董事会启动独立调查。"
    llm = _page_row(
        cause_source="llm",
        cause_state="llm",
        cause_reason=reason,
        cause_confidence="high",
        cause_info_ids=["news:benzinga:6302060001"],
        cause_headline="Nvidia's Huang Admits Affair With Suspected Chinese Spy",
        cause_first_seen=at(11, 8, 21, 27),
    )
    html = _live_module({"news_modules": {"live": [llm]}})
    assert reason in html and "模型判断" in html and "新闻 11-08 16:27美东" in html
    assert 'title="Nvidia&#x27;s Huang Admits' in html or "title=\"Nvidia's Huang Admits" in html
    assert "原因未明" not in html and "news:benzinga" not in html and "None" not in html
    for level in ("medium", "low"):
        tentative = dict(llm, cause_state="tentative", cause_confidence=level)
        html = _live_module({"news_modules": {"live": [tentative]}})
        assert "待证实" in html and "模型判断</span>" not in html
    unknown = _live_module({"news_modules": {"live": [_page_row()]}})
    assert "原因未明" in unknown


def test_brief_cause_state_and_label():
    from inves_cog.web.brief import _cause_label, _hl_grouped, cause_state

    rule = {"cause_event_id": "NVDA:guidance:2026-11-09", "cause_subject": "NVDA", "cause_kind": "guidance"}
    assert cause_state(rule) == "rule"
    llm = {
        "scope": "stock",
        "subject": "NVDA",
        "cause_source": "llm",
        "cause_reason": "丑闻",
        "cause_confidence": "high",
        "cause_info_ids": ["a"],
        "status": "active",
        "peak_z": -5,
    }
    assert cause_state(llm) == "llm" and _cause_label(llm) == "丑闻"
    assert cause_state({**llm, "cause_confidence": "medium"}) == "tentative"
    assert cause_state({**llm, "cause_confidence": "low"}) == "tentative"
    assert cause_state({**llm, "cause_info_ids": []}) is None
    groups = _hl_grouped([{**llm, "cause_label": "丑闻"}], [])
    assert groups[0]["cause"] == "丑闻" and groups[0]["cause_source"] == "llm"
    # medium is not a confirmed cause: no grouping key, no 模型判断 chip
    medium = {**llm, "cause_confidence": "medium", "cause_label": "丑闻"}
    groups = _hl_grouped([medium, {**medium, "subject": "AMD"}], [])
    assert len(groups) == 2 and all(g["cause_source"] is None for g in groups)
    assert groups[0]["cause"] == "待证实：丑闻"


def test_market_state_cause_uses_rule_and_high_only(monkeypatch):
    from inves_cog.web import brief

    monkeypatch.setattr(brief, "_series_fetch", lambda *a, **k: {})
    monkeypatch.setattr(brief, "_quote", lambda c, t, d, shared=None: {"ret": -0.04, "sig": 0.01, "mult": 4.0})
    base = {"scope": "market", "subject": "QQQ", "cause_source": "llm", "cause_info_ids": ["a"]}
    rows = [
        {**base, "cause_reason": "中等把握", "cause_confidence": "medium", "cause_label": "中等把握"},
        {**base, "cause_reason": "高把握", "cause_confidence": "high", "cause_label": "高把握"},
    ]
    state = brief._market_state(None, DAY, {}, rows)
    assert "高把握" in state["detail"] and "中等把握" not in state["detail"]


@pytest.mark.phase1_blocking
def test_llm_cause_columns_and_page_join_on_disposable_database():
    """Migration adds the columns; the writer path and the page join agree."""

    import psycopg
    from psycopg.rows import dict_row

    from inves_cog.web.brief import _live_anomalies
    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    with psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    ) as conn:
        conn.execute("DELETE FROM perception.live_anomalies WHERE trade_date=%s", (DAY,))
        conn.execute(
            "DELETE FROM ingest.info_items WHERE info_id = ANY(%s)", ([i["info_id"] for i in SCANDAL + NOISE],)
        )
        for i in SCANDAL + NOISE:
            conn.execute(
                """INSERT INTO ingest.info_items (info_id, kind, published_at, first_seen_at, source,
                       source_level, headline, summary, tickers, entities, extraction_status, flags,
                       payload, extraction_source)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ok','{}','{}'::jsonb,'{}'::jsonb)""",
                (
                    i["info_id"],
                    i["kind"],
                    i["published_at"],
                    i["first_seen_at"],
                    i["source"],
                    i["source_level"],
                    i["headline"],
                    i["summary"],
                    i["tickers"],
                    i["entities"],
                ),
            )
        conn.execute(
            """INSERT INTO perception.live_anomalies (trade_date, session, scope, subject, direction,
                   first_seen_at, last_seen_at, first_ret, last_ret, peak_ret, last_z, peak_z, members)
               VALUES (%s,'pre','stock','NVDA','down',%s,%s,-0.061,-0.07,-0.07,-5.4,-5.4,%s)""",
            (DAY, at(11, 9, 9, 22), at(11, 9, 9, 25), None),
        )
        client = FakeClient(scandal_reply)
        stats = llm_cause.llm_causes(conn, DAY, at(11, 9, 9, 25), {"NVDA"}, set(), client, rules=RULES)
        assert stats["written"] == 1
        heads = [n["标题"] for n in client.calls[0][1]["候选新闻"]]
        assert "NVDA Form 4" not in heads and not any("Goldman" in h for h in heads)
        rows = _live_anomalies(conn, DAY, True)
        row = [r for r in rows if r["subject"] == "NVDA"][0]
        assert row["cause_state"] == "llm" and row["cause_first_seen"] == SCANDAL[0]["first_seen_at"]
        assert row["cause_headline"].startswith("Nvidia's Huang Admits")
        assert llm_cause.calls_used(conn, DAY) == 1
        conn.execute("DELETE FROM perception.live_anomalies WHERE trade_date=%s", (DAY,))
        conn.execute(
            "DELETE FROM ingest.info_items WHERE info_id = ANY(%s)", ([i["info_id"] for i in SCANDAL + NOISE],)
        )
