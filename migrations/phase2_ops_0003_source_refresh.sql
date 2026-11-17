-- Daily bounded source refresh for recoverable backfill sources.
ALTER TABLE flows.cftc_positions ADD COLUMN IF NOT EXISTS fetched_at timestamptz DEFAULT now();

CREATE TABLE IF NOT EXISTS ops.data_guard_refresh (
  dataset text PRIMARY KEY,
  last_attempt_at timestamptz,
  last_result jsonb NOT NULL DEFAULT '{}'::jsonb
);
GRANT SELECT, INSERT, UPDATE ON ops.data_guard_refresh TO role_ingest;
GRANT SELECT ON ops.data_guard_refresh TO role_web;
