BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE IF NOT EXISTS overlay.versions (
 version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 date date NOT NULL, generated_at timestamptz NOT NULL, source_events_asof timestamptz NOT NULL,
 params_version text NOT NULL, payload jsonb NOT NULL,
 CHECK (source_events_asof <= generated_at)
);
CREATE INDEX IF NOT EXISTS overlay_versions_date ON overlay.versions (date, version DESC);

CREATE TABLE IF NOT EXISTS perception_shadow.signals (
 signal_key text PRIMARY KEY, date date NOT NULL, signal text NOT NULL CHECK (signal IN ('X1','X2','X3','X4')),
 ticker text NOT NULL, event_id text, condition_detail jsonb NOT NULL,
 shadow_action text NOT NULL, rule_a_action jsonb, params_version text NOT NULL
);
CREATE TABLE IF NOT EXISTS factor_shadow.registry (
 factor_id text NOT NULL, version text NOT NULL, definition text NOT NULL, inputs jsonb NOT NULL,
 pit_note text NOT NULL, target text NOT NULL, rationale text NOT NULL, source text NOT NULL,
 expected_direction text NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL,
 PRIMARY KEY (factor_id, version)
);
CREATE TABLE IF NOT EXISTS factor_shadow.daily (
 date date NOT NULL, ticker text NOT NULL, factor_id text NOT NULL, version text NOT NULL,
 value jsonb, substituted_value jsonb, would_pass boolean, rule_a_entry_pass boolean,
 gap_detail jsonb NOT NULL, params_version text NOT NULL, generated_at timestamptz NOT NULL,
 PRIMARY KEY (date, ticker, factor_id, version),
 FOREIGN KEY (factor_id,version) REFERENCES factor_shadow.registry (factor_id,version)
);
CREATE TABLE IF NOT EXISTS factor_shadow.f02_state (
 date date NOT NULL, ticker text NOT NULL, holding_id text NOT NULL, version text NOT NULL,
 state jsonb NOT NULL, shadow_action text NOT NULL, params_version text NOT NULL,
 PRIMARY KEY (date,ticker,holding_id,version)
);

REVOKE ALL ON ALL TABLES IN SCHEMA perception_shadow FROM role_trading;
REVOKE ALL ON ALL TABLES IN SCHEMA factor_shadow FROM role_trading;
REVOKE ALL ON SCHEMA perception_shadow, factor_shadow FROM role_trading;
REVOKE ALL ON overlay.versions, perception_shadow.signals, factor_shadow.registry,
 factor_shadow.daily, factor_shadow.f02_state FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON overlay.versions FROM role_trading;
GRANT SELECT ON overlay.versions TO role_trading;
-- Existing M0 defaults provide only the declared owner writes and web/shadow SELECT.
COMMIT;
