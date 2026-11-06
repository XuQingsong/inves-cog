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
