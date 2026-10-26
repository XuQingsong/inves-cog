-- A023: calendar contracts shared with the read-only investor pages.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.earnings_calendar (
 ticker text NOT NULL, report_date date NOT NULL,
 time text NOT NULL CHECK (time IN ('pre','post','unknown')),
 eps_forecast numeric, n_estimates int, market_cap numeric,
 company text, source text NOT NULL, fetched_at timestamptz NOT NULL,
 PRIMARY KEY (ticker,report_date,source)
);
CREATE TABLE IF NOT EXISTS ingest.econ_calendar (
 event_date date NOT NULL, event_time_et text, country text NOT NULL, name text NOT NULL,
 actual text, consensus text, previous text,
 source text NOT NULL, fetched_at timestamptz NOT NULL,
 PRIMARY KEY (event_date,country,name,source)
);
COMMIT;
