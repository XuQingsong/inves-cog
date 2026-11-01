BEGIN;

ALTER TABLE flows.cftc_positions ADD COLUMN IF NOT EXISTS open_interest bigint;

COMMIT;
