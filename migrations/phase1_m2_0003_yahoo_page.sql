-- Q-M2-25: Yahoo's analysis page is the same estimates provider.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE fundamentals.consensus_snapshot DROP CONSTRAINT IF EXISTS consensus_snapshot_source_check;
ALTER TABLE fundamentals.consensus_snapshot ADD CONSTRAINT consensus_snapshot_source_check
  CHECK (source IN ('muse_import', 'yfinance', 'yahoo_page'));
COMMIT;
