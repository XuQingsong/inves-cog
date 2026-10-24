"""B-056 review identity, retry cap, and oneliner accounting. No live model."""

import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.clock import FrozenClock
from inves_cog.ingest.market import next_trading_day, trading_day
from inves_cog.perception.review.patterns import rebuild_patterns
from inves_cog.perception.review.schedule import UPSTREAM, review_day, run_cycle
from scripts.schedule_review import _EnvironmentClient
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking

NY = ZoneInfo("America/New_York")
REVIEW_TABLES = (
    "perception.case_labels",
    "perception.cases",
    "perception.precursor_snapshots",
    "perception.miss_samples",
    "perception.patterns",
    "perception.reports_weekly",
    "perception.reports_monthly",
)
UPSTREAM_TABLES = (
    "marketstate.daily",
    "trading.plan",
    "valuation_v1.ranges",
    "valuation_v1.position_panel",
    "perception.anomalies",
    "perception.candidates",
    "perception.second_hits",
    "perception.linkage_events",
    "perception_shadow.signals",
    "factor_shadow.daily",
)


class _Plain:
    def __init__(self):
        self.calls = []

    def call(self, task, payload):
        self.calls.append(task)
        return {"text": "今天无异常"}


class _Trace:
    def __init__(self, connection, name, log):
        self._connection = connection
        self.name = name
        self.log = log

    def execute(self, query, params=None):
        self.log.append((self.name, query))
        if params is None:
            return self._connection.execute(query)
        return self._connection.execute(query, params)


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
    rebuild_patterns(connection, FrozenClock(datetime(2035, 1, 2, 6, tzinfo=NY)))
    connection.close()


def test_r1_reports_select_review_tables_on_the_perception_connection(admin, host):
    week_end = _period_end(date(2035, 4, 1), month=False)
    month_end = _period_end(date(2035, 4, 1), month=True)
    client = _Plain()
    log = []
    ingest, perception = _logins(host)
    try:
        for table in REVIEW_TABLES:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                ingest.execute(f"SELECT 1 FROM {table}")
        _seed(admin, week_end)
        _seed(admin, month_end)
        week = _traced(ingest, perception, _at(week_end + timedelta(days=1), 2, 0), client, log)
        month = _traced(ingest, perception, _at(month_end + timedelta(days=1), 2, 0), client, log)
        assert week["status"] == month["status"] == "ok"
        assert _count(admin, "perception.reports_weekly", "report_id = %s", "week:" + week_end.isoformat()) == 1
        assert _count(admin, "perception.reports_monthly", "report_id = %s", "month:" + month_end.isoformat()) == 1
        review_sql = [(name, sql) for name, sql in log if _review_tables(sql)]
        assert review_sql
        assert {name for name, _sql in review_sql} == {"perception"}
        selects = [sql for name, sql in review_sql if sql.lstrip().lower().startswith("select")]
        assert any("perception.miss_samples" in sql for sql in selects)
        assert any("perception.case_labels" in sql for sql in selects)
        assert any("perception.patterns" in sql for sql in selects)
    finally:
        ingest.close()
        perception.close()


def test_r2_three_failures_stop_and_a_success_is_left_alone(admin, host):
    day = _midweek(date(2035, 3, 4))
    moment = _at(day + timedelta(days=1), 2, 0)
    _upstream(admin, day, moment)
    _insert_jobs(admin, day, "review_snapshots", "failed", 3, moment, "boom")
    _insert_jobs(admin, day, "review_labels", "ok", 1, moment, None)
    _insert_jobs(admin, day, "review_oneliner", "failed", 2, moment, "超时")
    client = _Plain()
    ingest, perception = _logins(host)
    try:
        first = _cycle(ingest, perception, moment, client)
        assert first["tasks"] == ["review_oneliner"]
        assert len(_rows(admin, day, "review_snapshots")) == 3
        assert _rows(admin, day, "review_labels") == [{"status": "ok", "error_summary": None, "processed_count": 1}]
        oneliner = _rows(admin, day, "review_oneliner")
        assert [row["status"] for row in oneliner] == ["failed", "failed", "ok"]
        assert oneliner[-1]["error_summary"] == "模型原文采用"
        assert len(client.calls) == 1
        restarted = _cycle(ingest, perception, moment, client)
        assert restarted["status"] == "already_attempted"
        assert len(_rows(admin, day, "review_snapshots")) == 3
        assert len(_rows(admin, day, "review_oneliner")) == 3
        assert len(client.calls) == 1
    finally:
        ingest.close()
        perception.close()


