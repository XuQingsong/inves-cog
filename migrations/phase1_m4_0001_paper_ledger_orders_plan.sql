BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS trading.ledger (
 portfolio_id text NOT NULL, trade_date date NOT NULL, phase text NOT NULL,
 extractor text NOT NULL CHECK (extractor IN ('legacy','fixed')),
 rule_set text NOT NULL CHECK (rule_set='A'), params_version text NOT NULL,
 cash double precision NOT NULL, equity double precision, peak_equity double precision NOT NULL,
 state jsonb NOT NULL, observed_at timestamptz NOT NULL,
 PRIMARY KEY (portfolio_id,trade_date,phase,extractor,rule_set,params_version)
);
CREATE TABLE IF NOT EXISTS trading.orders (
 portfolio_id text NOT NULL, order_id text NOT NULL, signal_date date NOT NULL, trade_date date NOT NULL,
 ticker text NOT NULL, side text CHECK (side IN ('buy','sell')), kind text NOT NULL,
 qty bigint CHECK(qty IS NULL OR qty>0), fill_price double precision, cost double precision,
 rule_ids text[] NOT NULL, reason_zh text NOT NULL, tier text,
 rule_set text NOT NULL CHECK(rule_set='A'), params_version text NOT NULL, overlay_version text,
 status text NOT NULL CHECK(status IN ('pending','filled','canceled','blocked')),
 intent jsonb NOT NULL, PRIMARY KEY(portfolio_id,order_id), CHECK(trade_date>signal_date)
);
CREATE TABLE IF NOT EXISTS trading.plan (
 portfolio_id text NOT NULL, trade_date date NOT NULL, signal_date date NOT NULL,
 extractor text NOT NULL CHECK(extractor IN ('legacy','fixed')), rule_set text NOT NULL CHECK(rule_set='A'),
 params_version text NOT NULL, published boolean NOT NULL, generated_at timestamptz NOT NULL,
 payload jsonb NOT NULL, PRIMARY KEY(portfolio_id,trade_date,extractor,rule_set,params_version)
);
REVOKE ALL ON trading.ledger,trading.orders,trading.plan FROM PUBLIC;
GRANT INSERT, UPDATE, DELETE ON trading.ledger,trading.orders,trading.plan TO role_trading;
COMMIT;
