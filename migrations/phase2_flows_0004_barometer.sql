BEGIN;
CREATE TABLE flows.barometer_daily (
    date          date PRIMARY KEY,
    asof          timestamptz NOT NULL,
    fear          double precision,
    greed         double precision,
    fear_level    double precision,
    greed_level   double precision,
    stage         text,
    pendulum      double precision,
    short_heat    double precision,
    accumulation  double precision,
    nature        text,
    dims          jsonb NOT NULL DEFAULT '{}',
    inputs        jsonb NOT NULL DEFAULT '{}',
    missing       jsonb NOT NULL DEFAULT '[]',
    code_rev      text NOT NULL
);
CREATE TABLE flows.barometer_intraday (
    ts            timestamptz NOT NULL,
    asof          timestamptz NOT NULL,
    fear          double precision,
    greed         double precision,
    fear_level    double precision,
    greed_level   double precision,
    stage         text,
    pendulum      double precision,
    short_heat    double precision,
    accumulation  double precision,
    nature        text,
    dims          jsonb NOT NULL DEFAULT '{}',
    inputs        jsonb NOT NULL DEFAULT '{}',
    missing       jsonb NOT NULL DEFAULT '[]',
    code_rev      text NOT NULL,
    PRIMARY KEY (ts)
);
GRANT SELECT ON flows.barometer_daily TO role_web, role_perception, role_valuation;
GRANT SELECT ON flows.barometer_intraday TO role_web, role_perception, role_valuation;
GRANT SELECT, INSERT, UPDATE ON flows.barometer_daily TO role_ingest;
GRANT SELECT, INSERT, UPDATE ON flows.barometer_intraday TO role_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA flows GRANT SELECT ON TABLES TO role_web, role_perception, role_valuation;
ALTER DEFAULT PRIVILEGES IN SCHEMA flows GRANT SELECT, INSERT, UPDATE ON TABLES TO role_ingest;
COMMIT;