def test_r3_adopted_sentence_writes_one_llm_call(admin, host):
    day = _midweek(date(2035, 6, 3))
    moment = _at(day + timedelta(days=1), 2, 15)
    _upstream(admin, day, moment)
    sent = []
    clock = FrozenClock(moment)
    client = _EnvironmentClient(_llm_values(host), send=_reply(sent, "今天无异常"), clock=clock)
    before = _llm_count(admin)
    ingest, perception = _logins(host)
    try:
        result = _cycle(ingest, perception, moment, client)
        assert result["status"] == "ok"
        assert len(sent) == 1
        assert _llm_count(admin) == before + 1
        recorded = _llm_row(admin, clock.now_utc())
        assert recorded["task"] == "summary_oneliner" and recorded["status"] == "ok"
        assert _rows(admin, day, "review_oneliner")[-1]["error_summary"] == "模型原文采用"
    finally:
        _delete_llm(admin, clock.now_utc())
        ingest.close()
        perception.close()


def test_r3_ungrounded_text_is_a_template_result(admin, host):
    day = _midweek(date(2035, 7, 1))
    moment = _at(day + timedelta(days=1), 2, 20)
    _upstream(admin, day, moment)
    sent = []
    clock = FrozenClock(moment)
    client = _EnvironmentClient(_llm_values(host), send=_reply(sent, "没有编号"), clock=clock)
    ingest, perception = _logins(host)
    try:
        _cycle(ingest, perception, moment, client)
        assert len(sent) == 1
        assert _rows(admin, day, "review_oneliner")[-1]["error_summary"] == "模板（原文未引用当日编号）"
        stored = perception.execute(
            "SELECT payload->>'sentence' AS sentence FROM perception.reports_weekly WHERE report_id = %s",
            ("oneliner:" + day.isoformat(),),
        ).fetchone()
        assert stored["sentence"] == "今日异常 0 个，详见下方"
    finally:
        _delete_llm(admin, clock.now_utc())
        ingest.close()
        perception.close()


def test_r3_missing_database_url_fails_before_the_call(admin, host):
    day = _midweek(date(2035, 8, 1))
    moment = _at(day + timedelta(days=1), 2, 25)
    _upstream(admin, day, moment)
    sent = []
    values = _llm_values(host)
    values["INVES_COG_DATABASE_URL"] = ""
    before = _llm_count(admin)
    client = _EnvironmentClient(values, send=_reply(sent, "今天无异常"), clock=FrozenClock(moment))
    ingest, perception = _logins(host)
    try:
        with pytest.raises(RuntimeError, match="缺少 INVES_COG_DATABASE_URL"):
            _cycle(ingest, perception, moment, client)
        assert sent == []
        assert _llm_count(admin) == before
        failed = _rows(admin, day, "review_oneliner")
        assert len(failed) == 1
        assert failed[0]["status"] == "failed"
        assert failed[0]["error_summary"] == "缺少 INVES_COG_DATABASE_URL"
    finally:
        ingest.close()
        perception.close()


def test_r3_without_a_client_records_the_template_reason(admin, host):
    day = _midweek(date(2035, 9, 2))
    moment = _at(day + timedelta(days=1), 2, 30)
    _upstream(admin, day, moment)
    ingest, perception = _logins(host)
    try:
        result = _cycle(ingest, perception, moment, None)
        assert result["status"] == "ok"
        assert _rows(admin, day, "review_oneliner")[-1]["error_summary"] == "模板（未配置模型客户端）"
    finally:
        ingest.close()
        perception.close()


def _traced(ingest, perception, moment, client, log):
    return _cycle(_Trace(ingest, "ingest", log), _Trace(perception, "perception", log), moment, client)


