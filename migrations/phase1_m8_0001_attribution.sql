BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE IF NOT EXISTS perception.retrievals (
 anomaly_id text NOT NULL, info_id text NOT NULL,
 role text NOT NULL CHECK (role IN ('primary','background')),
 relevance double precision, published_at timestamptz, source_level integer,
 retrieval_mode text NOT NULL CHECK (retrieval_mode IN ('vector','rules')),
 PRIMARY KEY (anomaly_id, info_id)
);

CREATE TABLE IF NOT EXISTS perception.claims (
 claim_id text PRIMARY KEY, info_id text NOT NULL,
 subject text, variable text, mechanism text, direction text,
 quantity text, horizon text, certainty text, source_level integer
);

CREATE TABLE IF NOT EXISTS perception.candidates (
 anomaly_id text NOT NULL, candidate_id text NOT NULL,
 mechanism text NOT NULL, chain jsonb NOT NULL, affected jsonb NOT NULL,
 control_baskets text[] NOT NULL DEFAULT '{}', info_ids text[] NOT NULL,
 evidence jsonb, score double precision, confidence text, magnitude jsonb,
 fundamental text, scored boolean NOT NULL,
 PRIMARY KEY (anomaly_id, candidate_id),
 CHECK (scored = false OR cardinality(info_ids) > 0)
);

CREATE TABLE IF NOT EXISTS perception.linkage_events (
 event_id text PRIMARY KEY, anomaly_id text NOT NULL,
 lifecycle text NOT NULL CHECK (lifecycle IN (
  '已发现','假设中','市场确认','基本面核查中','已验证·有影响','已衰减·无影响','已证伪'
 )),
 history jsonb NOT NULL, deadline_outcome text, closing_reason text,
 unknowns jsonb NOT NULL DEFAULT '[]', mechanism text
);

CREATE TABLE IF NOT EXISTS perception.tracks (
 event_id text NOT NULL, trade_date date NOT NULL,
 emotion text, capital text, fundamental text, metrics jsonb NOT NULL,
 PRIMARY KEY (event_id, trade_date)
);

CREATE TABLE IF NOT EXISTS perception.second_hits (
 event_id text NOT NULL, info_id text NOT NULL, session text,
 expected_z double precision, control_z double precision,
 outcome text NOT NULL, source_root text NOT NULL, published_at timestamptz NOT NULL,
 PRIMARY KEY (event_id, info_id)
);

CREATE TABLE IF NOT EXISTS perception.impact_decomposition (
 anomaly_id text PRIMARY KEY, total_residual double precision NOT NULL,
 event_part double precision NOT NULL, amplification double precision NOT NULL,
 unexplained double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS perception.market_day (
 trade_date date PRIMARY KEY, systemic_event_tag text NOT NULL, info_ids text[] NOT NULL
);

CREATE TABLE IF NOT EXISTS perception.ticker_status (
 anomaly_id text NOT NULL, ticker text NOT NULL, exposure text, mechanism text,
 n_code text NOT NULL CHECK (n_code IN ('N1','N2','N6')), note text,
 PRIMARY KEY (anomaly_id, ticker)
);

CREATE TABLE IF NOT EXISTS perception.reports (
 anomaly_id text PRIMARY KEY, report jsonb NOT NULL
);

REVOKE ALL ON
 perception.retrievals, perception.claims, perception.candidates, perception.linkage_events,
 perception.tracks, perception.second_hits, perception.impact_decomposition, perception.market_day,
 perception.ticker_status, perception.reports
FROM PUBLIC;
COMMIT;
