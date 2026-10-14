BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS fundamentals.fin_state (
 ticker text NOT NULL, extractor text NOT NULL CHECK (extractor IN ('legacy','fixed')),
 accession text, form text, filed date NOT NULL, period_end date, fiscal_period text,
 rev_ttm double precision, ni_ttm double precision, rev_growth double precision,
 rev_q_yoy double precision, rev_accel_pp double precision, eps_ttm double precision,
 eps_growth double precision, gross_margin double precision, gross_margin_change_pp double precision,
 fcf_ttm double precision, fcf_margin double precision, fcf_conversion double precision, roe double precision,
 cash double precision, debt double precision, net_debt double precision, net_debt_fcf double precision,
 current_ratio double precision, shares double precision, fcf_margin_change_pp double precision,
 op_margin_ttm double precision, health_codes text[] NOT NULL, field_sources jsonb NOT NULL,
 values_extra jsonb NOT NULL, PRIMARY KEY(ticker,extractor,filed)
);
CREATE TABLE IF NOT EXISTS fundamentals.segments (
 ticker text NOT NULL, accession text NOT NULL, filed date NOT NULL, period_end date,
 period_len text, axis text NOT NULL, segment_raw text, segment_std text[],
 revenue double precision, segment_profit double precision, profit_basis text, margin_pct double precision,
 yoy_pct double precision, share_pct double precision, recast_group text, health_codes text[] NOT NULL,
 evidence jsonb NOT NULL, row_id text PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS fundamentals.segment_mapping (
 id text PRIMARY KEY, ticker text NOT NULL, segment_raw text NOT NULL, graph_node_ids text[] NOT NULL,
 drafted_by text NOT NULL CHECK(drafted_by='glm-5.3'), draft_reason text NOT NULL,
 status text NOT NULL CHECK(status IN ('待审核','已确认','驳回')), reviewed_at timestamptz,
 reviewer text, UNIQUE(ticker,segment_raw)
);
CREATE TABLE IF NOT EXISTS fundamentals.consensus_snapshot (
 as_of date NOT NULL, ticker text NOT NULL, source text NOT NULL CHECK(source IN ('yfinance','muse_import')),
 captured_at timestamptz, fy_cy date, fy_ny date,
 eps_cq double precision, eps_nq double precision, eps_cy double precision, eps_ny double precision,
 rev_cy double precision, rev_ny double precision, up_7d double precision, down_7d double precision,
 up_30d double precision, down_30d double precision, coverage double precision,
 eps_high_cy double precision, eps_low_cy double precision, pt_mean double precision, pt_median double precision,
 raw jsonb NOT NULL, PRIMARY KEY(as_of,ticker,source)
);
CREATE TABLE IF NOT EXISTS fundamentals.consensus_derived (
 as_of date NOT NULL, ticker text NOT NULL, chg_7d_pct double precision, chg_30d_pct double precision,
 chg_90d_pct double precision, breadth_7d double precision, breadth_30d double precision, dispersion double precision,
 surprise_last4 jsonb NOT NULL, window_status jsonb NOT NULL, values_extra jsonb NOT NULL,
 PRIMARY KEY(as_of,ticker)
);
CREATE TABLE IF NOT EXISTS fundamentals.profile (
 as_of date NOT NULL, ticker text NOT NULL, profile jsonb NOT NULL, PRIMARY KEY(as_of,ticker)
);
CREATE TABLE IF NOT EXISTS fundamentals.health (
 ticker text PRIMARY KEY, latest_period_end date, latest_filed date, latest_8k_202 timestamptz,
 health_codes text[] NOT NULL, can_score boolean NOT NULL, can_trade boolean NOT NULL, reason text,
 CHECK(NOT can_trade OR can_score), CHECK(can_score OR reason IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS fundamentals.fx_rates (
 currency text NOT NULL, series_id text NOT NULL, observation_date date NOT NULL, realtime_start date NOT NULL,
 value double precision, fetched_at timestamptz NOT NULL, PRIMARY KEY(currency,observation_date,realtime_start)
);
COMMIT;
