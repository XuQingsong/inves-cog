-- Shared M1/M2 operational tables. Admin ownership inherits the M0 role matrix.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.job_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_name text NOT NULL,
    trade_date date NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    status text NOT NULL CHECK (status IN ('ok', 'degraded', 'failed')),
    processed_count integer NOT NULL CHECK (processed_count >= 0),
    error_summary text,
    params_version text NOT NULL,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS job_runs_trade_task ON ingest.job_runs (trade_date, task_name);
CREATE TABLE IF NOT EXISTS ingest.source_health (
    source text PRIMARY KEY,
    last_success_at timestamptz,
    last_attempt_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('ok', 'degraded', 'unavailable', '未接通')),
    latency_sec double precision CHECK (latency_sec >= 0),
    items_last_run integer NOT NULL CHECK (items_last_run >= 0),
    note text,
    consecutive_failures integer NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0)
);
COMMIT;
