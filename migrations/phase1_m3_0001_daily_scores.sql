BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS trading.daily_scores (
 signal_date date NOT NULL, ticker text NOT NULL,
 extractor text NOT NULL CHECK (extractor IN ('legacy','fixed')),
 rule_set text NOT NULL CHECK (rule_set = 'A'), params_version text NOT NULL,
 tech jsonb NOT NULL, derived jsonb NOT NULL,
 quality double precision, growth double precision, valuation double precision, timing double precision,
 timing_subitems jsonb NOT NULL, rank_score double precision, red_lines text[] NOT NULL,
 tier text CHECK (tier IN ('defense','normal','attack')), tier_changed_on date,
 certainty text NOT NULL CHECK (certainty IN ('low','medium','high')), certainty_points integer NOT NULL,
 hold_score double precision NOT NULL, hold_ok boolean NOT NULL, fund_bad boolean NOT NULL,
 runway_ok boolean NOT NULL, m31_adjusted_valuation double precision, m32_ok boolean NOT NULL,
 gate_pass boolean NOT NULL, entry_pass boolean NOT NULL, consec_pass integer NOT NULL CHECK (consec_pass >= 0),
 tradable boolean NOT NULL, null_reason text,
 PRIMARY KEY(signal_date,ticker,extractor,rule_set,params_version)
);
COMMIT;
