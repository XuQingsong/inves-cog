BEGIN;

-- CUSIP -> ticker mapping for Form 13F holdings, source recorded per row
-- (openfigi = verified via api.openfigi.com; infotable-inference = name match
-- with manual spot check). Unmatched CUSIPs are logged, never guessed.
CREATE TABLE ingest.cusip_map (
    cusip       text PRIMARY KEY,
    ticker      text NOT NULL,
    source      text NOT NULL,
    mapped_at   timestamptz NOT NULL DEFAULT now()
);

-- One row per (accession, infotable_sk) exactly as filed; amendments are kept
-- as additional rows, never deleted. Read rule: for a given
-- (filer_cik, period, ticker) the visible row is the one with the greatest
-- filing_date; RESTATEMENT amendments supersede the original filing's rows
-- (same period, later filing_date), NEW HOLDINGS rows add positions not in
-- the original filing — both stay queryable by accession.
CREATE TABLE ingest.f13_holdings (
    accession       text NOT NULL,
    infotable_sk    bigint NOT NULL,
    filer_cik       text NOT NULL,
    filer_name      text,
    period          date NOT NULL,
    filing_date     date NOT NULL,
    is_amendment    boolean NOT NULL DEFAULT false,
    amendment_type  text,
    cusip           text NOT NULL,
    ticker          text,
    shares          bigint,
    value           bigint,
    put_call        text,
    PRIMARY KEY (accession, infotable_sk)
);
CREATE INDEX f13_holdings_ticker_period ON ingest.f13_holdings (ticker, period, filing_date);
CREATE INDEX f13_holdings_period ON ingest.f13_holdings (period);

GRANT SELECT ON ingest.cusip_map TO role_web, role_perception, role_valuation;
GRANT SELECT ON ingest.f13_holdings TO role_web, role_perception, role_valuation;
GRANT SELECT, INSERT, UPDATE ON ingest.cusip_map TO role_ingest;
GRANT SELECT, INSERT, UPDATE ON ingest.f13_holdings TO role_ingest;

COMMIT;
