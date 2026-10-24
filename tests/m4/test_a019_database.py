"""A019 cleanup against the disposable database; no production connection is used."""

from datetime import date, datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.clock import FrozenClock
from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.lifecycle import expire_legacy_orders
from inves_cog.trading.execution.repository import jsonb
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking
CLOCK = FrozenClock(datetime(2026, 10, 24, 6, tzinfo=timezone.utc))
PORTFOLIO = "a019-disposable-fixture"
OLD = date(2026, 10, 19)


@pytest.fixture
def database():
    c = psycopg.connect(host=_disposable_database(), dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row)
    e = ExecutionEngine(clock=CLOCK, portfolio_id=PORTFOLIO)
    e.signal_date = date(2026, 10, 16)
    for i in range(4):
        e.queue("STALE" + str(i), "buy_to", "M-35", "首笔买入", tier="normal", fraction=0.5)
    e.signal_date = date(2026, 10, 21)
    e.queue("ACTIVE", "buy_to", "M-35", "首笔买入", tier="normal", fraction=0.5)
    pending = list(e.pending)
    for i in range(4):
        e.queue("ORPHAN" + str(i), "buy_to", "M-35", "首笔买入", tier="normal", fraction=0.5)
    e.persist_orders(c, e.pending)
    e.pending = pending
    c.execute(
        "INSERT INTO trading.ledger (portfolio_id,trade_date,phase,extractor,rule_set,params_version,"
        "cash,equity,peak_equity,state,observed_at) VALUES (%s,'2026-10-22','plan','fixed','A',"
        "'p-2026.10',100000,100000,100000,%s,%s)",
        (PORTFOLIO, jsonb(e.snapshot()), CLOCK.now_utc()),
    )
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def test_p3_eight_expired_preserve_cash_positions_observed_at_and_plans(database):
    before = database.execute("SELECT * FROM trading.ledger WHERE portfolio_id=%s", (PORTFOLIO,)).fetchone()
    result = expire_legacy_orders(database, clock=CLOCK, portfolio_id=PORTFOLIO, obsolete_date=OLD)
    assert result == {"status": "reconciled", "expired": 8, "stale": 4, "orphans": 4}
    rows = database.execute(
        "SELECT status,reason_zh FROM trading.orders WHERE portfolio_id=%s", (PORTFOLIO,)
    ).fetchall()
    assert sum(r["status"] == "expired" for r in rows) == 8
    assert sum("计划延误" in r["reason_zh"] for r in rows) == 4
    assert sum("账本已移出" in r["reason_zh"] for r in rows) == 4
    after = database.execute("SELECT * FROM trading.ledger WHERE portfolio_id=%s", (PORTFOLIO,)).fetchone()
    assert len(after["state"]["pending"]) == 1
    for field in before:
        if field != "state":
            assert after[field] == before[field]
    for field in before["state"]:
        if field not in {"pending", "order_lifecycle"}:
            assert after["state"][field] == before["state"][field]
    assert expire_legacy_orders(database, clock=CLOCK, portfolio_id=PORTFOLIO, obsolete_date=OLD) == {
        "status": "already_reconciled",
        "expired": 0,
    }


def test_p3_changed_counts_fail_without_mutating_any_pending_order(database):
    with pytest.raises(ValueError, match="计数变化"):
        expire_legacy_orders(database, clock=CLOCK, portfolio_id=PORTFOLIO, obsolete_date=OLD, expected_stale=5)
    rows = database.execute("SELECT status FROM trading.orders WHERE portfolio_id=%s", (PORTFOLIO,)).fetchall()
    assert len(rows) == 9 and all(r["status"] == "pending" for r in rows)
