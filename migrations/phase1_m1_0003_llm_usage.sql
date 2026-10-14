-- FR-M1-17: the shared client records attempts without storing text or secrets.
BEGIN;
CREATE TABLE IF NOT EXISTS ingest.llm_calls (
    call_id text PRIMARY KEY,
    task text NOT NULL,
    model text NOT NULL CHECK (model IN ('glm-5.3', 'deepseek-v4.1-flash')),
    purpose text NOT NULL,
    input_tokens bigint CHECK (input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    latency_ms double precision NOT NULL CHECK (latency_ms >= 0),
    status text NOT NULL CHECK (status IN ('ok', 'failed', 'usage_missing', 'failed_usage_missing')),
    info_ids text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS llm_calls_created_task ON ingest.llm_calls (created_at, task);
CREATE INDEX IF NOT EXISTS llm_calls_info_ids ON ingest.llm_calls USING gin (info_ids);
ALTER TABLE ingest.job_runs ADD COLUMN IF NOT EXISTS llm_input_tokens bigint;
ALTER TABLE ingest.job_runs ADD COLUMN IF NOT EXISTS llm_output_tokens bigint;
ALTER TABLE ingest.job_runs ADD COLUMN IF NOT EXISTS llm_usage_missing_calls integer;
COMMIT;
