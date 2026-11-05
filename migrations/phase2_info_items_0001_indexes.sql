-- follow-up bleed-stop for the 2026-11-05 I/O stall: info_items day-only and
-- pending-poll predicates seq-scanned the table (EXPLAIN-confirmed).
-- Plain CREATE INDEX IF NOT EXISTS — migrations may run in a transaction, so no
-- CONCURRENTLY; prod already carries both indexes built CONCURRENTLY.
CREATE INDEX IF NOT EXISTS info_items_first_seen_idx ON ingest.info_items (first_seen_at);
CREATE INDEX IF NOT EXISTS info_items_pending_idx ON ingest.info_items (first_seen_at) WHERE extraction_status='pending';
