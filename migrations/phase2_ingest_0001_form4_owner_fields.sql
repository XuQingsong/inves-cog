BEGIN;

ALTER TABLE ingest.form4_events
    ADD COLUMN IF NOT EXISTS is_director boolean,
    ADD COLUMN IF NOT EXISTS officer_title text,
    ADD COLUMN IF NOT EXISTS is_ten_percent_owner boolean,
    ADD COLUMN IF NOT EXISTS aff10b5_one boolean,
    ADD COLUMN IF NOT EXISTS amount numeric;

COMMIT;
