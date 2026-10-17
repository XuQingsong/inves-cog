-- Disposable-database probe. role_perception can write attribution rows.
-- role_ingest cannot. The transaction rolls back.
BEGIN;
SET LOCAL ROLE role_perception;
INSERT INTO perception.retrievals
    (anomaly_id, info_id, role, relevance, published_at, source_level, retrieval_mode)
VALUES
    ('toshiba-2026-10-02', 'nikkei-hdd', 'primary', 0.8, '2026-10-01 12:00:00+00', 1, 'rules');
INSERT INTO perception.claims
    (claim_id, info_id, subject, mechanism, source_level)
VALUES
    ('claim-1', 'nikkei-hdd', 'Toshiba', '供给', 1);
INSERT INTO perception.candidates
    (anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids, scored)
VALUES
    ('toshiba-2026-10-02', 'c0', '供给', '[]'::jsonb, '[{"ticker":"WDC"}]'::jsonb, '{}', ARRAY['nikkei-hdd'], true);
INSERT INTO perception.candidates
    (anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids, scored)
VALUES
    ('toshiba-2026-10-02', 'c1', '无事件/资金面', '[]'::jsonb, '[]'::jsonb, '{}', '{}', false);
INSERT INTO perception.linkage_events
    (event_id, anomaly_id, lifecycle, history, deadline_outcome, closing_reason, unknowns, mechanism)
VALUES
    ('evt-1', 'toshiba-2026-10-02', '已验证·有影响', '[]'::jsonb, '支持', '截止日证据支持', '["投产与良率"]'::jsonb, '供给');
INSERT INTO perception.tracks
    (event_id, trade_date, emotion, capital, fundamental, metrics)
VALUES
    ('evt-1', '2026-10-02', '初现', '冲击中', '待验证', '{}'::jsonb);
INSERT INTO perception.second_hits
    (event_id, info_id, session, expected_z, control_z, outcome, source_root, published_at)
VALUES
    ('evt-1', 'tdk-heads', '2026-10-06', 1.4, 0.2, '命中', 'tdk', '2026-10-06 14:00:00+00');
INSERT INTO perception.impact_decomposition
    (anomaly_id, total_residual, event_part, amplification, unexplained)
VALUES
    ('toshiba-2026-10-02', -0.05, -0.05, 0, 0);
INSERT INTO perception.market_day (trade_date, systemic_event_tag, info_ids)
VALUES ('2026-10-02', '无', '{}');
INSERT INTO perception.ticker_status (anomaly_id, ticker, n_code)
VALUES ('toshiba-2026-10-02', 'WDC', 'N6');
INSERT INTO perception.reports (anomaly_id, report)
VALUES ('toshiba-2026-10-02', '{"fixture":"synthetic","status":"已验证·有影响"}'::jsonb);
DO $$
BEGIN
    INSERT INTO perception.candidates
        (anomaly_id, candidate_id, mechanism, chain, affected, control_baskets, info_ids, scored)
    VALUES
        ('toshiba-2026-10-02', 'empty', '供给', '[]'::jsonb, '[]'::jsonb, '{}', '{}', true);
    RAISE EXCEPTION 'empty citation was stored';
EXCEPTION
    WHEN check_violation THEN
        NULL;
END $$;
DO $$
DECLARE
    stored integer;
BEGIN
    SELECT count(*) INTO stored FROM perception.reports WHERE anomaly_id = 'toshiba-2026-10-02';
    IF stored <> 1 THEN
        RAISE EXCEPTION 'report was not stored';
    END IF;
END $$;
ROLLBACK;

DO $$
BEGIN
    SET LOCAL ROLE role_ingest;
    BEGIN
        INSERT INTO perception.reports (anomaly_id, report) VALUES ('ingest-denied', '{}'::jsonb);
        RAISE EXCEPTION 'ingest write was allowed';
    EXCEPTION
        WHEN insufficient_privilege THEN
            NULL;
    END;
END $$;
