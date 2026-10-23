-- B-049: seven M10 review tables. No new roles and no grants on other tables.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE perception.cases (
    case_id text PRIMARY KEY,
    anomaly_id text NOT NULL UNIQUE,
    trade_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('未完成', '已完成')),
    reason text,
    updated_at timestamptz NOT NULL
);

CREATE TABLE perception.case_labels (
    case_id text NOT NULL REFERENCES perception.cases(case_id),
    horizon text NOT NULL CHECK (horizon IN ('T+1', 'T+5', 'T+20')),
    as_of date NOT NULL,
    drafted boolean NOT NULL,
    confirmed_at timestamptz,
    labels jsonb NOT NULL,
    reason text,
    visible_until timestamptz NOT NULL,
    written_at timestamptz NOT NULL,
    PRIMARY KEY (case_id, horizon)
);

CREATE TABLE perception.precursor_snapshots (
    trade_date date NOT NULL,
    subject_kind text NOT NULL CHECK (subject_kind IN ('ticker', 'basket')),
    subject_id text NOT NULL,
    features jsonb NOT NULL,
    PRIMARY KEY (trade_date, subject_kind, subject_id)
);

CREATE TABLE perception.miss_samples (
    sample_id text PRIMARY KEY,
    frame text NOT NULL CHECK (frame IN ('weekly_info', 'monthly_move', 'monthly_company')),
    period_end date NOT NULL,
    item_ref text NOT NULL,
    discovered boolean NOT NULL,
    anomaly_id text,
    judgment text CHECK (judgment IN ('应发现', '不应发现', '未知', '数据不覆盖')),
    gap_ring text,
    judged_at timestamptz,
    UNIQUE (frame, period_end, item_ref)
);

CREATE TABLE perception.patterns (
    pattern_id text PRIMARY KEY,
    trigger_type text NOT NULL,
    mechanism text NOT NULL,
    capital_behavior text NOT NULL,
    outcome text NOT NULL,
    example_count integer NOT NULL,
    retained_holds boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('观察', '有效')),
    examples jsonb NOT NULL,
    counterexamples jsonb NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE perception.reports_weekly (
    report_id text PRIMARY KEY,
    period_end date NOT NULL,
    generated_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

CREATE TABLE perception.reports_monthly (
    report_id text PRIMARY KEY,
    period_end date NOT NULL,
    generated_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);

REVOKE ALL ON TABLE
    perception.cases,
    perception.case_labels,
    perception.precursor_snapshots,
    perception.miss_samples,
    perception.patterns,
    perception.reports_weekly,
    perception.reports_monthly
FROM PUBLIC, role_ingest, role_trading, role_marketstate, role_valuation, role_perception, role_overlay, role_shadow, role_web;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    perception.cases,
    perception.case_labels,
    perception.precursor_snapshots,
    perception.miss_samples,
    perception.patterns,
    perception.reports_weekly,
    perception.reports_monthly
TO role_perception;

GRANT SELECT ON TABLE
    perception.cases,
    perception.case_labels,
    perception.precursor_snapshots,
    perception.miss_samples,
    perception.patterns,
    perception.reports_weekly,
    perception.reports_monthly
TO role_web;

COMMIT;
