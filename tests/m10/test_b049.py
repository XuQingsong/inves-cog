"""B-049 review loop. R1–R9, with a counting client instead of a live model."""

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import next_trading_day, trading_day
from inves_cog.llm.registry import Registry
from inves_cog.perception.anomaly.service import run_recorded
from inves_cog.perception.review.calendar import add_sessions, cutoff
from inves_cog.perception.review.cases import run_labels
from inves_cog.perception.review.oneliner import ground
from inves_cog.perception.review.patterns import pattern_status, rebuild_patterns, record_example
from inves_cog.perception.review.reports import MONTHLY_BLOCKS, WEEKLY_BLOCKS, store_monthly, store_weekly
from inves_cog.perception.review.samples import miss_report, record_judgment, sample_monthly, sample_weekly
from inves_cog.perception.review.schedule import PARAMS, poll
from inves_cog.perception.review.snapshots import pool_tickers, write_snapshots
from inves_cog.web.api import create_app
from tests.m8.test_attribution import _disposable_database
from tests.m10.test_b048 import FORBIDDEN_FIELDS

pytestmark = pytest.mark.phase1_blocking
ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")
UTC = timezone.utc
LABEL = "估值参考 v1，不参与仓位"


class Counting:
    def __init__(self, text="", error=False):
        self.calls = []
        self.text = text
        self.error = error

    def call(self, task, payload):
        self.calls.append((task, payload))
        if self.error:
            raise RuntimeError("model down")
        return {"text": self.text}


@pytest.fixture(scope="module")
def host():
    return _disposable_database()


@pytest.fixture
def admin(host):
    connection = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    _roles(connection)
    _clean(connection)
    yield connection
    _clean(connection)
    connection.close()


