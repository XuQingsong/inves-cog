-- B-032: record when an anomaly result became available. Old rows stay NULL.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

ALTER TABLE perception.anomalies
    ADD COLUMN IF NOT EXISTS generated_at timestamptz;

COMMIT;
