-- A025 observations only; inherited M0 writer/read-only grants, no new roles.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
ALTER TABLE ingest.intraday_snapshots DROP CONSTRAINT intraday_snapshots_session_check;
ALTER TABLE ingest.intraday_snapshots ADD CONSTRAINT intraday_snapshots_session_check
 CHECK (session IN ('pre','regular','post','overnight'));
CREATE TABLE ingest.wide_snapshots (
 ticker text NOT NULL,
 as_of timestamptz NOT NULL,
 last numeric NOT NULL,
 prev_close numeric,
 source text NOT NULL,
 fetched_at timestamptz NOT NULL,
 PRIMARY KEY(ticker,as_of,source)
);
CREATE INDEX wide_snapshots_as_of ON ingest.wide_snapshots(as_of);
COMMIT;