def test_case_cadence(admin):
    days = _span(date(2032, 3, 1), 25)
    origin, plus1, plus5 = days[0], days[1], days[5]
    seen = datetime.combine(origin, time(2, 0), tzinfo=UTC)
    for name, ticker, universe in (
        ("b049-a1", "AAA", "pool"),
        ("b049-a2", "BBB", "pool"),
        ("b049-a3", "CCC", "pool"),
        ("b049-wide", "WIDE", "wide"),
    ):
        _anomaly(admin, name, ticker, origin, seen, universe)
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, unknowns)
        VALUES ('b049-e1', 'b049-a1', '假设中', %s, '[]')
        """,
        (Jsonb([{"at": seen.isoformat(), "new": "假设中"}]),),
    )
    admin.execute(
        """
        INSERT INTO perception.second_hits (event_id, info_id, outcome, source_root, published_at)
        VALUES ('b049-e1', 'b049-late', '确认', 'b049', %s)
        """,
        (cutoff(plus1),),
    )
    for ticker in ("AAA", "BBB"):
        _bar(admin, ticker, plus5, 10)
    for day in days:
        run_labels(admin, day, FrozenClock(datetime.combine(day, time(4, 0), tzinfo=UTC)))
    cases = {
        row["anomaly_id"]: row
        for row in admin.execute(
            "SELECT anomaly_id, status, reason FROM perception.cases WHERE anomaly_id LIKE 'b049-%'"
        ).fetchall()
    }
    assert set(cases) == {"b049-a1", "b049-a2", "b049-a3"}
    assert cases["b049-a1"]["status"] == "已完成" and cases["b049-a2"]["status"] == "已完成"
    assert cases["b049-a3"]["status"] == "未完成" and "CCC" in cases["b049-a3"]["reason"]
    labels = admin.execute(
        """
        SELECT case_id, horizon, drafted, reason, labels
        FROM perception.case_labels WHERE case_id LIKE 'b049-%'
        """
    ).fetchall()
    by_case = {}
    for row in labels:
        by_case.setdefault(row["case_id"], {})[row["horizon"]] = row
    for case_id in cases:
        assert set(by_case[case_id]) == {"T+1", "T+5", "T+20"}
        assert by_case[case_id]["T+20"]["drafted"] is True
        assert by_case[case_id]["T+1"]["drafted"] is False
    first = by_case["b049-a1"]["T+1"]["labels"]
    later = by_case["b049-a1"]["T+5"]["labels"]
    assert first["市场连接"] == "未检验" and "b049-late" not in first["可见二次命中"]
    assert later["市场连接"] == "确认" and "b049-late" in later["可见二次命中"]
    assert by_case["b049-a3"]["T+5"]["reason"] and "CCC" in by_case["b049-a3"]["T+5"]["reason"]


def test_precursor_snapshot_daily(admin):
    assert len(pool_tickers()) == 59
    day = _session(date(2032, 4, 5))
    days = [day, next_trading_day(day), next_trading_day(next_trading_day(day))]
    admin.execute(
        """
        INSERT INTO graph.baskets (basket_id, level, name, benchmark, members, factor_basis)
        VALUES ('b049-basket', 'L3', 'b049', 'QQQ', '[]', '{}')
        """
    )
    admin.execute(
        """
        INSERT INTO marketstate.daily (
            trade_date, ticker, session, ret, beta_share_5d, factor_set, health_codes
        ) VALUES (%s, 'NVDA', 'close', 0.01, 0.37, 'p-2026.10', ARRAY['ok'])
        """,
        (day,),
    )
    admin.execute(
        """
        INSERT INTO ingest.short_interest (
            observation_id, ticker, publish_date, si_pct_shares_outstanding, days_to_cover, source, raw
        ) VALUES ('b049-si', 'NVDA', %s, 0.02, 1.5, 'b049', '{}')
        """,
        (day,),
    )
    baskets = admin.execute("SELECT count(*) AS n FROM graph.baskets").fetchone()["n"]
    for item in days:
        assert write_snapshots(admin, item) == 59 + baskets
        rows = admin.execute(
            "SELECT subject_kind, subject_id, features FROM perception.precursor_snapshots WHERE trade_date = %s",
            (item,),
        ).fetchall()
        assert {row["subject_id"] for row in rows if row["subject_kind"] == "ticker"} == set(pool_tickers())
        assert "b049-basket" in {row["subject_id"] for row in rows if row["subject_kind"] == "basket"}
    stored = admin.execute(
        """
        SELECT features FROM perception.precursor_snapshots
        WHERE trade_date = %s AND subject_id = 'NVDA'
        """,
        (day,),
    ).fetchone()["features"]
    assert stored["价格结构"]["beta_share_5d"] == {"value": 0.37}
    assert stored["空头"]["空头占流通股比例"] == {"value": 0.02}
    assert stored["期权"]["隐含波动率分位"] == {"reason": "数据暂缺"}
    weekend = day
    while trading_day(weekend):
        weekend = weekend + timedelta(days=1)
    assert write_snapshots(admin, weekend) == 0
    assert (
        admin.execute(
            "SELECT count(*) AS n FROM perception.precursor_snapshots WHERE trade_date = %s",
            (weekend,),
        ).fetchone()["n"]
        == 0
    )


def test_miss_sample_frame(admin, host):
    period = date(2032, 6, 17)
    seen = datetime.combine(period, time(2, 0), tzinfo=UTC)
    for index in range(25):
        _info(admin, f"b049-info-{index:02d}", seen, attention=False, found=index < 12)
    _info(admin, "b049-info-attention", seen, attention=True, found=True)
    first = {row["item_ref"]: row["discovered"] for row in sample_weekly(admin, period)}
    assert len(first) == 20 and "b049-info-attention" not in first
    admin.execute(
        """
        UPDATE ingest.info_items
        SET payload = jsonb_set(
            payload, '{system_found}', to_jsonb(NOT COALESCE((payload->>'system_found')::boolean, false))
        )
        WHERE info_id LIKE 'b049-info-%'
        """
    )
    second = {row["item_ref"]: row["discovered"] for row in sample_weekly(admin, period)}
    assert set(first) == set(second)
    assert any(first[key] != second[key] for key in first)
    month_end = date(2032, 7, 31)
    move_day = date(2032, 7, 15)
    for index in range(15):
        _daily(admin, f"B049M{index:02d}", move_day, 0.01)
    for index in range(3):
        _daily(admin, f"B049H{index:02d}", move_day, 0.2)
    for index in range(12):
        _wide(admin, f"W049{index:02d}", month_end)
    _wide(admin, "NVDA", month_end)
    before = sample_monthly(admin, month_end)
    move_refs = {row["item_ref"] for row in before["moves"]}
    company_refs = {row["item_ref"] for row in before["companies"]}
    assert len(move_refs) == 10 and len(company_refs) == 10
    assert not any(ref.startswith("B049H") for ref in move_refs)
    assert "NVDA" not in company_refs
    for ref in sorted(move_refs):
        ticker = ref.split(":", 1)[0]
        _anomaly(admin, "b049-found-" + ticker, ticker, move_day, seen)
    for index in range(3):
        _anomaly(admin, f"b049-co-{index}", f"W049{index:02d}", move_day, seen)
    after = sample_monthly(admin, month_end)
    assert {row["item_ref"] for row in after["moves"]} == move_refs
    assert {row["item_ref"] for row in after["companies"]} == company_refs
    assert any(row["discovered"] for row in after["moves"])
    clock = FrozenClock(seen)
    rows = list(second)
    discovered = [key for key in rows if second[key]]
    hidden = [key for key in rows if not second[key]]
    rest = [key for key in rows if key not in {discovered[0], hidden[0]}]
    record_judgment(admin, _sample_id("weekly_info", period, discovered[0]), "应发现", clock)
    record_judgment(admin, _sample_id("weekly_info", period, hidden[0]), "应发现", clock)
    record_judgment(admin, _sample_id("weekly_info", period, rest[0]), "未知", clock)
    record_judgment(admin, _sample_id("weekly_info", period, rest[1]), "数据不覆盖", clock)
    stored = admin.execute(
        """
        SELECT discovered, judgment FROM perception.miss_samples
        WHERE frame = 'weekly_info' AND period_end = %s AND judgment IS NOT NULL
        """,
        (period,),
    ).fetchall()
    report = miss_report(stored)
    assert report["detection_denominator"] == 2
    assert report["detection_rate"] == 0.5
    assert report["unknown_count"] == 1 and report["uncovered_count"] == 1
    _anomaly(admin, "b049-miss", "MSFT", period, seen)
    _anomaly(admin, "b049-plain", "AMD", period, seen)
    record_judgment(admin, _sample_id("weekly_info", period, rest[2]), "应发现", clock, anomaly_id="b049-miss")
    client = TestClient(create_app(dsn=f"postgresql://b049_web@{host}/inves_cog", clock=clock))
    market = client.get("/api/pages/market", params={"date": period.isoformat()}).json()
    cards = {row["anomaly_id"]: row["disposition"] for row in market["anomalies"]}
    assert cards["b049-miss"] == "⑤" and cards["b049-plain"] == "①"


def test_pattern_thresholds(admin):
    day = date(2032, 2, 2)
    clock = FrozenClock(datetime.combine(day, time(4, 0), tzinfo=UTC))
    assert pattern_status(9, False) is None
    assert pattern_status(10, False) == "观察"
    assert pattern_status(30, True) == "有效"
    assert pattern_status(30, False) == "观察"
    for index in range(9):
        record_example(
            admin,
            clock,
            case_id=f"b049-pa-{index}",
            trade_date=day,
            trigger_type="b049-A",
            mechanism="机制",
            capital_behavior="流入",
            outcome="上涨",
            counterexample=index == 0,
        )
    for index in range(30):
        record_example(
            admin,
            clock,
            case_id=f"b049-pb-{index}",
            trade_date=day,
            trigger_type="b049-B",
            mechanism="机制",
            capital_behavior="流入",
            outcome="上涨",
            retained=index < 5,
            holds=True,
            counterexample=index == 9,
        )
        record_example(
            admin,
            clock,
            case_id=f"b049-pc-{index}",
            trade_date=day,
            trigger_type="b049-C",
            mechanism="机制",
            capital_behavior="流出",
            outcome="下跌",
            retained=index < 5,
            holds=False,
            counterexample=index == 9,
        )
    hidden = {row["trigger_type"] for row in _patterns(admin)}
    assert "b049-A" not in hidden and {"b049-B", "b049-C"} <= hidden
    record_example(
        admin,
        clock,
        case_id="b049-pa-9",
        trade_date=day,
        trigger_type="b049-A",
        mechanism="机制",
        capital_behavior="流入",
        outcome="上涨",
    )
    rebuild_patterns(admin, clock)
    found = {row["trigger_type"]: row for row in _patterns(admin)}
    assert found["b049-A"]["status"] == "观察" and found["b049-A"]["example_count"] == 10
    assert found["b049-B"]["status"] == "有效" and found["b049-B"]["example_count"] == 30
    assert found["b049-C"]["status"] == "观察" and found["b049-C"]["retained_holds"] is False
    for key in ("b049-A", "b049-B", "b049-C"):
        assert found[key]["counterexamples"]


def test_reports_contents(admin):
    origin = _session(date(2032, 9, 1))
    week_ending = origin
    month_end = date(origin.year, origin.month, 1) + timedelta(days=32)
    month_end = date(month_end.year, month_end.month, 1) - timedelta(days=1)
    seen = datetime.combine(origin, time(2, 0), tzinfo=UTC)
    clock = FrozenClock(datetime.combine(origin, time(4, 0), tzinfo=UTC))
    _bar(admin, "B049S", origin, 100)
    for count, close in ((5, 110), (21, 121), (63, 163)):
        _bar(admin, "B049S", add_sessions(origin, count), close)
    admin.execute(
        """
        INSERT INTO perception_shadow.signals (
            signal_key, date, signal, ticker, condition_detail, shadow_action, rule_a_action, params_version
        ) VALUES ('b049-x1', %s, 'X1', 'B049S', '{}', '减1/3', '{}', 'p-2026.10')
        """,
        (origin,),
    )
    admin.execute(
        """
        INSERT INTO factor_shadow.registry (
            factor_id, version, definition, inputs, pit_note, target, rationale, source,
            expected_direction, status, created_at
        ) VALUES ('b049-f', 'v1', 'def', '{}', 'pit', '质量账', 'why', 'b049', 'up', '影子计算', %s)
        """,
        (seen,),
    )
    admin.execute(
        """
        INSERT INTO factor_shadow.daily (
            date, ticker, factor_id, version, value, would_pass, rule_a_entry_pass, gap_detail,
            params_version, generated_at
        ) VALUES (%s, 'B049S', 'b049-f', 'v1', '{"value": 1}', true, false, '{}', 'p-2026.10', %s)
        """,
        (origin, seen),
    )
    _range(admin, "B049V", origin - timedelta(days=10), 12, seen, None)
    _range(admin, "B049V", origin, 20, seen, "一致预期")
    _panel(admin, "B049S", origin, seen)
    _plan(admin, origin, seen)
    _anomaly(admin, "b049-cal-1", "B049S", origin, seen)
    _anomaly(admin, "b049-cal-2", "B049V", origin, seen)
    _anomaly(admin, "b049-unknown", "B049U", origin, seen)
    admin.execute(
        """
        INSERT INTO perception.linkage_events (event_id, anomaly_id, lifecycle, history, deadline_outcome, unknowns)
        VALUES ('b049-cal-e', 'b049-cal-1', '市场确认', %s, '支持', '[]')
        """,
        (Jsonb([{"at": seen.isoformat(), "new": "市场确认"}]),),
    )
    admin.execute(
        """
        INSERT INTO perception.second_hits (event_id, info_id, outcome, source_root, published_at)
        VALUES ('b049-cal-e', 'b049-hit', '确认', 'b049', %s)
        """,
        (seen,),
    )
    for name, confidence in (("b049-cal-1", "高"), ("b049-cal-2", "高")):
        admin.execute(
            """
            INSERT INTO perception.candidates (
                anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids, scored, confidence
            ) VALUES (%s, 'c', '供给', '[]', '[]', ARRAY[]::text[], ARRAY['b049-hit'], false, %s)
            """,
            (name, confidence),
        )
    admin.execute(
        """
        INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, reason, updated_at)
        VALUES ('b049-pending', 'b049-pending', %s, '未完成', NULL, %s)
        """,
        (origin, seen),
    )
    admin.execute(
        """
        INSERT INTO perception.case_labels (
            case_id, horizon, as_of, drafted, labels, reason, visible_until, written_at
        ) VALUES ('b049-pending', 'T+20', %s, true, '{}', NULL, %s, %s)
        """,
        (origin, cutoff(origin), seen),
    )
    for index, ring in enumerate(("信源没覆盖", "信源没覆盖", "异常没触发")):
        admin.execute(
            """
            INSERT INTO perception.miss_samples (
                sample_id, frame, period_end, item_ref, discovered, judgment, gap_ring, judged_at
            ) VALUES (%s, 'monthly_move', %s, %s, false, '应发现', %s, %s)
            """,
            (f"b049-gap-{index}", origin, f"b049-item-{index}", ring, seen),
        )
    weekly = store_weekly(admin, week_ending, clock)
    monthly = store_monthly(admin, month_end, clock)
    for name in WEEKLY_BLOCKS:
        assert name in weekly
    for name in MONTHLY_BLOCKS:
        assert name in monthly
    signal = next(row for row in weekly["后续收益"] if row["kind"] == "signal")
    factor = next(row for row in monthly["规则A与因子影子分歧"] if row["factor_id"] == "b049-f")
    assert signal["shadow_action"] == "减1/3"
    assert factor["would_pass"] is True and factor["rule_a_entry_pass"] is False
    for count, close in ((5, 110), (21, 121), (63, 163)):
        point = next(item for item in signal["horizons"] if item["horizon"] == count)
        later = add_sessions(origin, count)
        stored_start = admin.execute(
            "SELECT close FROM ingest.bars_daily WHERE ticker = 'B049S' AND trade_date = %s",
            (origin,),
        ).fetchone()["close"]
        stored_end = admin.execute(
            "SELECT close FROM ingest.bars_daily WHERE ticker = 'B049S' AND trade_date = %s",
            (later,),
        ).fetchone()["close"]
        assert point["start_close"] == stored_start and point["end_close"] == stored_end == close
        assert point["ret"] == point["end_close"] / point["start_close"] - 1
    change = next(row for row in weekly["估值区间变化最大的10只"] if row["ticker"] == "B049V")
    assert change["earlier"] == 12 and change["later"] == 20 and change["abs_change"] == 8
    assert change["reason"] == "一致预期"
    assert any(row["case_id"] == "b049-pending" for row in weekly["待确认打标"])
    assert any(row["ticker"] == "B049S" for row in weekly["冷静期挡掉的买入此后表现"])
    assert any(row["ticker"] == "B049S" for row in weekly["估值仓位对照标黄持仓此后表现"])
    bucket = next(row for row in monthly["归因校准"]["buckets"] if row["confidence"] == "高")
    assert bucket["candidates"] == 2 and bucket["confirmed_hits"] == 1
    assert {"outcome": "支持", "count": 1} in monthly["归因校准"]["deadline_outcomes"]
    assert monthly["信源缺口排序"][0] == {"ring": "信源没覆盖", "count": 2}
    trend = next(row for row in monthly["原因未明占比趋势"] if row["trade_date"] == origin.isoformat())
    assert trend["total"] == 3 and trend["unknown"] == 2


def test_oneliner_grounded():
    page = {
        "date": "2032-05-04",
        "counts": {"anomaly_count": 2},
        "anomalies": [{"anomaly_id": "b049-z"}],
        "other_day": "2031-01-01",
    }
    cited = Counting("围绕 b049-z")
    assert ground(cited, page) == "围绕 b049-z"
    assert len(cited.calls) == 1 and cited.calls[0][0] == "summary_oneliner"
    encoded = json.dumps(cited.calls[0][1], ensure_ascii=False)
    assert "b049-z" in encoded and "2031-01-01" not in encoded and encoded.count("2032-05-04") == 1
    assert ground(Counting("没有编号"), page) == "今日异常 2 个，详见下方"
    assert ground(Counting(error=True), page) == "今日异常 2 个，详见下方"
    empty = {"date": "2032-05-04", "counts": {"anomaly_count": 0}, "anomalies": []}
    none = Counting("今天无异常")
    assert ground(none, empty) == "今天无异常" and len(none.calls) == 1
    model = Registry(ROOT / "config/llm_tasks.yaml").resolve("summary_oneliner").model
    assert model == "deepseek-v4.1-flash"


def test_review_page_blocks(admin, host):
    day = date(2032, 5, 3)
    clock = FrozenClock(datetime.combine(day, time(4, 0), tzinfo=UTC))
    weekly = store_weekly(admin, day, clock)
    monthly = store_monthly(admin, day, clock)
    client = TestClient(create_app(dsn=f"postgresql://b049_web@{host}/inves_cog", clock=clock))
    review = client.get("/api/pages/review", params={"date": day.isoformat()}).json()
    for name in ("案例库", "周报", "月报", "漏检报告", "模式库候选"):
        assert name in review
    for name in WEEKLY_BLOCKS:
        assert name in review["周报"] and name in weekly
    for name in MONTHLY_BLOCKS:
        assert name in review["月报"] and name in monthly
    paths = (
        "/api/pages/home",
        "/api/pages/market",
        "/api/pages/linkage/b049-missing",
        "/api/pages/stock/NVDA",
        "/api/pages/graph",
        "/api/pages/settings/data",
        "/api/pages/review",
    )
    for path in paths:
        response = client.get(path, params={"date": day.isoformat()})
        assert response.status_code == 200
        assert not (_keys(response.json()) & FORBIDDEN_FIELDS)


def test_review_grants(admin, host):
    text = (ROOT / "migrations/phase1_m10_0001_review.sql").read_text()
    assert text.count("CREATE TABLE") == 7
    assert "CREATE ROLE" not in text and "ALTER TABLE" not in text
    for name in (
        "perception.cases",
        "perception.case_labels",
        "perception.precursor_snapshots",
        "perception.miss_samples",
        "perception.patterns",
        "perception.reports_weekly",
        "perception.reports_monthly",
    ):
        assert name in text
        assert _priv(admin, "role_perception", name, "INSERT")
        assert _priv(admin, "role_web", name, "SELECT")
        assert not _priv(admin, "role_web", name, "INSERT")
        for role in (
            "role_trading",
            "role_overlay",
            "role_shadow",
            "role_ingest",
            "role_marketstate",
            "role_valuation",
        ):
            assert not _priv(admin, role, name, "SELECT")
    acl = admin.execute(
        """
        SELECT relacl::text AS acl FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'perception' AND relation.relname = 'cases'
        """
    ).fetchone()["acl"]
    assert not any(part.startswith("=") for part in acl.strip("{}").split(","))
    seen = datetime(2032, 5, 3, 2, tzinfo=UTC)
    writer = psycopg.connect(
        host=host, dbname="inves_cog", user="b049_perception", row_factory=dict_row, autocommit=True
    )
    writer.execute(
        """
        INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, updated_at)
        VALUES ('b049-grant', 'b049-grant', '2032-05-03', '未完成', %s)
        """,
        (seen,),
    )
    writer.close()
    reader = psycopg.connect(host=host, dbname="inves_cog", user="b049_web", row_factory=dict_row, autocommit=True)
    counted = reader.execute("SELECT count(*) AS n FROM perception.cases WHERE case_id = 'b049-grant'").fetchone()
    assert counted["n"] == 1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        reader.execute(
            """
            INSERT INTO perception.cases (case_id, anomaly_id, trade_date, status, updated_at)
            VALUES ('b049-web', 'b049-web', '2032-05-03', '未完成', %s)
            """,
            (seen,),
        )
    reader.close()


def test_review_schedule_waits_then_skips(admin):
    day = _session(date(2032, 1, 5))
    upstream = {"rows": []}

    def records(task):
        if task == "anomaly_daily":
            return upstream["rows"]
        if task == "market_structure":
            return upstream["market"]
        return _jobs(admin, day, task)

    upstream["market"] = []
    early = _at(day, 7, 0)
    early_result = poll("review_labels", early, records=records, connection=admin, clock=FrozenClock(early))
    assert early_result["status"] == "not_due"
    waiting = _at(day, 7, 35)
    assert (
        poll("review_labels", waiting, records=records, connection=admin, clock=FrozenClock(waiting))["status"]
        == "waiting_dependencies"
    )
    assert _jobs(admin, day, "review_labels") == []
    deadline = _at(day, 7, 40)
    skipped = poll("review_labels", deadline, records=records, connection=admin, clock=FrozenClock(deadline))
    assert skipped["error_summary"].startswith("skipped_upstream:") and "anomaly_daily" in skipped["error_summary"]
    stored = _jobs(admin, day, "review_labels")
    assert stored[0]["status"] == "failed" and stored[0]["error_summary"].startswith("skipped_upstream:")
    again = poll("review_labels", deadline, records=records, connection=admin, clock=FrozenClock(deadline))
    assert again["status"] == "already_attempted"
    ready = _at(day, 21, 15)
    upstream["market"] = [{"status": "ok", "ended_at": ready - timedelta(minutes=1), "task_name": "market_structure"}]

    def succeed():
        run_recorded(
            admin,
            clock=FrozenClock(ready),
            task_name="review_snapshots",
            trade_date=day,
            params_version=PARAMS,
            operation=lambda: 1,
        )

    snapped = poll(
        "review_snapshots", ready, records=records, connection=admin, clock=FrozenClock(ready), operation=succeed
    )
    assert snapped["status"] == "ok"
    assert _jobs(admin, day, "review_snapshots")[0]["status"] == "ok"
    report_at = _at(day, 7, 45)
    finished = [{"status": "ok", "ended_at": report_at - timedelta(seconds=1)}]

    def report_records(task):
        if task in {"review_labels", "review_snapshots"}:
            return finished
        return []

    missed = poll("review_reports", report_at, records=report_records, operation=lambda: None)
    assert missed == {"status": "failed", "reason": "no_job_row"}


def _roles(admin):
    for name, parent in (("b049_perception", "role_perception"), ("b049_web", "role_web")):
        admin.execute(
            f"""
            DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{name}') THEN
            CREATE ROLE {name} LOGIN INHERIT; END IF; END $$
            """
        )
        admin.execute(f"GRANT {parent} TO {name}")


def _clean(admin):
    admin.execute("DELETE FROM perception.case_labels WHERE case_id LIKE 'b049-%'")
    admin.execute("DELETE FROM perception.cases WHERE case_id LIKE 'b049-%' OR anomaly_id LIKE 'b049-%'")
    admin.execute(
        """
        DELETE FROM perception.precursor_snapshots
        WHERE trade_date >= DATE '2032-01-01' AND trade_date < DATE '2033-01-01'
        """
    )
    admin.execute(
        """
        DELETE FROM perception.miss_samples
        WHERE item_ref LIKE 'b049%' OR item_ref LIKE 'B049%' OR item_ref LIKE 'W049%'
           OR anomaly_id LIKE 'b049-%' OR sample_id LIKE 'b049-%'
        """
    )
    admin.execute("DELETE FROM perception.patterns WHERE trigger_type LIKE 'b049-%'")
    admin.execute(
        """
        DELETE FROM perception.reports_weekly
        WHERE report_id LIKE 'week:2032%' OR report_id LIKE 'oneliner:2032%' OR period_end >= DATE '2032-01-01'
        """
    )
    admin.execute("DELETE FROM perception.reports_monthly WHERE period_end >= DATE '2032-01-01'")
    admin.execute("DELETE FROM perception.second_hits WHERE event_id LIKE 'b049-%'")
    admin.execute("DELETE FROM perception.candidates WHERE anomaly_id LIKE 'b049-%'")
    admin.execute("DELETE FROM perception.linkage_events WHERE event_id LIKE 'b049-%' OR anomaly_id LIKE 'b049-%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b049-%'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b049-%'")
    admin.execute("DELETE FROM ingest.bars_daily WHERE ticker LIKE 'B049%' OR ticker IN ('AAA', 'BBB', 'CCC')")
    admin.execute("DELETE FROM ingest.short_interest WHERE observation_id = 'b049-si'")
    admin.execute(
        """
        DELETE FROM ingest.wide_universe
        WHERE ticker LIKE 'W049%' OR (ticker = 'NVDA' AND trade_date = DATE '2032-07-31')
        """
    )
    admin.execute(
        """
        DELETE FROM marketstate.daily
        WHERE ticker LIKE 'B049%' OR (ticker = 'NVDA' AND trade_date >= DATE '2032-04-01')
        """
    )
    admin.execute("DELETE FROM graph.baskets WHERE basket_id = 'b049-basket'")
    admin.execute("DELETE FROM valuation_v1.position_panel WHERE ticker LIKE 'B049%'")
    admin.execute("DELETE FROM valuation_v1.ranges WHERE ticker LIKE 'B049%'")
    admin.execute("DELETE FROM trading.plan WHERE portfolio_id = 'b049'")
    admin.execute("DELETE FROM factor_shadow.daily WHERE factor_id = 'b049-f'")
    admin.execute("DELETE FROM factor_shadow.registry WHERE factor_id = 'b049-f'")
    admin.execute("DELETE FROM perception_shadow.signals WHERE signal_key = 'b049-x1'")
    admin.execute("DELETE FROM ingest.job_runs WHERE task_name LIKE 'review_%' AND trade_date >= DATE '2032-01-01'")


def _span(start, count):
    day = start if trading_day(start) else next_trading_day(start)
    days = [day]
    for _ in range(count - 1):
        day = next_trading_day(day)
        days.append(day)
    return days


def _session(day):
    return day if trading_day(day) else next_trading_day(day)


def _at(day, hour, minute):
    return datetime.combine(day, time(hour, minute), tzinfo=NY)


def _anomaly(admin, anomaly_id, ticker, day, generated, universe="pool"):
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction,
            max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe,
            params_version, generated_at
        ) VALUES (
            %s, %s, 'close', ARRAY['A'], 'L3', 'alert', ARRAY['b049'], %s, 'up',
            1.1, '{}', '{}', '{}', ARRAY[]::text[], '已发现·原因未明', %s, 'p-2026.10', %s
        )
        """,
        (anomaly_id, day, Jsonb([{"ticker": ticker}]), universe, generated),
    )


