-- B-072: per-earnings cards for core companies
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS perception.earnings_cards (
    ticker      text NOT NULL,
    report_date date NOT NULL,
    report_time text NOT NULL DEFAULT 'unknown',
    stage       text NOT NULL,
    card        jsonb NOT NULL DEFAULT '{}'::jsonb,
    missing     text[] NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, report_date)
);
CREATE INDEX IF NOT EXISTS earnings_cards_stage ON perception.earnings_cards (stage, report_date);
GRANT SELECT, INSERT, UPDATE, DELETE ON perception.earnings_cards TO role_perception;
GRANT SELECT ON perception.earnings_cards TO role_web;
-- card builder inputs
GRANT SELECT ON ingest.earnings_calendar TO role_perception;
GRANT SELECT ON ingest.earnings_implied_moves TO role_perception;
GRANT SELECT ON fundamentals.consensus_snapshot TO role_perception;
COMMIT;
