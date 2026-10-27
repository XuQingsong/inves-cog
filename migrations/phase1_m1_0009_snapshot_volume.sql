-- B-068: cumulative daily volume on delayed SIP snapshots.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE ingest.intraday_snapshots ADD COLUMN day_volume bigint;
COMMIT;
