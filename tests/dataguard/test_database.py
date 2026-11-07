from datetime import date, datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.dataguard.core import Finding
from inves_cog.dataguard.store import Store
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking


def test_one_row_per_gap_atomic_notice_idempotence_resolution_and_reopen():
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    day = date(2026, 11, 5)
    with psycopg.connect(
        host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", autocommit=True, row_factory=dict_row
    ) as c:
        try:
            c.execute("DELETE FROM ops.data_gaps WHERE dataset='TEST_guard'")
            c.execute("SET ROLE role_ingest")
            store = Store(c)
            finding = Finding("TEST_guard", day, "missing", {"impact": "测试"})
            for _ in range(2):
                with c.transaction():
                    rows, keys = store.reconcile("TEST_guard", day, [finding], now)
                    store.enqueue(keys, rows, now)
            assert c.execute("SELECT count(*) n FROM ops.data_gaps WHERE dataset='TEST_guard'").fetchone()["n"] == 1
            assert (
                c.execute("SELECT count(*) n FROM ops.data_gap_events WHERE dataset='TEST_guard'").fetchone()["n"] == 1
            )

            class Mailbox:
                configured = True

                def __init__(self):
                    self.messages = []

                def send(self, key, subject, body):
                    self.messages.append((key, body))
                    return "sent"

            mailbox = Mailbox()
            store.send_pending(mailbox, now)
            store.send_pending(mailbox, now)
            assert len(mailbox.messages) == 1
            rows, keys = store.reconcile("TEST_guard", day, [], now)
            assert rows[0]["status"] == "resolved"
            store.enqueue(keys, rows, now)
            store.send_pending(mailbox, now)
            assert len(mailbox.messages) == 2 and "已补齐" in mailbox.messages[-1][1]
            rows, keys = store.reconcile("TEST_guard", day, [finding], now)
            assert rows[0]["generation"] == 2
            c.execute("RESET ROLE")
            c.execute("SET ROLE role_web")
            assert (
                c.execute("SELECT status FROM ops.data_gaps WHERE dataset='TEST_guard'").fetchone()["status"] == "open"
            )
            assert not c.execute("SELECT has_table_privilege(current_user,'ops.data_gaps','UPDATE') ok").fetchone()[
                "ok"
            ]
            assert not c.execute("SELECT has_table_privilege(current_user,'ops.data_notices','SELECT') ok").fetchone()[
                "ok"
            ]
        finally:
            c.execute("RESET ROLE")
            c.execute("DELETE FROM ops.data_gaps WHERE dataset='TEST_guard'")
            c.execute("DELETE FROM ops.data_gap_events WHERE dataset='TEST_guard'")
            c.execute("DELETE FROM ops.data_notices WHERE body LIKE '%TEST_guard%'")


def test_revisions_keep_original_append_only_roles_and_actual_late_daily_inputs():
    from datetime import timedelta

    from inves_cog.dataguard.reader import barometer_drifts, load, read
    from inves_cog.dataguard.restatement import InputView, restate

    day = date(2026, 11, 5)
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    with (
        psycopg.connect(
            host=_disposable_database(),
            dbname="inves_cog",
            user="inves_cog_admin",
            autocommit=True,
            row_factory=dict_row,
        ) as c,
        c.transaction(force_rollback=True),
    ):
        c.execute("DELETE FROM ops.barometer_revisions WHERE data_date=%s", (day,))
        c.execute("DELETE FROM flows.barometer_daily WHERE date=%s", (day,))
        c.execute(
            "INSERT INTO flows.barometer_daily(date,asof,fear,greed,inputs,code_rev) "
            "VALUES (%s,%s,10,20,'{\"VIX\":16.61}','original')",
            (day, day),
        )
        c.execute("DELETE FROM ingest.macro_observations WHERE series_id='VIX_CBOE' AND observation_date=%s", (day,))
        c.execute(
            "INSERT INTO ingest.macro_observations(series_id,observation_date,value,realtime_start,fetched_at) "
            "VALUES ('VIX_CBOE',%s,28.18,%s,%s)",
            (day, day, now),
        )
        c.execute(
            "INSERT INTO flows.series_catalog(series_id,name_zh,unit,frequency,source) "
            "VALUES ('cboe_pc_TEST','测试','ratio','daily','fixture') ON CONFLICT DO NOTHING"
        )
        c.execute(
            "INSERT INTO flows.observations(series_id,obs_date,value,published_at,ingested_at,vintage) "
            "VALUES ('cboe_pc_TEST',%s,0.7,%s,%s,'backfill') ON CONFLICT DO NOTHING",
            (day, now, now),
        )
        c.execute("SET LOCAL ROLE role_ingest")
        view = InputView(c, day, now)
        rows = view.execute(
            "SELECT obs_date AS d,value,published_at AS p FROM flows.observations "
            "WHERE series_id=%s ORDER BY published_at",
            ("cboe_pc_TEST",),
        ).fetchall()
        assert len(rows) == 1 and rows[0]["p"].date() == day
        # Actual database visibility is retained; the source was not backdated.
        assert (
            c.execute("SELECT published_at FROM flows.observations WHERE series_id='cboe_pc_TEST'").fetchone()[
                "published_at"
            ]
            == now
        )
        record = dict(date=day, fear=42.0, greed=20.0, missing=[], inputs={"VIX": 28.18})

        def compute(*_):
            return [record]

        restate(c, day, now, compute=compute, code_rev="fixture")
        restate(c, day, now + timedelta(minutes=1), compute=compute, code_rev="fixture")
        assert (
            c.execute("SELECT count(*) n FROM ops.barometer_revisions WHERE data_date=%s", (day,)).fetchone()["n"] == 1
        )
        _, items = load("config/data_expectations.yaml")
        item = next(i for i in items if i.table == "flows.barometer_daily")
        assert read(c, item, day, day, now)[day][0]["value"] == "42.0"
        assert not barometer_drifts(c, item, day, day)
        assert c.execute("SELECT fear FROM flows.barometer_daily WHERE date=%s", (day,)).fetchone()["fear"] == 10
        c.execute("SET LOCAL ROLE role_web")
        assert (
            c.execute("SELECT revised_at FROM ops.barometer_revisions WHERE data_date=%s", (day,)).fetchone()[
                "revised_at"
            ]
            == now
        )
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            assert not c.execute(
                "SELECT has_table_privilege(current_user,'ops.barometer_revisions',%s) ok", (privilege,)
            ).fetchone()["ok"]
