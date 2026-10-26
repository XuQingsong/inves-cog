-- A024 is display-only; rule A does not read this table.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.intraday_snapshots (
 ticker text NOT NULL,
 as_of timestamptz NOT NULL,
 session text NOT NULL CHECK (session IN ('pre','regular','post')),
 last numeric NOT NULL,
 prev_close numeric,
 delay_minutes int NOT NULL,
 source text NOT NULL,
 fetched_at timestamptz NOT NULL,
 PRIMARY KEY (ticker,as_of,source)
);
CREATE INDEX IF NOT EXISTS intraday_snapshots_as_of ON ingest.intraday_snapshots(as_of);
COMMIT;
