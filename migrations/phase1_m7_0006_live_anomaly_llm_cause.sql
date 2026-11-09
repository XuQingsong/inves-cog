-- Live anomalies: model-picked cause from ingested news when no rule link exists.
-- Existing table-level grants (role_perception RW, role_web R) cover the new columns.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE perception.live_anomalies
    ADD COLUMN IF NOT EXISTS cause_source text CHECK (cause_source IN ('rule','llm')),
    ADD COLUMN IF NOT EXISTS cause_reason text,
    ADD COLUMN IF NOT EXISTS cause_confidence text CHECK (cause_confidence IN ('high','medium','low')),
    ADD COLUMN IF NOT EXISTS cause_timing text
        CHECK (cause_timing IN ('news_before_move','move_before_news','unclear')),
    ADD COLUMN IF NOT EXISTS cause_info_ids text[],
    ADD COLUMN IF NOT EXISTS llm_attempts integer NOT NULL DEFAULT 0 CHECK (llm_attempts >= 0),
    ADD COLUMN IF NOT EXISTS llm_last_at timestamptz,
    ADD COLUMN IF NOT EXISTS llm_last_major boolean NOT NULL DEFAULT false;
UPDATE perception.live_anomalies SET cause_source='rule' WHERE cause_event_id IS NOT NULL AND cause_source IS NULL;
GRANT SELECT, INSERT, UPDATE, DELETE ON perception.live_anomalies TO role_perception;
GRANT SELECT ON perception.live_anomalies TO role_web;
COMMIT;
