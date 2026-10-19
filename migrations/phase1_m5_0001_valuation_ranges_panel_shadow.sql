BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS valuation_v1.ranges (
 trade_date date NOT NULL, ticker text NOT NULL, params_version text NOT NULL,
 method_version text NOT NULL, version text NOT NULL, type text NOT NULL,
 status text NOT NULL CHECK(status IN ('ok','unvalued','failed')),
 bear double precision, neutral double precision, bull double precision,
 pending_review boolean NOT NULL, payload jsonb NOT NULL, observed_at timestamptz NOT NULL,
 PRIMARY KEY(trade_date,ticker,params_version),
 CHECK(bear IS NULL OR (bear<=neutral AND neutral<=bull)),
 CHECK(payload->>'label'='估值参考 v1，不参与仓位')
);
CREATE TABLE IF NOT EXISTS valuation_v1.position_panel (
 trade_date date NOT NULL, ticker text NOT NULL, params_version text NOT NULL,
 payload jsonb NOT NULL, observed_at timestamptz NOT NULL,
 PRIMARY KEY(trade_date,ticker,params_version),
 CHECK(payload->>'label'='估值参考 v1，不参与仓位')
);
CREATE TABLE IF NOT EXISTS valuation_v1.shadow_rules (
 trade_date date NOT NULL, ticker text NOT NULL, params_version text NOT NULL,
 version text NOT NULL, vt1 boolean, vt2 boolean, v1_score double precision,
 v2_coef double precision, v3_trim_flag boolean, payload jsonb NOT NULL,
 observed_at timestamptz NOT NULL,
 PRIMARY KEY(trade_date,ticker,params_version),
 CHECK(payload->>'label'='估值参考 v1，不参与仓位')
);
REVOKE ALL ON valuation_v1.ranges,valuation_v1.position_panel,valuation_v1.shadow_rules FROM PUBLIC;
REVOKE ALL ON valuation_v1.ranges,valuation_v1.position_panel,valuation_v1.shadow_rules FROM role_trading;
REVOKE ALL ON SCHEMA valuation_v1 FROM role_trading;
GRANT SELECT,INSERT,UPDATE,DELETE ON valuation_v1.ranges,valuation_v1.position_panel,valuation_v1.shadow_rules TO role_valuation;
COMMIT;
