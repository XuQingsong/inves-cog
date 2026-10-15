BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS ingest.bars_minute (
 ticker text NOT NULL, ts_utc timestamptz NOT NULL,
 open double precision, high double precision, low double precision, close double precision,
 volume bigint, session text NOT NULL CHECK (session IN ('pre','intraday','post')),
 source text NOT NULL, PRIMARY KEY (ticker, ts_utc)
);
CREATE TABLE IF NOT EXISTS ingest.bars_daily (
 ticker text NOT NULL, trade_date date NOT NULL, open double precision, high double precision,
 low double precision, close double precision, volume bigint, post_close double precision,
 adj_factor double precision, source text NOT NULL, PRIMARY KEY (ticker, trade_date)
);
CREATE TABLE IF NOT EXISTS ingest.wide_universe (
 trade_date date NOT NULL, ticker text NOT NULL, mktcap double precision, adv20 double precision,
 included boolean NOT NULL, exclude_reason text, notes text[] NOT NULL,
 PRIMARY KEY (trade_date, ticker)
);
CREATE TABLE IF NOT EXISTS ingest.info_items (
 info_id text PRIMARY KEY,
 kind text NOT NULL CHECK (kind IN ('news','sec_8k','form4','app_rank','trend','site_change','macro','short_interest','options_stats')),
 published_at timestamptz, first_seen_at timestamptz NOT NULL, source text NOT NULL,
 source_root text, source_level smallint NOT NULL CHECK (source_level BETWEEN 1 AND 4),
 headline text NOT NULL, body text, summary text, url text,
 tickers text[] NOT NULL, entities text[] NOT NULL, embedding vector(1024),
 extraction_status text NOT NULL CHECK (extraction_status IN ('ok','failed','pending')),
 flags text[] NOT NULL, payload jsonb NOT NULL, is_guidance boolean,
 guidance_direction text CHECK (guidance_direction IN ('up','down','maintain')),
 is_rating_change boolean, extraction_source jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS info_items_publication ON ingest.info_items (published_at);
CREATE INDEX IF NOT EXISTS info_items_source_root ON ingest.info_items (source_root);
CREATE INDEX IF NOT EXISTS info_items_tickers ON ingest.info_items USING gin (tickers);
CREATE TABLE IF NOT EXISTS ingest.info_item_versions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 info_id text NOT NULL REFERENCES ingest.info_items(info_id), version_seen_at timestamptz NOT NULL,
 headline text NOT NULL, body text, raw jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest.sec_filings (
 ticker text NOT NULL, cik text NOT NULL, accession text PRIMARY KEY, form text NOT NULL,
 filing_date date NOT NULL, report_date date, accepted_at timestamptz, items text[] NOT NULL,
 primary_document text, is_xbrl boolean, is_inline_xbrl boolean, fetched_at timestamptz NOT NULL,
 raw jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS sec_filings_ticker_date ON ingest.sec_filings (ticker, filing_date);
CREATE TABLE IF NOT EXISTS ingest.earnings_events (
 event_id text PRIMARY KEY, ticker text NOT NULL, accession text, item text, accepted_at timestamptz,
 session text CHECK (session IN ('pre','intraday','post','closed')), reaction_day date,
 ref_close double precision, fiscal_period text, fallback boolean NOT NULL,
 flags text[] NOT NULL, reported_date date, fetched_at timestamptz NOT NULL, superseded_at timestamptz
);
CREATE TABLE IF NOT EXISTS ingest.form4_events (
 event_id text PRIMARY KEY, ticker text NOT NULL, filed_at timestamptz, insider_name text,
 is_officer boolean, transaction_code text, shares double precision, price double precision,
 accession text, transaction_index integer, source text NOT NULL, raw jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest.app_rank_snapshots (
 ts_utc timestamptz NOT NULL, chart text NOT NULL CHECK (chart IN ('free','grossing')),
 rank smallint NOT NULL CHECK (rank BETWEEN 1 AND 100), app_id text NOT NULL,
 app_name text, developer text, PRIMARY KEY (ts_utc, chart, app_id)
);
CREATE TABLE IF NOT EXISTS ingest.short_interest (
 observation_id text PRIMARY KEY, ticker text NOT NULL, settlement_date date, publish_date date,
 short_interest double precision, avg_daily_volume double precision, days_to_cover double precision,
 si_pct_shares_outstanding double precision, source text NOT NULL, raw jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest.options_stats (
 trade_date date NOT NULL, category text NOT NULL, call_volume double precision,
 put_volume double precision, put_call_ratio double precision, open_interest double precision,
 source text NOT NULL, PRIMARY KEY (trade_date,category,source)
);
CREATE TABLE IF NOT EXISTS ingest.macro_observations (
 series_id text NOT NULL, observation_date date NOT NULL, value double precision, units text,
 realtime_start date NOT NULL, fetched_at timestamptz NOT NULL,
 PRIMARY KEY (series_id,observation_date,realtime_start)
);
CREATE TABLE IF NOT EXISTS ingest.website_snapshots (
 url text NOT NULL, captured_at timestamptz NOT NULL, body text NOT NULL,
 PRIMARY KEY (url,captured_at)
);
COMMIT;
