"""B-032: an anomaly is visible only after it was actually generated."""

from datetime import date, datetime

import pytest

from inves_cog.perception.anomaly.service import write_anomalies
from inves_cog.perception.attribution.morning import _load, main

MORNING = datetime.fromisoformat("2026-10-16T09:15:00+08:00")
DAY = "2026-10-15"
BEFORE = datetime.fromisoformat("2026-10-15T21:00:00+08:00")
AFTER = datetime.fromisoformat("2026-10-21T02:15:00+00:00")


class Quiet:
    def call(self, task, payload):
        return {"没有": True}


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


def _day(value):
    return str(value)[:10]


class Pages:
    def __init__(self, anomalies):
        self.anomalies = list(anomalies)
        self.calls = []
        self.jobs = []
        self.served = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        compact = " ".join(statement.split())
        if compact.startswith("INSERT INTO ingest.job_runs"):
            row = {"id": len(self.jobs) + 1}
            self.jobs.append(row)
            return Cursor([row])
        if compact.startswith("UPDATE ingest.job_runs"):
            return Cursor([])
        if "perception.anomalies" in compact:
            rows = [row for row in self.anomalies if _day(row["trade_date"]) == _day(params[0])]
            if "generated_at" in compact:
                moment = params[1]
                rows = [
                    row
                    for row in rows
                    if row.get("generated_at") is not None and row["generated_at"] <= moment
                ]
            rows.sort(key=lambda row: (row["session"], row["anomaly_id"]))
            self.served = [row["anomaly_id"] for row in rows]
            return Cursor(rows)
        if "ingest.info_items" in compact or "valuation_v1.ranges" in compact or "ingest.bars_daily" in compact:
            return Cursor([])
        if "trading.ledger" in compact or "trading.plan" in compact:
            return Cursor([])
        raise AssertionError(compact)


def _anomaly(name, generated_at):
    return {
        "anomaly_id": name,
        "trade_date": DAY,
        "session": "close",
        "direction": "down",
        "universe": "pool",
        "members": [{"ticker": "JNJ"}],
        "generated_at": generated_at,
    }


def write_row():
    return {
        "anomaly_id": "2026-01-27:close:001",
        "trade_date": date(2026, 1, 27),
        "session": "close",
        "entry_paths": ["B"],
        "layer": "L4",
        "severity": "watch",
        "baskets": [],
        "members": [],
        "direction": "down",
        "max_abs_z": 1.0,
        "data_quality": {},
        "coverage": {},
        "amplification": {},
        "type_candidates_prelim": [],
        "status": "已发现·原因未明",
        "universe": "pool",
        "params_version": "p-2026.10",
    }


class Inserts:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((" ".join(statement.split()), params))
        return Cursor([])


@pytest.mark.phase1_blocking
def test_generated_before_the_morning_is_visible():
    loaded = _load(Pages([_anomaly("early", BEFORE)]), MORNING, DAY)
    assert [row["anomaly_id"] for row in loaded["anomalies"]] == ["early"]


@pytest.mark.phase1_blocking
def test_generated_after_the_morning_stays_hidden():
    loaded = _load(Pages([_anomaly("early", BEFORE), _anomaly("late", AFTER)]), MORNING, DAY)
    assert [row["anomaly_id"] for row in loaded["anomalies"]] == ["early"]


@pytest.mark.phase1_blocking
def test_missing_generated_time_is_not_treated_as_known():
    loaded = _load(Pages([_anomaly("old", None), _anomaly("early", BEFORE)]), MORNING, DAY)
    assert [row["anomaly_id"] for row in loaded["anomalies"]] == ["early"]


@pytest.mark.phase1_blocking
def test_replay_at_an_old_morning_does_not_see_a_later_backfill():
    pages = Pages([_anomaly("backfill", AFTER), _anomaly("early", BEFORE)])
    code = main(["--at", MORNING.isoformat()], connection=pages, client=Quiet())
    assert code == 0
    query = next(params for statement, params in pages.calls if "perception.anomalies" in statement)
    assert query[0] == DAY
    assert query[1] == MORNING
    assert pages.served == ["early"]


@pytest.mark.phase1_blocking
def test_detection_write_uses_the_injected_clock():
    connection = Inserts()
    write_anomalies(connection, [write_row()], generated_at=AFTER)
    statement, params = connection.statements[0]
    assert "generated_at" in statement
    assert params[1] == date(2026, 1, 27)
    assert params[-1] == AFTER


class Split:
    def today_trade_date(self):
        return date(2026, 1, 27)

    def now_utc(self):
        return AFTER


class Runs:
    def __init__(self):
        self.job = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()

    def execute(self, statement, params=None):
        if "INSERT INTO ingest.job_runs" in statement:
            self.job = {"id": 7, "status": "failed"}
        if "UPDATE ingest.job_runs" in statement and params and "status = %s" in statement:
            self.job["status"] = params[1]
        return self

    def fetchone(self):
        return self.job


@pytest.mark.phase1_blocking
def test_detection_run_stamps_the_clock_not_the_old_trade_date(monkeypatch):
    from inves_cog.perception.anomaly import database
    from scripts import schedule_daily_modules as schedule

    captured = {}

    def capture(_connection, rows, *, generated_at):
        captured["generated_at"] = generated_at
        captured["ids"] = [row["anomaly_id"] for row in rows]
        return len(rows)

    class Panel:
        def detect(self, day, session):
            return [{"session": session, "entry_paths": ["B"], "data_quality": []}]

    monkeypatch.setattr(schedule, "connect", lambda _url: Runs())
    monkeypatch.setattr(database.DatabasePanel, "from_connection", lambda *args, **kwargs: Panel())
    monkeypatch.setattr("inves_cog.perception.anomaly.service.write_anomalies", capture)
    result = schedule.run_anomalies(clock=Split(), values={"INVES_COG_PERCEPTION_DATABASE_URL": "fixture"})
    assert result["status"] == "ok"
    assert captured["generated_at"] == AFTER
    assert captured["ids"] == ["2026-01-27:close:001", "2026-01-27:post:001"]
