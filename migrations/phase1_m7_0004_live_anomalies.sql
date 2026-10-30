-- B-070: 5-minute live anomaly detection. Direction in PK allows flips.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE perception.live_anomalies (
    trade_date date NOT NULL,
    session text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('stock','basket','market')),
    subject text NOT NULL,
    direction text NOT NULL CHECK (direction IN ('up','down')),
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    first_ret double precision NOT NULL,
    last_ret double precision NOT NULL,
    peak_ret double precision NOT NULL,
    last_z double precision,
    peak_z double precision,
    quote_time timestamptz,
    members jsonb,
    data_quality text[],
    cause_event_id text,
    cause_kind text,
    cause_lag_minutes double precision,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','faded')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date, session, scope, subject, direction)
);
CREATE INDEX live_anomalies_status ON perception.live_anomalies (trade_date, status);
GRANT SELECT, INSERT, UPDATE, DELETE ON perception.live_anomalies TO role_perception;
GRANT SELECT ON perception.live_anomalies TO role_web;
COMMIT;
