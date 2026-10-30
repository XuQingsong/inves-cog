-- B-069: rule-based news event layer (no LLM). Read-only on ingest.info_items.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE perception.news_events (
    event_id text PRIMARY KEY,
    subject text NOT NULL,
    kind text NOT NULL,
    et_date date NOT NULL,
    session text NOT NULL CHECK (session IN ('pre','regular','post','overnight')),
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    info_ids text[] NOT NULL,
    headline text,
    facts jsonb,
    segment text,
    importance smallint NOT NULL,
    importance_parts jsonb NOT NULL,
    reaction jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX news_events_et_date ON perception.news_events (et_date);
CREATE INDEX news_events_subject ON perception.news_events (subject, et_date);
GRANT SELECT ON ingest.info_items TO role_perception;
GRANT SELECT, INSERT, UPDATE, DELETE ON perception.news_events TO role_perception;
GRANT SELECT ON perception.news_events TO role_web;
COMMIT;
