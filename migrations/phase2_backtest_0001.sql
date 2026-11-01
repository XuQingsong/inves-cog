BEGIN;

CREATE SCHEMA IF NOT EXISTS backtest;

CREATE TABLE backtest.runs (
    run_id      bigserial PRIMARY KEY,
    label       text NOT NULL,
    spec        jsonb NOT NULL,
    code_rev    text NOT NULL,
    started_at  timestamptz NOT NULL,
    finished_at timestamptz,
    status      text NOT NULL DEFAULT 'running',
    metrics     jsonb
);

CREATE TABLE backtest.trades (
    run_id     bigint NOT NULL REFERENCES backtest.runs(run_id) ON DELETE CASCADE,
    trade_date date NOT NULL,
    ticker     text NOT NULL,
    label      text NOT NULL,
    qty        numeric NOT NULL,
    price      numeric,
    amount     numeric
);

CREATE TABLE backtest.equity_curve (
    run_id   bigint NOT NULL REFERENCES backtest.runs(run_id) ON DELETE CASCADE,
    date     date NOT NULL,
    equity   numeric NOT NULL,
    cash     numeric NOT NULL,
    drawdown numeric NOT NULL,
    PRIMARY KEY (run_id, date)
);

CREATE TABLE backtest.positions_eod (
    run_id bigint NOT NULL REFERENCES backtest.runs(run_id) ON DELETE CASCADE,
    date   date NOT NULL,
    ticker text NOT NULL,
    qty    numeric NOT NULL,
    price  numeric,
    PRIMARY KEY (run_id, date, ticker)
);

CREATE TABLE backtest.skips (
    run_id bigint NOT NULL REFERENCES backtest.runs(run_id) ON DELETE CASCADE,
    date   date NOT NULL,
    ticker text NOT NULL,
    reason text NOT NULL
);

GRANT USAGE ON SCHEMA backtest TO role_web, role_perception, role_valuation, role_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA backtest TO role_web, role_perception, role_valuation;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA backtest TO role_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA backtest GRANT SELECT ON TABLES TO role_web, role_perception, role_valuation;
ALTER DEFAULT PRIVILEGES IN SCHEMA backtest GRANT SELECT, INSERT, UPDATE ON TABLES TO role_ingest;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA backtest TO role_ingest;
ALTER DEFAULT PRIVILEGES IN SCHEMA backtest GRANT USAGE ON SEQUENCES TO role_ingest;

COMMIT;
