BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE IF NOT EXISTS perception.anomalies (
    anomaly_id text PRIMARY KEY,
    trade_date date NOT NULL,
    session text NOT NULL CHECK (session IN ('close', 'post')),
    entry_paths text[] NOT NULL,
    layer text NOT NULL CHECK (layer IN ('L1', 'L2', 'L3', 'L4')),
    severity text NOT NULL CHECK (severity IN ('alert', 'watch')),
    baskets text[] NOT NULL,
    members jsonb NOT NULL,
    direction text NOT NULL CHECK (direction IN ('up', 'down')),
    max_abs_z double precision,
    data_quality jsonb NOT NULL,
    coverage jsonb NOT NULL,
    amplification jsonb NOT NULL,
    type_candidates_prelim text[] NOT NULL,
    status text NOT NULL CHECK (status = '已发现·原因未明'),
    universe text NOT NULL CHECK (universe IN ('pool', 'wide')),
    params_version text NOT NULL
);

CREATE TABLE IF NOT EXISTS perception.premarket_review (
    trade_date date NOT NULL,
    ticker text NOT NULL,
    prev_close double precision NOT NULL,
    premarket_last double precision NOT NULL,
    premarket_ret double precision NOT NULL,
    premarket_z double precision NOT NULL,
    reason text NOT NULL CHECK (reason IN ('holding', 'linked_event')),
    flag boolean NOT NULL,
    params_version text NOT NULL,
    PRIMARY KEY (trade_date, ticker)
);

GRANT INSERT, UPDATE ON TABLE ingest.job_runs TO role_perception;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE ingest.job_runs_id_seq TO role_perception;

COMMIT;
