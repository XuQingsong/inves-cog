-- Collection-task coverage audit + health table (2026-11-10).
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE ops.data_gaps DROP CONSTRAINT data_gaps_kind_check;
ALTER TABLE ops.data_gaps ADD CONSTRAINT data_gaps_kind_check CHECK(
 kind IN ('missing','partial','stale','suspect','job_failed','uncovered','degraded','empty_run','consec_failed'));
CREATE TABLE IF NOT EXISTS ops.collection_health (
 task_name text PRIMARY KEY,
 display_name text, source text, cadence text,
 last_ok_at timestamptz, last_run_at timestamptz, last_status text,
 fail_streak integer NOT NULL DEFAULT 0, degraded_streak integer NOT NULL DEFAULT 0,
 state text NOT NULL DEFAULT 'ok',
 note text, updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON ops.collection_health TO role_web;
COMMIT;
