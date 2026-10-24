"""B-052 review execution. A counting client stands in for the model."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import next_trading_day, trading_day
from inves_cog.perception.review.calendar import cutoff
from inves_cog.perception.review.schedule import due_tasks, review_day, run_cycle
from inves_cog.perception.review.snapshots import pool_tickers
from inves_cog.web.html_page import render_page
from inves_cog.web.pages import page_home, page_market
from scripts.schedule_review import run_once
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking

NY = ZoneInfo("America/New_York")
UPSTREAM = ("anomaly_daily", "attribution_labels", "bars_full")


class Counting:
    def __init__(self):
        self.calls = []

    def call(self, task, payload):
        self.calls.append((task, payload))
        ids = payload["facts"]["anomaly_ids"]
        return {"text": ids[0] if ids else "无异常"}


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


def test_review_window_is_the_morning_after_the_session():
    day = _midweek(date(2033, 4, 4))
    morning = _at(day + timedelta(days=1), 2, 0)
    assert review_day(morning) == day
    assert review_day(_at(day + timedelta(days=1), 0, 30)) is None
    assert review_day(_at(day + timedelta(days=1), 1, 0)) == day
    assert review_day(_at(day + timedelta(days=1), 7, 30)) == day
    assert review_day(_at(day + timedelta(days=1), 7, 31)) is None
    assert "review_weekly_sample" not in due_tasks(day)
    friday = _period_end(date(2033, 4, 4), month=False)
    assert review_day(_at(friday + timedelta(days=1), 2, 0)) == friday
    assert review_day(_at(friday + timedelta(days=3), 3, 0)) is None
    assert "review_weekly_sample" in due_tasks(friday)


def test_q1_real_execution(admin, host):
    day = _midweek(date(2033, 4, 4))
    previous = _previous(day)
    moment = _at(day + timedelta(days=1), 2, 0)
    _anomaly(admin, "b052-due", previous, datetime.combine(previous, time(15, 0), tzinfo=NY))
    _upstream(admin, day, moment)
    client = Counting()
    before = _review_state(admin)
    ingest, perception = _logins(host)
    try:
        first = run_once(clock=FrozenClock(moment), connection=ingest, writer=perception, client=client)
        second = run_once(clock=FrozenClock(moment), connection=ingest, writer=perception, client=client)
        assert first["status"] == "ok" and second["status"] == "already_attempted"
        assert len(client.calls) == 1 and client.calls[0][0] == "summary_oneliner"
        baskets = _baskets(admin)
        snapshots = _count(admin, "perception.precursor_snapshots", "trade_date = %s", day)
        assert len(pool_tickers()) == 59
        assert snapshots == 59 + baskets
        label = admin.execute(
            "SELECT horizon FROM perception.case_labels WHERE case_id = 'b052-due' ORDER BY horizon"
        ).fetchall()
        assert [row["horizon"] for row in label] == ["T+1"]
        assert _count(admin, "perception.reports_weekly", "report_id = %s", "oneliner:" + day.isoformat()) == 1
        jobs = {name: _ok_job(admin, day, name) for name in ("review_snapshots", "review_labels", "review_oneliner")}
        assert jobs["review_snapshots"]["processed_count"] == snapshots
        assert jobs["review_labels"]["processed_count"] == _added(admin, before)
        assert jobs["review_oneliner"]["processed_count"] == 1
        assert all(row["status"] == "ok" for row in jobs.values())
    finally:
        ingest.close()
        perception.close()
        _restore(admin, before)


def test_q2_week_and_month(admin, host):
    week_end = _period_end(date(2033, 4, 4), month=False)
    month_end = _period_end(date(2033, 4, 4), month=True)
    client = Counting()
    before = _review_state(admin)
    ingest, perception = _logins(host)
    try:
        _seed_period(admin, week_end)
        week_moment = _at(week_end + timedelta(days=1), 2, 0)
        week = run_once(clock=FrozenClock(week_moment), connection=admin, writer=perception, client=client)
        week_again = run_once(clock=FrozenClock(week_moment), connection=admin, writer=perception, client=client)
        _seed_period(admin, month_end)
        month_moment = _at(month_end + timedelta(days=1), 2, 0)
        month = run_once(clock=FrozenClock(month_moment), connection=admin, writer=perception, client=client)
        month_again = run_once(clock=FrozenClock(month_moment), connection=admin, writer=perception, client=client)
        assert week["status"] == month["status"] == "ok"
        assert week_again["status"] == month_again["status"] == "already_attempted"
        weekly_rows = _count(admin, "perception.miss_samples", "frame = 'weekly_info' AND period_end = %s", week_end)
        assert weekly_rows >= 1
        assert _count(admin, "perception.miss_samples", "item_ref = %s", "b052-info-" + week_end.isoformat()) == 1
        assert _count(admin, "perception.reports_weekly", "report_id = %s", "week:" + week_end.isoformat()) == 1
        assert _count(admin, "perception.miss_samples", "item_ref = %s", "B052M:" + month_end.isoformat()) == 1
        assert _count(admin, "perception.reports_monthly", "report_id = %s", "month:" + month_end.isoformat()) == 1
        assert _ok_job(admin, week_end, "review_weekly_sample")["processed_count"] == weekly_rows
        assert _ok_job(admin, week_end, "review_weekly_report")["processed_count"] == 1
        assert _ok_job(admin, month_end, "review_monthly_sample")["processed_count"] >= 1
        assert _ok_job(admin, month_end, "review_monthly_report")["processed_count"] == 1
        assert len(client.calls) == 2
    finally:
        ingest.close()
        perception.close()
        _restore(admin, before)


def test_q3_wait_then_skip(admin, host):
    day = _midweek(date(2033, 5, 2))
    waiting_at = _at(day + timedelta(days=1), 2, 0)
    deadline = _at(day + timedelta(days=1), 7, 30)
    _upstream(admin, day, waiting_at, labels=False)
    client = Counting()
    ingest, perception = _logins(host)
    try:
        waiting = run_once(clock=FrozenClock(waiting_at), connection=ingest, writer=perception, client=client)
        skipped = run_once(clock=FrozenClock(deadline), connection=ingest, writer=perception, client=client)
        again = run_once(clock=FrozenClock(deadline), connection=ingest, writer=perception, client=client)
    finally:
        ingest.close()
        perception.close()
    assert waiting["status"] == "waiting_dependencies"
    assert skipped["status"] == "failed" and skipped["error_summary"].startswith("skipped_upstream:")
    assert "attribution_labels" in skipped["error_summary"]
    assert again["status"] == "already_attempted"
    assert client.calls == []
    assert _count(admin, "perception.precursor_snapshots", "trade_date = %s", day) == 0
    assert _count(admin, "perception.cases", "case_id LIKE %s", "b052-%") == 0
    stored = _jobs(admin, day, "review_snapshots")
    assert len(stored) == 1
    assert stored[0]["status"] == "failed" and stored[0]["error_summary"].startswith("skipped_upstream:")


def test_q4_perception_writer(admin, host):
    day = _midweek(date(2033, 6, 1))
    previous = _previous(day)
    moment = _at(day + timedelta(days=1), 2, 0)
    _anomaly(admin, "b052-role", previous, datetime.combine(previous, time(15, 0), tzinfo=NY))
    _upstream(admin, day, moment)
    client = Counting()
    before = _review_state(admin)
    ingest, perception = _logins(host)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            ingest.execute(
                """
                INSERT INTO perception.precursor_snapshots (trade_date, subject_kind, subject_id, features)
                VALUES (%s, 'ticker', 'NVDA', '{}')
                """,
                (day,),
            )
        blocked = run_once(clock=FrozenClock(moment), connection=ingest, writer=None, client=client)
        assert blocked["status"] == "failed"
        assert blocked["error_summary"] == "缺少 INVES_COG_PERCEPTION_DATABASE_URL"
        assert client.calls == []
        assert _count(admin, "perception.precursor_snapshots", "trade_date = %s", day) == 0
        done = run_once(clock=FrozenClock(moment), connection=ingest, writer=perception, client=client)
        assert done["status"] == "ok"
        assert len(client.calls) == 1
        assert _count(admin, "perception.precursor_snapshots", "trade_date = %s", day) == 59 + _baskets(admin)
        assert perception.execute("SELECT current_user AS name").fetchone()["name"] == "b052_perception"
    finally:
        ingest.close()
        perception.close()
        _restore(admin, before)


def test_q5_run_once(admin, host):
    day = _midweek(date(2033, 7, 5))
    previous = _previous(day)
    moment = _at(day + timedelta(days=1), 3, 0)
    _anomaly(admin, "b052-once", previous, datetime.combine(previous, time(15, 0), tzinfo=NY))
    _upstream(admin, day, moment)
    first_client = Counting()
    restarted = Counting()
    before = _review_state(admin)
    ingest, perception = _logins(host)
    try:
        ran = _run(ingest, perception, day, moment, first_client)
        again = _run(ingest, perception, day, moment, first_client)
        after_restart = _run(ingest, perception, day, moment, restarted)
        assert ran["status"] == "ok"
        assert again["status"] == "already_attempted"
        assert after_restart["status"] == "already_attempted"
        assert len(first_client.calls) == 1
        assert restarted.calls == []
        assert _count(admin, "perception.reports_weekly", "report_id = %s", "oneliner:" + day.isoformat()) == 1
        assert len(_jobs(admin, day, "review_oneliner")) == 1
    finally:
        ingest.close()
        perception.close()
        _restore(admin, before)


def test_q6_pool_unhandled(admin):
    day = _midweek(date(2033, 8, 2))
    seen = cutoff(day) - timedelta(hours=2)
    _anomaly(admin, "b052-p1", day, seen, universe="pool")
    _anomaly(admin, "b052-p2", day, seen, universe="pool")
    for index in range(94):
        _anomaly(admin, f"b052-w{index:02d}", day, seen, universe="wide")
    late = FrozenClock(cutoff(day) + timedelta(minutes=1))
    early = FrozenClock(cutoff(day) - timedelta(minutes=1))
    home = page_home(admin, day, late)
    market = page_market(admin, day, late)
    assert home["counts"]["anomaly_count"] == 96
    assert home["counts"]["pool_anomaly_count"] == 2
    assert home["counts"]["wide_anomaly_count"] == 94
    assert {row["anomaly_id"] for row in home["unhandled"]} == {"b052-p1", "b052-p2"}
    assert all(row["highlighted"] is True for row in home["unhandled"])
    assert all(row["highlighted"] is False for row in page_home(admin, day, early)["unhandled"])
    listed = {row["anomaly_id"]: row for row in market["anomalies"]}
    assert len(listed) == 96
    assert listed["b052-w00"]["universe"] == "wide" and listed["b052-w00"]["highlighted"] is False
    assert listed["b052-p1"]["highlighted"] is True
    home_html = render_page(home)
    market_html = render_page(market)
    assert "b052-p1" in home_html and "标红" in home_html and "b052-w00" not in home_html
    assert "b052-w00" in market_html
    assert _marked(market_html, "b052-p1")
    assert not _marked(market_html, "b052-w00")


def _marked(html, anomaly_id):
    before = html[: html.index(anomaly_id)]
    opened = before.rfind("<div")
    return 'class="mark"' in before[opened : opened + 40]


def _review_state(admin):
    cases = admin.execute("SELECT case_id, status, reason, updated_at FROM perception.cases").fetchall()
    labels = admin.execute("SELECT case_id, horizon FROM perception.case_labels").fetchall()
    return {
        "cases": {row["case_id"]: row for row in cases},
        "labels": {(row["case_id"], row["horizon"]) for row in labels},
    }


def _added(admin, before):
    cases = admin.execute("SELECT case_id FROM perception.cases").fetchall()
    labels = admin.execute("SELECT case_id, horizon FROM perception.case_labels").fetchall()
    new_cases = sum(row["case_id"] not in before["cases"] for row in cases)
    new_labels = sum((row["case_id"], row["horizon"]) not in before["labels"] for row in labels)
    return new_cases + new_labels


def _restore(admin, before):
    for row in admin.execute("SELECT case_id, horizon FROM perception.case_labels").fetchall():
        if (row["case_id"], row["horizon"]) not in before["labels"]:
            admin.execute(
                "DELETE FROM perception.case_labels WHERE case_id = %s AND horizon = %s",
                (row["case_id"], row["horizon"]),
            )
    for row in admin.execute("SELECT case_id FROM perception.cases").fetchall():
        if row["case_id"] not in before["cases"]:
            admin.execute("DELETE FROM perception.case_labels WHERE case_id = %s", (row["case_id"],))
            admin.execute("DELETE FROM perception.cases WHERE case_id = %s", (row["case_id"],))
    for case_id, row in before["cases"].items():
        admin.execute(
            """
            UPDATE perception.cases SET status = %s, reason = %s, updated_at = %s WHERE case_id = %s
            """,
            (row["status"], row["reason"], row["updated_at"], case_id),
        )


def _run(ingest, perception, day, moment, client):
    return run_cycle(
        moment,
        records=_records(ingest, day),
        connection=ingest,
        writer=perception,
        clock=FrozenClock(moment),
        client=client,
    )


def _records(connection, day):
    def records(task):
        return list(
            connection.execute(
                """
                SELECT task_name, status, ended_at, error_summary, processed_count
                FROM ingest.job_runs
                WHERE trade_date = %s AND task_name = %s
                ORDER BY id
                """,
                (day, task),
            ).fetchall()
        )

    return records


def _logins(host):
    ingest = psycopg.connect(host=host, dbname="inves_cog", user="b052_ingest", row_factory=dict_row, autocommit=True)
    perception = psycopg.connect(
        host=host, dbname="inves_cog", user="b052_perception", row_factory=dict_row, autocommit=True
    )
    return ingest, perception


def _roles(admin):
    for name, parent in (("b052_ingest", "role_ingest"), ("b052_perception", "role_perception")):
        admin.execute(
            f"""
            DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{name}') THEN
            CREATE ROLE {name} LOGIN INHERIT; END IF; END $$
            """
        )
        admin.execute(f"GRANT {parent} TO {name}")


def _clean(admin):
    admin.execute("DELETE FROM perception.case_labels WHERE case_id LIKE 'b052-%'")
    admin.execute("DELETE FROM perception.cases WHERE case_id LIKE 'b052-%' OR anomaly_id LIKE 'b052-%'")
    admin.execute(
        """
        DELETE FROM perception.precursor_snapshots
        WHERE trade_date >= DATE '2033-01-01' AND trade_date < DATE '2034-01-01'
        """
    )
    admin.execute(
        """
        DELETE FROM perception.miss_samples
        WHERE item_ref LIKE 'b052%' OR sample_id LIKE '%b052%' OR period_end >= DATE '2033-01-01'
        """
    )
    admin.execute(
        """
        DELETE FROM perception.reports_weekly
        WHERE report_id LIKE 'oneliner:2033%' OR report_id LIKE 'week:2033%' OR period_end >= DATE '2033-01-01'
        """
    )
    admin.execute("DELETE FROM perception.reports_monthly WHERE report_id LIKE 'month:2033%'")
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'b052-%'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b052-%'")
    admin.execute("DELETE FROM marketstate.daily WHERE ticker LIKE 'B052%'")
    admin.execute(
        """
        DELETE FROM ingest.job_runs
        WHERE trade_date >= DATE '2033-01-01' AND trade_date < DATE '2034-01-01'
          AND (task_name LIKE 'review_%' OR params_version = 'b052')
        """
    )


def _upstream(admin, day, moment, labels=True):
    names = UPSTREAM if labels else ("anomaly_daily", "bars_full")
    for name in names:
        admin.execute(
            """
            INSERT INTO ingest.job_runs (
                task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
            ) VALUES (%s, %s, %s, %s, 'ok', 1, NULL, 'b052')
            """,
            (name, day, moment - timedelta(minutes=5), moment - timedelta(minutes=1)),
        )


def _seed_period(admin, day):
    moment = _at(day + timedelta(days=1), 2, 0)
    _upstream(admin, day, moment)
    admin.execute(
        """
        INSERT INTO ingest.info_items (
            info_id, kind, first_seen_at, source, source_level, headline, tickers, entities,
            extraction_status, flags, payload, extraction_source
        ) VALUES (
            %s, 'news', %s, 'b052', 2, 'h', ARRAY[]::text[], ARRAY[]::text[], 'ok', ARRAY[]::text[], %s, '{}'
        )
        """,
        ("b052-info-" + day.isoformat(), cutoff(day) - timedelta(days=1), Jsonb({"system_found": False})),
    )
    admin.execute(
        """
        INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
        VALUES (%s, 'B052M', 'close', 0.02, 'p-2026.10', ARRAY['ok'])
        """,
        (day,),
    )


def _anomaly(admin, anomaly_id, day, generated, universe="pool"):
    admin.execute(
        """
        INSERT INTO perception.anomalies (
            anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction,
            max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe,
            params_version, generated_at
        ) VALUES (
            %s, %s, 'close', ARRAY['A'], 'L3', 'alert', ARRAY['b052'], %s, 'up',
            1.1, '{}', '{}', '{}', ARRAY[]::text[], '已发现·原因未明', %s, 'b052', %s
        )
        """,
        (anomaly_id, day, Jsonb([{"ticker": "NVDA"}]), universe, generated),
    )


def _count(connection, table, clause, param):
    params = () if param is None else (param,)
    return connection.execute(f"SELECT count(*) AS n FROM {table} WHERE {clause}", params).fetchone()["n"]


def _ok_job(connection, day, task):
    return connection.execute(
        """
        SELECT status, processed_count FROM ingest.job_runs
        WHERE trade_date = %s AND task_name = %s AND status = 'ok'
        ORDER BY id DESC LIMIT 1
        """,
        (day, task),
    ).fetchone()


def _jobs(connection, day, task):
    return list(
        connection.execute(
            """
            SELECT status, error_summary, processed_count FROM ingest.job_runs
            WHERE trade_date = %s AND task_name = %s ORDER BY id
            """,
            (day, task),
        ).fetchall()
    )


def _baskets(admin):
    return admin.execute("SELECT count(*) AS n FROM graph.baskets").fetchone()["n"]


def _at(day, hour, minute):
    return datetime.combine(day, time(hour, minute), tzinfo=NY)


def _previous(day):
    cursor = day - timedelta(days=1)
    while not trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor


def _midweek(start):
    day = start if trading_day(start) else next_trading_day(start)
    for _ in range(20):
        nxt = next_trading_day(day)
        if nxt.isocalendar()[:2] == day.isocalendar()[:2] and (nxt.year, nxt.month) == (day.year, day.month):
            return day
        day = nxt
    raise AssertionError("no midweek session")


def _period_end(start, *, month):
    day = start if trading_day(start) else next_trading_day(start)
    for _ in range(40):
        nxt = next_trading_day(day)
        week_end = nxt.isocalendar()[:2] != day.isocalendar()[:2]
        month_end = (nxt.year, nxt.month) != (day.year, day.month)
        if month and month_end:
            return day
        if not month and week_end and not month_end:
            return day
        day = nxt
    raise AssertionError("no period end")
