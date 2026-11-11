BEGIN;
SET LOCAL ROLE inves_cog_admin;

ALTER TABLE perception.anomalies ADD COLUMN IF NOT EXISTS precursor jsonb;

COMMIT;
