-- Explicit 2026-10-15 requirements: durable starts and separate embedding usage.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE ingest.job_runs DROP CONSTRAINT IF EXISTS job_runs_status_check;
ALTER TABLE ingest.job_runs ADD CONSTRAINT job_runs_status_check
  CHECK (status IN ('running', 'ok', 'degraded', 'failed'));
ALTER TABLE ingest.llm_calls DROP CONSTRAINT IF EXISTS llm_calls_model_check;
ALTER TABLE ingest.llm_calls ADD CONSTRAINT llm_calls_model_check CHECK (
  (task = 'embedding' AND model = 'text-embedding-v3') OR
  (task <> 'embedding' AND model IN ('glm-5.3', 'deepseek-v4.1-flash'))
);
ALTER TABLE ingest.llm_calls ADD COLUMN IF NOT EXISTS item_count integer CHECK (item_count >= 0);
COMMIT;
