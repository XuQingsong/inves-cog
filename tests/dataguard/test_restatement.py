from datetime import date, datetime, timezone

import pytest

from inves_cog.dataguard.restatement import InputView, restate, verified

pytestmark = pytest.mark.phase1_blocking
DAY = date(2026, 11, 5)
NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self.calls = []
        self.saved = None

    def execute(self, sql, args=()):
        self.calls.append((sql, args))
        if "INSERT INTO ops.barometer_revisions" in sql:
            import json

            self.saved = dict(record=json.loads(args[3]), revised_at=args[1])
        if "SELECT record,revised_at FROM ops.barometer_revisions" in sql:
            return Result([self.saved])
        return Result()


def test_restatement_reads_are_bounded_and_late_daily_values_use_observation_day():
    db = DB()
    view = InputView(db, DAY, NOW)
    view.execute(
        "SELECT obs_date AS d, value, published_at AS p FROM flows.observations "
        "WHERE series_id=%s ORDER BY published_at",
        ("cboe_pc_equity",),
    )
    sql, args = db.calls[-1]
    assert "obs_date>=" in sql and "obs_date<=" in sql
    assert "ingested_at<=" in sql and "published_at<=" in sql
    assert "obs_date::timestamp" in sql and args[0] == "cboe_pc_equity"
    assert DAY in args and NOW in args
    view.execute("SELECT market, release_at AS p FROM flows.cftc_positions ORDER BY release_at")
    sql, args = db.calls[-1]
    assert "report_date<=" in sql and "release_at<=" in sql
    assert "report_date::timestamp" not in sql  # weekly publication semantics are preserved
    with pytest.raises(ValueError):
        view.execute("DELETE FROM flows.barometer_daily")


def test_append_only_restatement_preserves_original_and_uses_actual_revision_time():
    db = DB()
    record = dict(date=DAY, fear=42.0, greed=20.0, missing=[], inputs={"VIX": 28.18})
    got = restate(db, DAY, NOW, compute=lambda view, start, end: [record], code_rev="test")
    assert got["revised_at"] == NOW.isoformat() and got["record"]["asof"] == NOW.isoformat()
    assert got["record"]["date"] == str(DAY)
    assert got["input_hash"] and got["record"]["inputs"]["VIX"] == 28.18
    assert all("UPDATE flows." not in sql and "INSERT INTO flows." not in sql for sql, _ in db.calls)
    insert = next((sql, args) for sql, args in db.calls if "INSERT INTO ops.barometer_revisions" in sql)
    assert "DO NOTHING" in insert[0] and NOW in insert[1]
    assert verified(got)
    assert not verified({**got, "record": {**got["record"], "missing": ["债市信用"]}})
    assert not verified({**got, "record": {**got["record"], "fear": None}})
    with pytest.raises(ValueError):
        restate(db, DAY, datetime(2026, 11, 4, tzinfo=timezone.utc), compute=lambda *a: [record])


def test_page_discloses_original_and_revision_without_replacing_original():
    from inves_cog.web.data_status import revision_notice

    html = revision_notice([dict(data_date=DAY, revised_at=NOW, record={"fear": 42, "greed": 20, "missing": []})])
    assert "事后修订" in html and "原读数" in html and "2026-11-05" in html
    assert "42" in html and "20" in html and "2026-11-07" in html


def test_existing_calculator_runs_on_nonempty_restatement_view_without_future_rows():
    import pandas as pd

    from inves_cog.perception.barometer.compute import SPDR_FLOW
    from inves_cog.perception.barometer.loader import AI_CHAIN, BARS_ETFS, BARS_TICKERS, SECTORS

    days = pd.bdate_range(end=DAY, periods=390)

    class Market(DB):
        def execute(self, sql, args=()):
            self.calls.append((sql, args))
            if "INSERT INTO " in sql or "SELECT record,revised_at" in sql:
                return super().execute(sql, args)
            if "FROM ingest.bars_daily" in sql:
                return Result(
                    [
                        dict(ticker=t, d=d.date(), c=100 + n * 0.1)
                        for t in BARS_TICKERS + BARS_ETFS + SECTORS + AI_CHAIN
                        for n, d in enumerate(days)
                    ]
                )
            if "FROM flows.etf_daily" in sql:
                return Result(
                    [
                        dict(ticker=t, d=d.date(), aum=1e9 + n * 1e6, nav=100 + n * 0.1)
                        for t in set(SPDR_FLOW) | {"TQQQ", "UPRO", "QLD", "SSO", "USD", "SQQQ", "SPXU", "QID", "SDS"}
                        for n, d in enumerate(days)
                    ]
                )
            if "FROM flows.cftc_positions" in sql:
                return Result(
                    [
                        dict(
                            market="NASDAQ-100 Consolidated",
                            trader_class=t,
                            d=d.date(),
                            long=500,
                            short=100,
                            open_interest=1000,
                            p=d.tz_localize("UTC"),
                        )
                        for t in ("lev_money", "asset_mgr")
                        for d in days[::5]
                    ]
                )
            value = 28.18 if args[0] == "VIX_CBOE" else 0.7 if str(args[0]).startswith("cboe") else 100
            return Result([dict(d=d.date(), value=value, p=d.tz_localize(NY)) for d in days])

    from inves_cog.dataguard.calendar import NY

    result = restate(Market(), DAY, NOW)
    assert result["record"]["inputs"]["VIX"] == 28.18
    assert result["record"]["inputs"]["个股看跌看涨5日"] == 0.7
    assert isinstance(result["record"]["fear"], float)


def test_inputview_does_not_double_distinct_on_already_deduped_macro_query():
    """loader._series emits DISTINCT ON for macro_observations since #154;
    InputView must not prepend a second DISTINCT ON (syntax error)."""
    db = DB()
    view = InputView(db, DAY, NOW)
    view.execute(
        "SELECT DISTINCT ON (observation_date) observation_date AS d, value "
        "FROM ingest.macro_observations WHERE series_id=%s AND observation_date <= %s "
        "ORDER BY observation_date, fetched_at DESC, realtime_start DESC",
        ("CBBTCUSD",),
    )
    sql, _ = db.calls[-1]
    assert sql.count("DISTINCT ON") == 1
    assert "ORDER BY observation_date,fetched_at DESC,realtime_start DESC" in sql