def _bar(admin, ticker, day, close):
    admin.execute(
        "INSERT INTO ingest.bars_daily (ticker, trade_date, close, source) VALUES (%s, %s, %s, 'b049')",
        (ticker, day, close),
    )


def _info(admin, info_id, seen, attention, found):
    admin.execute(
        """
        INSERT INTO ingest.info_items (
            info_id, kind, first_seen_at, source, source_level, headline, tickers, entities,
            extraction_status, flags, payload, extraction_source
        ) VALUES (
            %s, 'news', %s, 'b049', 2, 'h', ARRAY[]::text[], ARRAY[]::text[], 'ok', %s, %s, '{}'
        )
        """,
        (info_id, seen, ["attention"] if attention else [], Jsonb({"system_found": found})),
    )


def _daily(admin, ticker, day, ret):
    admin.execute(
        """
        INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
        VALUES (%s, %s, 'close', %s, 'p-2026.10', ARRAY['ok'])
        """,
        (day, ticker, ret),
    )


def _wide(admin, ticker, day):
    admin.execute(
        """
        INSERT INTO ingest.wide_universe (trade_date, ticker, included, notes)
        VALUES (%s, %s, true, ARRAY[]::text[])
        """,
        (day, ticker),
    )


def _range(admin, ticker, day, neutral, seen, reason):
    payload = {"label": LABEL, "change_reason": reason} if reason else {"label": LABEL}
    admin.execute(
        """
        INSERT INTO valuation_v1.ranges (
            trade_date, ticker, params_version, method_version, version, type, status,
            bear, neutral, bull, pending_review, payload, observed_at
        ) VALUES (%s, %s, 'p-2026.10', 'v1', 'v1', 'range', 'ok', 10, %s, 30, false, %s, %s)
        """,
        (day, ticker, neutral, Jsonb(payload), seen),
    )


