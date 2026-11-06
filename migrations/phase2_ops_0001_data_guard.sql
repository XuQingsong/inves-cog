-- A-032: isolated operational state; business readers retain their existing permissions.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE SCHEMA IF NOT EXISTS ops;
REVOKE ALL ON SCHEMA ops FROM PUBLIC;
GRANT USAGE ON SCHEMA ops TO role_ingest,role_web;
CREATE TABLE ops.data_gaps (
 dataset text NOT NULL, data_date date NOT NULL,
 kind text NOT NULL CHECK(kind IN ('missing','partial','stale','suspect','job_failed')),
 detail jsonb NOT NULL,
 first_detected_at timestamptz NOT NULL, last_checked_at timestamptz NOT NULL,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), last_attempt_at timestamptz,
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','backfilling','resolved','unrecoverable')),
 resolved_at timestamptz, generation integer NOT NULL DEFAULT 1,
 PRIMARY KEY(dataset,data_date,kind)
);
CREATE INDEX data_gaps_active_idx ON ops.data_gaps(last_checked_at) WHERE status<>'resolved';
CREATE INDEX data_gaps_resolved_idx ON ops.data_gaps(resolved_at) WHERE resolved_at IS NOT NULL;
CREATE TABLE ops.data_gap_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 dataset text NOT NULL, data_date date NOT NULL, kind text NOT NULL,
 generation integer NOT NULL, at timestamptz NOT NULL, status text NOT NULL, detail jsonb NOT NULL
);
CREATE INDEX data_gap_events_key_idx ON ops.data_gap_events(dataset,data_date,kind,at);
CREATE TABLE ops.data_notices (
 event_key text PRIMARY KEY, subject text NOT NULL, body text NOT NULL,
 created_at timestamptz NOT NULL, sent_at timestamptz,
 attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL,
 result text NOT NULL DEFAULT 'pending'
);
CREATE INDEX data_notices_pending_idx ON ops.data_notices(next_attempt_at) WHERE sent_at IS NULL;
CREATE TABLE ops.data_guard_runtime (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), first_started_at timestamptz NOT NULL, checked_at timestamptz NOT NULL,
 detect_only boolean NOT NULL, mail_status text NOT NULL, resource_status jsonb NOT NULL,
 complete_datasets integer NOT NULL, checked_datasets integer NOT NULL, duration_seconds double precision NOT NULL
);
REVOKE ALL ON ops.data_gaps,ops.data_gap_events,ops.data_notices,ops.data_guard_runtime FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON ops.data_gaps,ops.data_gap_events,ops.data_notices,ops.data_guard_runtime TO role_ingest;
GRANT USAGE,SELECT ON SEQUENCE ops.data_gap_events_id_seq TO role_ingest;
GRANT SELECT ON ops.data_gaps,ops.data_guard_runtime TO role_web;
CREATE INDEX IF NOT EXISTS info_items_first_seen_idx ON ingest.info_items(first_seen_at);
COMMIT;
