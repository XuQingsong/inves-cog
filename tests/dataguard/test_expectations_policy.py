from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from inves_cog.dataguard.core import Expectation, Finding, due_dates, evaluate
from inves_cog.dataguard.reader import query
from inves_cog.dataguard.refresh import _fetch, _reopen, configured, window
from inves_cog.dataguard.service import retire_undue
from inves_cog.dataguard.store import Store
from inves_cog.dataguard.worker import degraded_keys

NOW = datetime(2026, 11, 12, 15, tzinfo=timezone.utc)


def _item(**overrides):
    values = {
        "dataset": "测试",
        "table": "flows.observations",
        "date_column": "obs_date",
        "cadence": "trading_day",
        "deadline_et": "09:00",
    }
    values.update(overrides)
    return Expectation(**values)


def test_us_federal_holiday_is_not_due():
    item = _item(holiday_calendar="us_federal")
    assert date(2026, 11, 11) not in due_dates(item, NOW, lookback=1)
    assert date(2026, 11, 10) in due_dates(item, NOW, lookback=2)


def test_active_since_and_rolling_recheck_bound_due_dates():
    item = _item(active_since="2026-11-10")
    assert date(2026, 11, 9) not in due_dates(item, NOW, lookback=3)
    rolling = _item(recheck_days=0)
    assert due_dates(rolling, NOW, lookback=7) == [date(2026, 11, 12)]


def test_ratio_and_score_metrics_skip_split_like_jump():
    item = _item(split_like=False, key_column="series_id", value_column="value")
    rows = [{"key": "cboe_pc_vix", "value": 0.42}]
    previous = [{"key": "cboe_pc_vix", "value": 0.87}]
    assert evaluate(item, date(2026, 11, 12), rows, previous) == []


def test_refresh_window_is_configured_and_fred_fetch_is_missing_only(monkeypatch):
    item = _item(
        table="flows.observations",
        filter={"series_id": ["fred_sofr"]},
        backfill={"entry": "fred", "refresh_days": 10},
    )
    assert configured(item) == 10
    days = window(item, NOW, configured(item))
    assert days[0] == date(2026, 11, 3) and days[-1] == date(2026, 11, 12) and len(days) == 10
    reader = MagicMock()
    reader.execute.return_value.fetchall.return_value = [{"series_id": "fred_sofr", "d": date(2026, 11, 10)}]
    calls = []

    def fake_fred(http, writer, raw, now, **kwargs):
        calls.append(kwargs)
        return [{"source": "FRED:SOFR", "rows": 0}]

    import inves_cog.dataguard.refresh as refresh

    monkeypatch.setattr(refresh.backfill, "backfill_fred", fake_fred)
    reports = _fetch(reader, MagicMock(), item, [date(2026, 11, 10)], {}, NOW, MagicMock())
    assert reports[0]["rows"] == 0
    assert calls[0]["sids"] == ["SOFR"]
    assert calls[0]["dates"] == {date(2026, 11, 10)}
    assert calls[0]["existing"] == {("fred_sofr", date(2026, 11, 10))}
    assert calls[0]["conflict"] == "nothing"


def test_macro_refresh_preserves_actual_fetch_timestamp(monkeypatch):
    import inves_cog.ingest.providers as providers

    fetched_at = datetime(2026, 11, 12, 14, 55, tzinfo=timezone.utc)
    row = {
        "series_id": "DGS10",
        "observation_date": date(2026, 11, 11),
        "value": 4.1,
        "realtime_start": date(2026, 11, 12),
        "fetched_at": fetched_at,
    }

    class FakeFred:
        def __init__(self, **kwargs):
            pass

        def collect(self, sid):
            return [row]

    written = []

    class FakeRepo:
        def __init__(self, connection):
            pass

        def write(self, table, value):
            written.append((table, value))

    writer = MagicMock()
    writer.execute.return_value.fetchall.return_value = []
    import inves_cog.dataguard.refresh as refresh

    monkeypatch.setattr(providers, "FRED", FakeFred)
    monkeypatch.setattr(refresh, "Repository", FakeRepo)
    item = _item(
        dataset="十年期国债收益率日线",
        table="ingest.macro_observations",
        filter={"series_id": ["DGS10"]},
        backfill={"entry": "fred"},
    )
    reports = _fetch(writer, writer, item, [date(2026, 11, 11)], {}, NOW, MagicMock())
    assert written == [("macro_observations", row)]
    assert written[0][1]["fetched_at"] == fetched_at
    assert reports[0]["rows"] == 1