def _panel(admin, ticker, day, seen):
    admin.execute(
        """
        INSERT INTO valuation_v1.position_panel (trade_date, ticker, params_version, payload, observed_at)
        VALUES (%s, %s, 'p-2026.10', %s, %s)
        """,
        (day, ticker, Jsonb({"label": LABEL, "flag_yellow": True}), seen),
    )


def _plan(admin, day, seen):
    admin.execute(
        """
        INSERT INTO trading.plan (
            portfolio_id, trade_date, signal_date, extractor, rule_set, params_version, published, generated_at, payload
        ) VALUES ('b049', %s, %s, 'fixed', 'A', 'p-2026.10', true, %s, %s)
        """,
        (
            day,
            day,
            seen,
            Jsonb({"skips": [{"ticker": "B049S", "n_code": "N5", "reason_zh": "事件冷静期，暂停买入"}]}),
        ),
    )


def _sample_id(frame, period, item):
    return frame + ":" + period.isoformat() + ":" + item


def _patterns(admin):
    rebuild_patterns(admin, FrozenClock(datetime(2032, 2, 2, 4, tzinfo=UTC)))
    return admin.execute(
        "SELECT trigger_type, status, example_count, retained_holds, counterexamples FROM perception.patterns"
    ).fetchall()


def _jobs(admin, day, task):
    return list(
        admin.execute(
            """
            SELECT status, error_summary, ended_at FROM ingest.job_runs
            WHERE trade_date = %s AND task_name = %s ORDER BY id
            """,
            (day, task),
        ).fetchall()
    )


def _priv(admin, role, table, privilege):
    return admin.execute("SELECT has_table_privilege(%s, %s, %s) AS ok", (role, table, privilege)).fetchone()["ok"]


def _keys(value):
    found = set()
    if isinstance(value, dict):
        found.update(value)
        for item in value.values():
            found.update(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_keys(item))
    return found
