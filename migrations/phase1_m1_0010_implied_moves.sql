-- A028: indicative reference quotes only; M0 grants retained, no new roles.
BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.earnings_implied_moves (
 ticker text NOT NULL, report_date date NOT NULL,
 report_time text NOT NULL CHECK (report_time IN ('pre','post','unknown')),
 captured_at timestamptz NOT NULL, quote_time timestamptz NOT NULL,
 expiry date NOT NULL, strike numeric NOT NULL CHECK (strike>0),
 spot numeric NOT NULL CHECK (spot>0), spot_source text NOT NULL CHECK (spot_source IN ('IEX','SIP')),
 call_mid numeric NOT NULL CHECK (call_mid>0), put_mid numeric NOT NULL CHECK (put_mid>0),
 straddle_pct numeric NOT NULL CHECK (straddle_pct>0), iv_call numeric, iv_put numeric,
 feed text NOT NULL CHECK (feed='indicative'),
 PRIMARY KEY (ticker,report_date,captured_at)
);
GRANT SELECT,INSERT,UPDATE,DELETE ON ingest.earnings_implied_moves TO role_ingest;
GRANT SELECT ON ingest.earnings_implied_moves TO role_web,role_perception,role_valuation,role_shadow,role_trading;
COMMIT;
