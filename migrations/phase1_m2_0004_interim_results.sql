-- Execute as inves_cog_admin; existing schema default grants apply.
CREATE TABLE IF NOT EXISTS fundamentals.interim_results (
    ticker text NOT NULL,
    accession text NOT NULL,
    filed date NOT NULL,
    period_end date,
    currency text,
    revenue double precision,
    gross_profit double precision,
    operating_income double precision,
    net_income double precision,
    eps_diluted double precision,
    eps_basis text NOT NULL,
    source_exhibit text NOT NULL,
    parse_status text NOT NULL,
    UNIQUE NULLS NOT DISTINCT (ticker, accession, period_end)
);
CREATE INDEX IF NOT EXISTS interim_results_pit ON fundamentals.interim_results (ticker, filed, period_end);
CREATE TABLE IF NOT EXISTS fundamentals.monthly_revenue (
    ticker text NOT NULL,
    month date NOT NULL,
    revenue double precision NOT NULL,
    currency text NOT NULL,
    filed date NOT NULL,
    accession text NOT NULL,
    PRIMARY KEY (ticker, month, accession)
);
