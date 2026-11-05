BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS valuation_v1.ceiling_daily (
 ticker text NOT NULL, trade_date date NOT NULL,
 method text NOT NULL CHECK(method IN ('growth','loss','cyclical','financial')),
 r double precision NOT NULL CHECK(r>0), m double precision,
 m_r_minus_1 double precision, m_r_plus_1 double precision, fcf_m double precision,
 quality text NOT NULL CHECK(quality IN ('高','低')),
 band text NOT NULL CHECK(band IN ('可信','偏高','严重透支','不适用')),
 band_rule text NOT NULL, evidence jsonb NOT NULL, missing jsonb NOT NULL,
 asof timestamptz NOT NULL, payload jsonb NOT NULL, observed_at timestamptz NOT NULL,
 PRIMARY KEY(ticker,trade_date),
 CHECK(method='growth' OR band='不适用')
);
REVOKE ALL ON valuation_v1.ceiling_daily FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON valuation_v1.ceiling_daily TO role_valuation;
GRANT USAGE ON SCHEMA valuation_v1 TO role_web,role_trading;
GRANT SELECT ON valuation_v1.ceiling_daily TO role_web,role_trading;
COMMIT;
