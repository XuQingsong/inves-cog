-- User explicitly approved six alternative models on 2026-10-15.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE ingest.llm_calls DROP CONSTRAINT IF EXISTS llm_calls_model_check;
ALTER TABLE ingest.llm_calls ADD CONSTRAINT llm_calls_model_check CHECK (
  (task = 'embedding' AND model IN (
    'text-embedding-v1', 'text-embedding-v2', 'text-embedding-v3', 'text-embedding-v4',
    'qwen3.7-text-embedding-flash', 'text-embedding-async-v1', 'text-embedding-async-v2'
  )) OR (task <> 'embedding' AND model IN ('glm-5.3', 'deepseek-v4.1-flash'))
);
CREATE TABLE IF NOT EXISTS ingest.info_embeddings (
    info_id text NOT NULL REFERENCES ingest.info_items(info_id),
    model text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions > 0),
    input_sha256 text NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (info_id, model, input_sha256),
    CHECK (vector_dims(embedding) = dimensions)
);
CREATE INDEX IF NOT EXISTS info_embeddings_model ON ingest.info_embeddings(model, info_id);
COMMIT;
