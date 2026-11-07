"""Expectation coverage follows the current barometer sources (bars_daily +
DGS10) and the providers.FRED recovery path."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from inves_cog.dataguard import worker
from inves_cog.dataguard.reader import load

pytestmark = pytest.mark.phase1_blocking
NOW = datetime(2026, 11, 6, 22, tzinfo=timezone.utc)
DAY = date(2026, 11, 5)


def _items():
    _, items = load("config/data_expectations.yaml")
    return {item.dataset: item for item in items}


def test_cross_asset_daily_only_expects_remaining_yahoo_series():
    item = _items()["利率信用与跨资产日线"]
    keys = set(item.filter["series_id"])
    assert keys == {"yahoo_px_jpyx", "yahoo_px_btcusd", "yahoo_px_move"}
    dropped = {
        "yahoo_px_tqqq",
        "yahoo_px_soxl",
        "yahoo_px_gld",
        "yahoo_px_hyg",
        "yahoo_px_ief",
        "yahoo_px_tlt",
        "yahoo_px_tnx",
    }
    assert not keys & dropped


def test_index_etf_daily_covers_barometer_etfs():
    item = _items()["指数与半导体基金日线"]
    assert {"TQQQ", "SOXL", "GLD", "HYG", "IEF", "TLT"} <= set(item.filter["ticker"])


def test_dgs10_expected_with_fred_recovery():
    item = _items()["十年期国债收益率日线"]
    assert item.table == "ingest.macro_observations"
    assert item.backfill["entry"] == "fred"
    assert item.filter["series_id"] == ["DGS10"]


def test_intraday_snapshots_never_auto_backfilled():
    assert _items()["宽池盘中快照"].backfill["entry"] == "manual"
    assert _items()["监控池盘中快照"].backfill["entry"] == "manual"


def test_short_volume_has_finra_collector_entry():
    assert _items()["空头成交量"].backfill["entry"] == "finra_short"


def _stub_conn(monkeypatch):
    db = MagicMock()
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=db)
    conn.__exit__ = MagicMock(return_value=None)
    monkeypatch.setattr(worker, "connect", lambda values, writer=False: conn)
    return db


def _fred_item(table, keys):
    return SimpleNamespace(
        dataset="测试",
        table=table,
        filter={"series_id": keys},
        backfill={"entry": "fred"},
    )


def test_fred_recovery_uses_provider_for_flows_series(monkeypatch):
    from inves_cog.ingest import providers

    class FakeFred:
        def __init__(self, **kwargs):
            assert kwargs["key"] == "key1"

        def collect(self, sid):
            assert sid == "SOFR"
            return [
                {"observation_date": DAY, "value": 4.28},
                {"observation_date": date(2026, 11, 4), "value": 4.3},
            ]

    db = _stub_conn(monkeypatch)
    monkeypatch.setattr(providers, "FRED", FakeFred)
    evidence = {}
    item = _fred_item("flows.observations", ["fred_sofr"])
    assert worker.recover(item, DAY, NOW, {"FRED_API_KEY": "key1"}, evidence=evidence) is True
    executemany = db.cursor.return_value.__enter__.return_value.executemany
    sql, values = executemany.call_args.args
    assert "INSERT INTO flows.observations" in sql
    rows = [dict(zip(sql.split("(")[1].split(")")[0].split(","), v, strict=True)) for v in values]
    assert [r["series_id"] for r in rows] == ["fred_sofr"]
    assert all(r["obs_date"] == DAY for r in rows)  # receipt bounds to the gap day
    assert evidence["candidate_rows"] == 1


def test_fred_recovery_writes_macro_series_directly(monkeypatch):
    from inves_cog.ingest import providers, repository

    class FakeFred:
        def __init__(self, **kwargs):
            pass

        def collect(self, sid):
            assert sid == "DGS10"
            return [
                {"observation_date": DAY, "value": 4.85},
                {"observation_date": date(2026, 11, 4), "value": 4.9},
            ]

    written = []

    class FakeRepo:
        def __init__(self, connection):
            pass

        def write(self, table, row):
            written.append((table, row))

    _stub_conn(monkeypatch)
    monkeypatch.setattr(providers, "FRED", FakeFred)
    monkeypatch.setattr(repository, "Repository", FakeRepo)
    evidence = {}
    assert worker.recover(_fred_item("ingest.macro_observations", ["DGS10"]), DAY, NOW, {}, evidence=evidence) is True
    assert written == [("macro_observations", {"observation_date": DAY, "value": 4.85})]
    assert evidence["candidate_rows"] == 1
