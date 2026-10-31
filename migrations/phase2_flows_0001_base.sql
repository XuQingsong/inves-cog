BEGIN;

CREATE SCHEMA IF NOT EXISTS flows;

CREATE TABLE IF NOT EXISTS flows.raw_files (
    raw_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source text NOT NULL,
    url text NOT NULL,
    period text NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    sha256 text NOT NULL,
    path text NOT NULL,
    bytes integer NOT NULL
);

CREATE TABLE IF NOT EXISTS flows.series_catalog (
    series_id text PRIMARY KEY,
    name_zh text NOT NULL,
    unit text NOT NULL,
    frequency text NOT NULL,
    publish_rule text,
    source text NOT NULL,
    history_start date
);

CREATE TABLE IF NOT EXISTS flows.observations (
    series_id text NOT NULL REFERENCES flows.series_catalog(series_id),
    obs_date date NOT NULL,
    value double precision NOT NULL,
    published_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    vintage text NOT NULL DEFAULT 'initial',
    raw_file_id bigint REFERENCES flows.raw_files(raw_file_id),
    PRIMARY KEY (series_id, obs_date, vintage)
);
CREATE INDEX IF NOT EXISTS observations_date_idx ON flows.observations (obs_date);
CREATE INDEX IF NOT EXISTS observations_pub_idx ON flows.observations (published_at);

CREATE TABLE IF NOT EXISTS flows.etf_daily (
    ticker text NOT NULL,
    date date NOT NULL,
    nav double precision,
    shares bigint,
    aum double precision,
    issuer text NOT NULL,
    published_at timestamptz NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS flows.option_chain (
    underlying text NOT NULL,
    snapshot_at timestamptz NOT NULL,
    expiry date NOT NULL,
    strike double precision NOT NULL,
    cp text NOT NULL CHECK (cp IN ('C', 'P')),
    oi bigint,
    oi_date date,
    volume bigint,
    iv double precision,
    delta double precision,
    gamma double precision,
    bid double precision,
    ask double precision,
    source text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (underlying, snapshot_at, expiry, strike, cp, source)
);
CREATE INDEX IF NOT EXISTS option_chain_und_snap_idx ON flows.option_chain (underlying, snapshot_at);

CREATE TABLE IF NOT EXISTS flows.option_volume_occ (
    date date NOT NULL,
    underlying text NOT NULL,
    account_type text NOT NULL,
    cp text NOT NULL,
    quantity bigint NOT NULL,
    PRIMARY KEY (date, underlying, account_type, cp)
);

CREATE TABLE IF NOT EXISTS flows.cftc_positions (
    report_date date NOT NULL,
    release_at timestamptz NOT NULL,
    market text NOT NULL,
    trader_class text NOT NULL,
    long bigint,
    short bigint,
    spread bigint,
    PRIMARY KEY (report_date, market, trader_class)
);

CREATE TABLE IF NOT EXISTS flows.short_volume (
    date date NOT NULL,
    ticker text NOT NULL,
    short_volume bigint,
    total_volume bigint,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS flows.derived_daily (
    metric_id text NOT NULL,
    date date NOT NULL,
    value double precision,
    asof timestamptz,
    inputs_hash text,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metric_id, date)
);

GRANT SELECT ON ALL TABLES IN SCHEMA flows TO role_web;
GRANT SELECT ON ALL TABLES IN SCHEMA flows TO role_perception;
GRANT SELECT ON ALL TABLES IN SCHEMA flows TO role_valuation;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA flows TO role_ingest;
GRANT USAGE ON SCHEMA flows TO role_web, role_perception, role_valuation, role_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA flows GRANT SELECT ON TABLES TO role_web, role_perception, role_valuation;
ALTER DEFAULT PRIVILEGES IN SCHEMA flows GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO role_ingest;

COMMIT;
