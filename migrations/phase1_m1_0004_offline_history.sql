BEGIN;
-- Offline R7 source evidence; unknown visibility never enters PIT observations.
CREATE TABLE IF NOT EXISTS ingest.offline_history (
 source_table text NOT NULL CHECK (source_table IN ('data.insider_transactions','data.vix_daily')),
 record_id text NOT NULL, raw jsonb NOT NULL, file_sha256 text NOT NULL,
 imported_at timestamptz NOT NULL, gaps text[] NOT NULL,
 PRIMARY KEY (source_table,record_id)
);
COMMIT;
