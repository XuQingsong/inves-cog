BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.source_cursors (
 cursor_key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz NOT NULL
);
COMMIT;