def _cycle(connection, writer, moment, client):
    day = review_day(moment)
    return run_cycle(
        moment,
        records=_records(connection, day),
        connection=connection,
        writer=writer,
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


def _review_tables(sql):
    folded = " ".join(sql.lower().split())
    return [table for table in REVIEW_TABLES if table in folded]


def _llm_values(host):
    values = {"INVES_COG_DATABASE_URL": f"postgresql://b056_ingest@{host}/inves_cog"}
    for prefix in ("LLM_HARD", "LLM_STANDARD"):
        values[prefix + "_API_KEY"] = "fixture"
        values[prefix + "_BASE_URL"] = "https://fixture.invalid/v1"
        values[prefix + "_API_STYLE"] = "openai"
    return values


def _reply(box, text):
    from inves_cog.ingest.http import Response

    def send(method, url, **kwargs):
        box.append(kwargs["json"])
        body = json.dumps({"text": text}, ensure_ascii=False)
        usage = {"prompt_tokens": 2, "completion_tokens": 1}
        return Response(200, {"choices": [{"message": {"content": body}}], "usage": usage})

    return send


def _roles(admin):
    for name, parent in (("b056_ingest", "role_ingest"), ("b056_perception", "role_perception")):
        admin.execute(
            f"""
            DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{name}') THEN
            CREATE ROLE {name} LOGIN INHERIT; END IF; END $$
            """
        )
        admin.execute(f"GRANT {parent} TO {name}")
    for table in UPSTREAM_TABLES:
        schema = table.split(".", 1)[0]
        admin.execute(f"GRANT USAGE ON SCHEMA {schema} TO b056_ingest")
        admin.execute(f"GRANT SELECT ON TABLE {table} TO b056_ingest")


def _logins(host):
    ingest = psycopg.connect(host=host, dbname="inves_cog", user="b056_ingest", row_factory=dict_row, autocommit=True)
    perception = psycopg.connect(
        host=host, dbname="inves_cog", user="b056_perception", row_factory=dict_row, autocommit=True
    )
    return ingest, perception


def _clean(admin):
    admin.execute(
        """
        DELETE FROM perception.reports_weekly
        WHERE report_id LIKE 'oneliner:2035%' OR report_id LIKE 'week:2035%'
           OR (period_end >= DATE '2035-01-01' AND period_end < DATE '2036-01-01')
        """
    )
    admin.execute("DELETE FROM perception.reports_monthly WHERE report_id LIKE 'month:2035%'")
    admin.execute(
        """
        DELETE FROM perception.miss_samples
        WHERE period_end >= DATE '2035-01-01' AND period_end < DATE '2036-01-01'
        """
    )
    admin.execute(
        """
        DELETE FROM perception.precursor_snapshots
        WHERE trade_date >= DATE '2035-01-01' AND trade_date < DATE '2036-01-01'
        """
    )
    admin.execute("DELETE FROM marketstate.daily WHERE ticker = 'B056M'")
    admin.execute("DELETE FROM ingest.info_items WHERE info_id LIKE 'b056-%'")
    admin.execute(
        """
        DELETE FROM ingest.job_runs
        WHERE trade_date >= DATE '2035-01-01' AND trade_date < DATE '2036-01-01'
          AND (task_name LIKE 'review_%' OR task_name = ANY(%s) OR params_version = 'b056')
        """,
        (list(UPSTREAM),),
    )


def _seed(admin, day):
    moment = _at(day + timedelta(days=1), 2, 0)
    _upstream(admin, day, moment)
    admin.execute(
        """
        INSERT INTO marketstate.daily (trade_date, ticker, session, ret, factor_set, health_codes)
        VALUES (%s, 'B056M', 'close', 0.02, 'p-2026.10', ARRAY['ok'])
        """,
        (day,),
    )


def _upstream(admin, day, moment):
    for name in UPSTREAM:
        admin.execute(
            """
            INSERT INTO ingest.job_runs (
                task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
            ) VALUES (%s, %s, %s, %s, 'ok', 1, NULL, 'b056')
            """,
            (name, day, moment - timedelta(minutes=5), moment - timedelta(minutes=1)),
        )


def _insert_jobs(admin, day, task, status, count, moment, summary):
    for _index in range(count):
        admin.execute(
            """
            INSERT INTO ingest.job_runs (
                task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'b056')
            """,
            (
                task,
                day,
                moment - timedelta(minutes=10),
                moment - timedelta(minutes=9),
                status,
                1 if status == "ok" else 0,
                summary,
            ),
        )


def _rows(connection, day, task):
    return list(
        connection.execute(
            """
            SELECT status, error_summary, processed_count FROM ingest.job_runs
            WHERE trade_date = %s AND task_name = %s ORDER BY id
            """,
            (day, task),
        ).fetchall()
    )


def _count(connection, table, clause, param):
    return connection.execute(f"SELECT count(*) AS n FROM {table} WHERE {clause}", (param,)).fetchone()["n"]


def _llm_count(connection):
    return connection.execute("SELECT count(*) AS n FROM ingest.llm_calls WHERE task = 'summary_oneliner'").fetchone()[
        "n"
    ]


def _llm_row(connection, created):
    return connection.execute(
        """
        SELECT task, status FROM ingest.llm_calls
        WHERE task = 'summary_oneliner' AND created_at = %s
        """,
        (created,),
    ).fetchone()


def _delete_llm(connection, created):
    connection.execute(
        "DELETE FROM ingest.llm_calls WHERE task = 'summary_oneliner' AND created_at = %s",
        (created,),
    )


def _at(day, hour, minute):
    return datetime.combine(day, time(hour, minute), tzinfo=NY)


def _midweek(start):
    day = start if trading_day(start) else next_trading_day(start)
    for _index in range(20):
        nxt = next_trading_day(day)
        same_week = nxt.isocalendar()[:2] == day.isocalendar()[:2]
        same_month = (nxt.year, nxt.month) == (day.year, day.month)
        if same_week and same_month:
            return day
        day = nxt
    raise AssertionError("no midweek session")


def _period_end(start, *, month):
    day = start if trading_day(start) else next_trading_day(start)
    for _index in range(40):
        nxt = next_trading_day(day)
        week_end = nxt.isocalendar()[:2] != day.isocalendar()[:2]
        month_end = (nxt.year, nxt.month) != (day.year, day.month)
        if month and month_end:
            return day
        if not month and week_end and not month_end:
            return day
        day = nxt
    raise AssertionError("no period end")
