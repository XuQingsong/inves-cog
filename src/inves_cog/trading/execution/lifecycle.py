"""Explicit, guarded A019 reconciliation; never settle or rewrite historical trades."""

from inves_cog.trading.engine import ExecutionEngine
from inves_cog.trading.execution.repository import jsonb


def expire_legacy_orders(connection, *, clock, portfolio_id, obsolete_date, expected_stale=4, expected_orphan=4):
    """Expire the approved stale intents and DB-only orphans atomically, with exact-count guards.

    Call only after the terminal-state migration. Prices, cash, positions, fills, plan
    snapshots and ledger observation times are unchanged. Repeating a completed cleanup
    is read-only. New discrepancies fail closed instead of broadening the repair.
    """
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("A019:" + portfolio_id,))
        ledger = connection.execute(
            "SELECT * FROM trading.ledger WHERE portfolio_id=%s AND extractor='fixed' "
            "AND rule_set='A' AND params_version='p-2026.10' "
            "ORDER BY trade_date DESC,observed_at DESC LIMIT 1 FOR UPDATE",
            (portfolio_id,),
        ).fetchone()
        if ledger is None:
            raise ValueError("缺少活动账本，不执行清理")
        state = ledger["state"]
        active = {o["order_id"] for o in state.get("pending", [])}
        rows = connection.execute(
            "SELECT * FROM trading.orders WHERE portfolio_id=%s AND status='pending' "
            "AND rule_set='A' AND params_version='p-2026.10' FOR UPDATE",
            (portfolio_id,),
        ).fetchall()
        stale = [r for r in rows if r["order_id"] in active and r["trade_date"] == obsolete_date]
        orphans = [r for r in rows if r["order_id"] not in active]
        if not stale and not orphans:
            return {"status": "already_reconciled", "expired": 0}
        if len(stale) != expected_stale or len(orphans) != expected_orphan:
            raise ValueError("旧单或孤儿单计数变化，停止清理")
        engine = ExecutionEngine(clock=clock, portfolio_id=portfolio_id)
        engine.restore(state)
        for row in stale + orphans:
            reason = "过期未成交（计划延误）" if row in stale else "账本已移出、无终态"
            # Use stored immutable order identity/dates; never manufacture a new fill.
            order = {**row["intent"], "order_id": row["order_id"]}
            engine.record_terminal(order, "expired", reason)
        engine.persist_orders(connection, engine.terminal_orders)
        updated = {**state, "pending": engine.pending, "order_lifecycle": engine.order_lifecycle}
        connection.execute(
            "UPDATE trading.ledger SET state=%s WHERE portfolio_id=%s AND trade_date=%s "
            "AND phase=%s AND extractor='fixed' AND rule_set='A' AND params_version='p-2026.10'",
            (jsonb(updated), portfolio_id, ledger["trade_date"], ledger["phase"]),
        )
        return {
            "status": "reconciled",
            "expired": len(stale) + len(orphans),
            "stale": len(stale),
            "orphans": len(orphans),
        }
