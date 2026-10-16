BEGIN;
SET LOCAL ROLE inves_cog_admin;
CREATE TABLE IF NOT EXISTS graph.entities (
 entity_id text PRIMARY KEY, kind text NOT NULL CHECK(kind IN
 ('company','private_company','product','app','model','workload','segment','theme')),
 name text NOT NULL, aliases text[] NOT NULL DEFAULT '{}', ticker text,
 app_store_ids text[] NOT NULL DEFAULT '{}', trend_keywords text[] NOT NULL DEFAULT '{}',
 official_urls text[] NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS graph.source_texts (
 ticker text NOT NULL, accession text NOT NULL, section text NOT NULL, text text NOT NULL,
 char_start integer NOT NULL CHECK(char_start>=0), char_end integer NOT NULL,
 fetched_at timestamptz NOT NULL, source_url text NOT NULL, source_sha256 text NOT NULL,
 CHECK(char_end=char_start+length(text)), PRIMARY KEY(ticker,accession,section,char_start)
);
CREATE TABLE IF NOT EXISTS graph.relations (
 relation_id text PRIMARY KEY, from_entity text NOT NULL REFERENCES graph.entities(entity_id),
 to_entity text NOT NULL REFERENCES graph.entities(entity_id),
 connection_type text NOT NULL CHECK(connection_type IN ('业务关系','市场共振','市场叙事','经营传导')),
 mechanism text NOT NULL CHECK(mechanism IN ('供给','需求','竞争','客户融资','估值倍数')),
 direction text, strength double precision, lag text,
 exposure_usd double precision CHECK(exposure_usd>=0), exposure_basis text,
 exposure_asof date, source_info_ids text[] NOT NULL DEFAULT '{}', evidence jsonb NOT NULL,
 opposing_evidence jsonb NOT NULL DEFAULT '[]', first_discovered_at timestamptz NOT NULL,
 last_evidence_at timestamptz, next_check_at timestamptz, invalidation_condition text,
 status text NOT NULL CHECK(status IN ('候选','观察到','有支持','已确立','驳回')),
 drafted_by text NOT NULL, reviewed_at timestamptz, basket_ids text[] NOT NULL DEFAULT '{}',
 revision integer NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS graph.baskets (
 basket_id text PRIMARY KEY, level text NOT NULL CHECK(level IN ('L1','L2','L3','auto')),
 name text NOT NULL, benchmark text NOT NULL, members jsonb NOT NULL, factor_basis jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS graph.monitored_entities (
 entity_id text PRIMARY KEY REFERENCES graph.entities(entity_id), reason text NOT NULL,
 channels text[] NOT NULL CHECK(channels <@ ARRAY['app','trend','site']::text[])
);
CREATE TABLE IF NOT EXISTS graph.review_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, relation_id text NOT NULL REFERENCES graph.relations,
 action text NOT NULL, before_row jsonb NOT NULL, after_row jsonb NOT NULL, reviewed_at timestamptz NOT NULL
);
CREATE OR REPLACE VIEW graph.confirmed_relations AS
 SELECT * FROM graph.relations WHERE status IN ('观察到','有支持','已确立') AND reviewed_at IS NOT NULL;
CREATE TABLE IF NOT EXISTS marketstate.daily (
 trade_date date NOT NULL,ticker text NOT NULL,session text NOT NULL CHECK(session IN ('close','post')),
 ret double precision,resid double precision,resid_z double precision,sigma double precision,
 beta_m double precision,beta_s double precision,beta_t double precision,primary_basket text,
 resid_5d double precision,resid_5d_z double precision,beta_share_5d double precision
 CHECK(beta_share_5d BETWEEN 0 AND 1),factor_set text NOT NULL,health_codes text[] NOT NULL,
 null_reason text, PRIMARY KEY(trade_date,ticker,session)
);
CREATE TABLE IF NOT EXISTS marketstate.baskets (
 trade_date date NOT NULL,basket_id text NOT NULL,session text NOT NULL CHECK(session IN ('close','post')),
 ret_ew double precision,resid double precision,resid_z double precision,same_sign_share double precision,
 member_resid_std double precision,health_codes text[] NOT NULL,null_reason text,
 PRIMARY KEY(trade_date,basket_id,session)
);
CREATE TABLE IF NOT EXISTS marketstate.rotation (
 trade_date date NOT NULL,session text NOT NULL CHECK(session IN ('close','post')),
 group_kind text NOT NULL CHECK(group_kind IN ('index','style','sector','l3')),group_id text NOT NULL,
 ret double precision,z double precision,ret_5d double precision,z_5d double precision,
 rank integer,rank_5d integer,health_codes text[] NOT NULL,null_reason text,
 PRIMARY KEY(trade_date,session,group_kind,group_id)
);
CREATE TABLE IF NOT EXISTS marketstate.market (
 trade_date date PRIMARY KEY,spy_5d_pct double precision,vix double precision,vix_pctile_252 double precision,
 down_share_5d_pct double precision,shock_flag boolean NOT NULL,l1_state text NOT NULL,
 vix3m double precision,vix_term_inverted boolean,spy_drawdown_252_pct double precision,
 null_reason text,sector_spread_z double precision,style_spread_z jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest.issuer_profiles (
 cik text NOT NULL,ticker text PRIMARY KEY,sic integer,sic_description text,fetched_at timestamptz NOT NULL
);
COMMIT;
