BEGIN;

CREATE TABLE IF NOT EXISTS ingest.analyst_actions (
    ticker text NOT NULL,
    action_date date NOT NULL,
    firm text NOT NULL,
    action text NOT NULL,
    from_grade text,
    to_grade text,
    pt_action text,
    prior_pt numeric,
    current_pt numeric,
    source text NOT NULL DEFAULT 'yahoo',
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, action_date, firm, source)
);

GRANT SELECT ON ingest.analyst_actions TO role_web;
GRANT SELECT, INSERT ON ingest.analyst_actions TO role_ingest;
GRANT SELECT ON ingest.analyst_actions TO role_perception;
GRANT SELECT ON ingest.analyst_actions TO role_valuation;

COMMIT;
