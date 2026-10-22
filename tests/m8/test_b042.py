"""B-042: inputs and jobs stay on the ingest login; M8 writes use role_perception."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from inves_cog.clock import FrozenClock
from inves_cog.perception.attribution.morning import main as morning_main
from inves_cog.perception.attribution.replay_window import main as replay_main
from inves_cog.perception.attribution.replay_window import replay_window, slot_moment
from inves_cog.perception.attribution.scheduled import main as stage_main
from inves_cog.perception.attribution.snapshot import m8_provider, read_replay_snapshot
from tests.m8.test_b041_contract import (
    DAY,
    TOSHIBA_START,
    Fixture,
    _assert_contract_events,
    _clear,
    _contract,
    _db_anomaly,
    _fixture,
    _pool,
)

pytestmark = pytest.mark.phase1_blocking

REAL = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)
_TASKS = ("attribution_candidates", "attribution_tracks", "attribution_labels")
_LIVE = ("linkage_events", "ticker_status", "candidates", "tracks", "claims", "reports", "market_day")


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Attach:
    """Keep the real login, and put the fixture fields back on each anomaly row."""

    def __init__(self, inner, extras):
        self.inner = inner
        self.extras = extras
        self.statements = []

    def execute(self, statement, params=None):
        compact = " ".join(statement.split())
        self.statements.append(compact)
        cursor = self.inner.execute(statement, params)
        if "FROM perception.anomalies" not in compact or compact.upper().startswith("INSERT"):
            return cursor
        rows = []
        for row in cursor.fetchall():
            prepared = dict(row)
            extra = self.extras.get(prepared.get("anomaly_id"))
            if extra:
                prepared.update(extra)
            rows.append(prepared)
        return _Cursor(rows)

    def close(self):
        return None


class _Trace:
    def __init__(self, inner):
        self.inner = inner
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append(" ".join(statement.split()))
        return self.inner.execute(statement, params)

    def close(self):
        return None


class _Counted:
    def __init__(self, inner, record):
        self.inner = inner
        self.record = record
        self.tasks = []

    def call(self, task, payload):
        output = self.inner.call(task, payload)
        self.tasks.append(task)
        self.record(task)
        return output


class _Boom:
    def call(self, task, payload):
        raise AssertionError(task)


def test_w5_replay_cli_requires_a_mode():
    with pytest.raises(SystemExit, match="需要 --dry-run 或 --execute"):
        replay_main([])


def test_w6_env_example_names_the_variable_without_a_value():
    text = Path(".env.example").read_text(encoding="utf-8")
    line = next(item for item in text.splitlines() if "INVES_COG_PERCEPTION_DATABASE_URL" in item)
    assert line == "INVES_COG_PERCEPTION_DATABASE_URL="
    assert not list(Path("migrations").glob("*b042*"))


def test_w1_two_accounts_run_the_contract_on_disposable_database(tmp_path):
    host, ingest, perception, admin = _open()
    anomalies, items = _fixture()
    try:
        _seed(admin, anomalies, items)
        _assert_matrix(ingest, perception)
        client = _Counted(Fixture(), lambda task: _record_call(ingest, task))
        wrapped = _Attach(ingest, _extras(anomalies))
        morning = slot_moment(DAY, "attribution_candidates")
        tracks = slot_moment(DAY, "attribution_tracks")
        labels = slot_moment(DAY, "attribution_labels")
        assert _run_morning(wrapped, perception, morning, client, tmp_path) == 0
        assert (tmp_path / f"daily_page_{DAY}.txt").exists()
        assert _run_stage("attribution_tracks", wrapped, perception, tracks, client) == 0
        assert _run_stage("attribution_labels", wrapped, perception, labels, client) == 0
        assert _job_status(ingest) >= {
            ("attribution_candidates", "ok"),
            ("attribution_tracks", "ok"),
            ("attribution_labels", "ok"),
        }
        assert perception.execute("SELECT count(*) AS n FROM perception.reports").fetchone()["n"] > 0
        assert perception.execute("SELECT count(*) AS n FROM perception.m9_input_snapshots").fetchone()["n"] > 0
        found = m8_provider(perception)(DAY, _contract()["cutoff"])
        assert "evt-future" not in {row["event_id"] for row in found["events"]}
        _assert_contract_events(found, {"toshiba": "假设中", "expired": "假设中"})
        recorded = admin.execute("SELECT count(*) AS n FROM ingest.llm_calls WHERE purpose = 'b042'").fetchone()["n"]
        assert recorded == len(client.tasks)
        assert client.tasks
        _perception_cannot_write_calls(perception)
    finally:
        _cleanup(admin, anomalies, items)
        _close(ingest, perception, admin)


def test_w3_missing_perception_url_fails_before_the_model_on_disposable_database(tmp_path, monkeypatch):
    host, ingest, perception, admin = _open()
    try:
        monkeypatch.setenv("INVES_COG_DATABASE_URL", _dsn(host, "b042_ingest"))
        monkeypatch.delenv("INVES_COG_PERCEPTION_DATABASE_URL", raising=False)
        monkeypatch.setenv("INVES_COG_PAGE_DIR", str(tmp_path))
        client = _Counted(Fixture(), lambda task: None)
        assert morning_main([], clock=FrozenClock(slot_moment(DAY, "attribution_candidates")), client=client) == 1
        assert client.tasks == []
        assert not list(tmp_path.glob("daily_page_*.txt"))
        job = _latest_job(ingest, "attribution_candidates")
        assert job["status"] == "failed"
        assert "INVES_COG_PERCEPTION_DATABASE_URL" in job["error_summary"]
    finally:
        _cleanup(admin, [], [])
        _close(ingest, perception, admin)


def test_w4_ingest_writer_is_rejected_before_the_model_on_disposable_database(monkeypatch):
    host, ingest, perception, admin = _open()
    try:
        monkeypatch.setenv("INVES_COG_DATABASE_URL", _dsn(host, "b042_ingest"))
        monkeypatch.setenv("INVES_COG_PERCEPTION_DATABASE_URL", _dsn(host, "b042_ingest"))
        client = _Counted(Fixture(), lambda task: None)
        assert morning_main([], clock=FrozenClock(slot_moment(DAY, "attribution_candidates")), client=client) == 1
        assert client.tasks == []
        job = _latest_job(ingest, "attribution_candidates")
        assert job["status"] == "failed"
        assert "没有写入权限" in job["error_summary"]
    finally:
        _cleanup(admin, [], [])
        _close(ingest, perception, admin)


def test_w5_replay_cli_on_disposable_database(capsys):
    host, ingest, perception, admin = _open()
    anomalies, items = _fixture()
    try:
        _seed(admin, anomalies, items)
        wrapped = _Attach(ingest, _extras(anomalies))
        assert (
            replay_main(
                ["--dry-run", "--days", DAY],
                connection=wrapped,
                perception=perception,
                clock=FrozenClock(REAL),
                client=_Boom(),
            )
            == 0
        )
        printed = json.loads(capsys.readouterr().out)
        expected = replay_window(None, FrozenClock(REAL), anomalies=anomalies, items=items, days=(DAY,), dry_run=True)
        assert [stage["calls"] for stage in printed["days"][0]["stages"]] == [
            stage["calls"] for stage in expected["days"][0]["stages"]
        ]
        assert printed["calls"] == []
        assert not any(item.upper().startswith("INSERT") for item in wrapped.statements)
        traced = _Trace(perception)
        assert (
            replay_main(
                ["--execute", "--days", DAY],
                connection=wrapped,
                perception=traced,
                clock=FrozenClock(REAL),
                client=Fixture(),
            )
            == 0
        )
        executed = json.loads(capsys.readouterr().out)
        text = " ".join(traced.statements)
        for name in _LIVE:
            assert name not in text
        snapshot_id = executed["days"][0]["snapshot_id"]
        assert snapshot_id
        row = admin.execute(
            "SELECT kind, snapshot_generated_at FROM perception.m9_input_snapshots WHERE snapshot_id = %s",
            (snapshot_id,),
        ).fetchone()
        assert row["kind"] == "historical_backfill"
        assert row["snapshot_generated_at"] == REAL
        assert read_replay_snapshot(perception, DAY)["replay"] is True
        visible = admin.execute(
            "SELECT snapshot_id FROM perception.m9_input_snapshots "
            "WHERE snapshot_id = %s AND snapshot_generated_at <= %s",
            (snapshot_id, slot_moment(DAY, "attribution_labels")),
        ).fetchone()
        assert visible is None
    finally:
        _cleanup(admin, anomalies, items)
        _close(ingest, perception, admin)


def _run_morning(connection, perception, moment, client, folder):
    import os

    os.environ["INVES_COG_PAGE_DIR"] = str(folder)
    try:
        return morning_main([], connection=connection, perception=perception, clock=FrozenClock(moment), client=client)
    finally:
        os.environ.pop("INVES_COG_PAGE_DIR", None)


def _run_stage(task_name, connection, perception, moment, client):
    return stage_main(
        ["--task", task_name],
        connection=connection,
        perception=perception,
        clock=FrozenClock(moment),
        client=client,
    )


def _job_status(connection):
    rows = connection.execute(
        "SELECT task_name, status FROM ingest.job_runs WHERE trade_date = %s AND task_name = ANY(%s)",
        (DAY, list(_TASKS)),
    ).fetchall()
    return {(row["task_name"], row["status"]) for row in rows}


def _latest_job(connection, task_name):
    return connection.execute(
        "SELECT status, error_summary FROM ingest.job_runs "
        "WHERE trade_date = %s AND task_name = %s ORDER BY id DESC LIMIT 1",
        (DAY, task_name),
    ).fetchone()


def _perception_cannot_write_calls(connection):
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        connection.execute(
            "INSERT INTO ingest.llm_calls "
            "(call_id, task, model, purpose, latency_ms, status, info_ids, created_at) "
            "VALUES (%s, 'move_card', 'deepseek-v4.1-flash', 'b042', 0, 'usage_missing', '{}', %s)",
            (uuid.uuid4().hex, REAL),
        )


def _record_call(connection, task):
    connection.execute(
        "INSERT INTO ingest.llm_calls "
        "(call_id, task, model, purpose, latency_ms, status, info_ids, created_at) "
        "VALUES (%s, %s, 'deepseek-v4.1-flash', 'b042', 0, 'usage_missing', '{}', %s)",
        (uuid.uuid4().hex, task, datetime.now(timezone.utc)),
    )


def _extras(anomalies):
    kept = {}
    for row in anomalies:
        extra = {"relations": row.get("relations") or [], "started_at": row.get("started_at")}
        if row.get("deadline_on"):
            extra["deadline_on"] = row["deadline_on"]
        kept[row["anomaly_id"]] = extra
    return kept


def _open():
    import psycopg
    from psycopg.rows import dict_row

    from tests.m8.test_attribution import _disposable_database

    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    _roles(admin)
    ingest = psycopg.connect(_dsn(host, "b042_ingest"), row_factory=dict_row, autocommit=True)
    perception = psycopg.connect(_dsn(host, "b042_perception"), row_factory=dict_row, autocommit=True)
    return host, ingest, perception, admin


def _dsn(host, user):
    return f"postgresql://{user}@{host}/inves_cog"


def _roles(admin):
    admin.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b042_ingest') THEN "
        "CREATE ROLE b042_ingest LOGIN INHERIT; END IF; "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'b042_perception') THEN "
        "CREATE ROLE b042_perception LOGIN INHERIT; END IF; END $$"
    )
    admin.execute("GRANT role_ingest TO b042_ingest")
    admin.execute("GRANT role_perception TO b042_perception")
    admin.execute("GRANT USAGE ON SCHEMA perception, valuation_v1, trading TO b042_ingest")
    admin.execute("GRANT SELECT ON perception.anomalies TO b042_ingest")
    admin.execute("GRANT SELECT ON valuation_v1.ranges TO b042_ingest")
    admin.execute("GRANT SELECT ON trading.plan, trading.ledger TO b042_ingest")


def _assert_matrix(ingest, perception):
    assert _allowed(ingest, "perception.anomalies", "SELECT")
    assert not _allowed(ingest, "perception.reports", "INSERT")
    assert not _allowed(ingest, "perception.m9_input_snapshots", "INSERT")
    assert _allowed(ingest, "ingest.llm_calls", "INSERT")
    assert _allowed(ingest, "valuation_v1.ranges", "SELECT")
    assert _allowed(perception, "perception.reports", "INSERT")
    assert _allowed(perception, "perception.m9_input_snapshots", "INSERT")
    assert not _allowed(perception, "valuation_v1.ranges", "SELECT")
    assert not _allowed(perception, "ingest.llm_calls", "INSERT")


def _allowed(connection, table, privilege):
    row = connection.execute(
        "SELECT has_table_privilege(current_user, %s, %s) AS allowed",
        (table, privilege),
    ).fetchone()
    return row["allowed"]


def _seed(admin, anomalies, items):
    from inves_cog.perception.anomaly.service import write_anomalies

    labels = slot_moment(DAY, "attribution_labels")
    future = _pool(
        "future",
        ["NVDA"],
        [{"ticker": "NVDA", "exposure": "直接", "status": "观察到"}],
        TOSHIBA_START,
        "2026-11-06",
    )
    ids = [row["anomaly_id"] for row in anomalies] + [future["anomaly_id"]]
    admin.execute("DELETE FROM perception.claims WHERE anomaly_id = ANY(%s)", (ids,))
    _clear(admin, ids)
    admin.execute("DELETE FROM perception.market_day WHERE trade_date = %s", (DAY,))
    write_anomalies(admin, [_db_anomaly(row) for row in anomalies], generated_at=TOSHIBA_START)
    write_anomalies(admin, [_db_anomaly(future)], generated_at=labels + timedelta(hours=2))
    for item in items:
        _insert_news(admin, item)


def _insert_news(connection, item):
    connection.execute(
        "INSERT INTO ingest.info_items ("
        "info_id, kind, published_at, first_seen_at, source, source_level, headline, "
        "tickers, entities, extraction_status, flags, payload, extraction_source"
        ") VALUES (%s, %s, %s, %s, 'fixture', 1, %s, %s, '{}', 'ok', '{}', '{}', %s) "
        "ON CONFLICT (info_id) DO NOTHING",
        (
            item["info_id"],
            item["kind"],
            item["published_at"],
            item["first_seen_at"],
            item["headline"],
            item["tickers"],
            json.dumps(item["extraction_source"]),
        ),
    )


def _cleanup(admin, anomalies, items):
    ids = [row["anomaly_id"] for row in anomalies] + ["future"]
    admin.execute("DELETE FROM perception.claims WHERE anomaly_id = ANY(%s)", (ids,))
    _clear(admin, ids)
    admin.execute("DELETE FROM perception.market_day WHERE trade_date = %s", (DAY,))
    info_ids = [item["info_id"] for item in items]
    if info_ids:
        admin.execute("DELETE FROM ingest.info_items WHERE info_id = ANY(%s)", (info_ids,))
    admin.execute("DELETE FROM ingest.llm_calls WHERE purpose = 'b042'")
    admin.execute(
        "DELETE FROM ingest.job_runs WHERE trade_date = %s AND params_version = 'p-2026.10' AND task_name = ANY(%s)",
        (DAY, list(_TASKS)),
    )


def _close(ingest, perception, admin):
    ingest.close()
    perception.close()
    admin.close()
