-- bleed-stop for the 2026-11-05 I/O stall: day-only predicates on bars_daily
-- (cards.py _next_session/_prev_session, pages wide movers) seq-scanned the
-- whole 1.28M-row table. Plain CREATE INDEX IF NOT EXISTS — migrations may run
-- inside a transaction so CONCURRENTLY is unavailable; prod already carries
-- bars_daily_trade_date_idx built CONCURRENTLY and this is a no-op there.
CREATE INDEX IF NOT EXISTS bars_daily_trade_date_idx ON ingest.bars_daily (trade_date);