def test_cboe_history_refresh_filters_existing_values(monkeypatch, tmp_path):
    from inves_cog.flows import backfill

    text = "DATE,VIX9D\n11/11/2026,15.5\n11/12/2026,15.7\n"
    http = MagicMock()
    http.request.return_value = text
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"raw_file_id": 1}
    captured = []
    monkeypatch.setattr(backfill, "upsert_many", lambda *args: captured.append(args))
    reports = backfill.backfill_cboe_index(
        http,
        conn,
        tmp_path,
        date(2026, 11, 12),
        NOW,
        dates={date(2026, 11, 11), date(2026, 11, 12)},
        existing={("cboe_idx_vix9d", date(2026, 11, 11))},
        conflict="nothing",
    )
    observations = next(args for args in captured if args[1] == "observations")
    assert [row["obs_date"] for row in observations[3]] == [date(2026, 11, 12)]
    assert observations[4] == "nothing"
    assert next(r for r in reports if r["source"] == "CboeIdx:VIX9D")["rows"] == 1


def test_refresh_reopens_unrecoverable_gap():
    row = {
        "dataset": "测试",
        "data_date": date(2026, 11, 10),
        "kind": "missing",
        "generation": 1,
        "detail": {},
        "status": "unrecoverable",
        "attempts": 3,
    }
    writer = MagicMock()
    writer.execute.return_value.fetchall.return_value = [row]
    assert _reopen(writer, _item(), [date(2026, 11, 10)], NOW) == 1
    assert row["status"] == "open" and row["attempts"] == 0 and row["resolved_at"] is None


def test_trends_rotation_expectation_counts_successful_keywords():
    item = _item(
        table="ingest.job_runs",
        key_column="task_name",
        value_column="status",
        success_column="processed_count",
        latest_column="started_at",
        filter={"task_name": ["trends"]},
        expected_keys=("trends",),
    )
    sql, args = query(item, date(2026, 11, 10), date(2026, 11, 12))
    assert "processed_count AS n" in sql
    row = {"key": "trends", "value": "degraded", "day": date(2026, 11, 12)}
    missing = evaluate(item, date(2026, 11, 12), [row], [], row_count=0)
    assert [f.kind for f in missing] == ["missing"]
    assert evaluate(item, date(2026, 11, 12), [row], [], row_count=3) == []


def test_disabled_upstream_source_retires_open_gap():
    item = _item(disabled={"reason": "上游停更"})
    row = {
        "dataset": "测试",
        "data_date": date(2026, 11, 9),
        "kind": "missing",
        "generation": 1,
        "detail": {},
        "status": "open",
        "attempts": 0,
    }
    writer = MagicMock()
    writer.execute.return_value.fetchall.return_value = [row]
    assert retire_undue(writer, item, NOW) == 1
    assert row["status"] == "resolved" and row["resolved_at"] == NOW


def test_config_marks_wrmfns_stopped_and_move_degraded():
    from inves_cog.dataguard.reader import load

    _, items = load("config/data_expectations.yaml")
    wrmfns = next(item for item in items if item.dataset == "货币基金规模")
    move = next(item for item in items if item.dataset == "利率信用与跨资产日线")
    assert wrmfns.disabled["reason"].startswith("FRED WRMFNS 上游停更")
    assert move.backfill["entry"] == "yahoo_px"
    assert move.backfill["degraded_http_statuses"] == [429]
    assert move.backfill["degraded_keys"] == ["yahoo_px_move"]


def test_yahoo_429_gap_is_recorded_degraded_and_not_reopened():
    item = SimpleNamespace(
        backfill={
            "degraded_keys": ["yahoo_px_move"],
            "degraded_http_statuses": [429],
        }
    )
    prev = {
        "dataset": "利率信用与跨资产日线",
        "data_date": date(2026, 11, 10),
        "kind": "missing",
        "generation": 1,
        "status": "unrecoverable",
        "attempts": 3,
        "detail": {"recovery_evidence": {"source_errors": [{"http_status": 429}]}},
    }
    assert degraded_keys(item, prev["detail"]["recovery_evidence"], ["yahoo_px_move"]) == {"yahoo_px_move"}
    store = Store(MagicMock())
    finding = Finding(prev["dataset"], prev["data_date"], "missing", {"missing_keys": ["yahoo_px_move"]})
    assert store._mark_degraded(item, prev, finding, NOW) is True
    assert prev["status"] == "resolved"
    assert prev["detail"]["degraded_keys"] == ["yahoo_px_move"]
