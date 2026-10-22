-- B-036: append-only M8 input snapshot for M9. No historical backfill.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE perception.m9_input_snapshots (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trade_date date NOT NULL,
    snapshot_generated_at timestamptz NOT NULL,
    source_asof timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('complete', 'degraded')),
    kind text NOT NULL CHECK (kind IN ('stage_completion', 'historical_backfill')),
    jobs jsonb NOT NULL,
    events jsonb NOT NULL,
    missing jsonb NOT NULL
);

REVOKE ALL ON TABLE perception.m9_input_snapshots FROM PUBLIC, role_ingest, role_trading, role_marketstate, role_valuation, role_perception, role_overlay, role_shadow, role_web;
GRANT SELECT, INSERT ON TABLE perception.m9_input_snapshots TO role_perception;
GRANT SELECT ON TABLE perception.m9_input_snapshots TO role_shadow;

REVOKE ALL ON SEQUENCE perception.m9_input_snapshots_snapshot_id_seq FROM PUBLIC, role_ingest, role_trading, role_marketstate, role_valuation, role_perception, role_overlay, role_shadow, role_web;
GRANT USAGE, SELECT ON SEQUENCE perception.m9_input_snapshots_snapshot_id_seq TO role_perception;

CREATE FUNCTION perception.reject_m9_snapshot_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'm9_input_snapshots is append-only';
END;
$$;

REVOKE ALL ON FUNCTION perception.reject_m9_snapshot_change() FROM PUBLIC, role_ingest, role_trading, role_marketstate, role_valuation, role_perception, role_overlay, role_shadow, role_web;

CREATE TRIGGER m9_input_snapshots_append_only
BEFORE UPDATE OR DELETE ON perception.m9_input_snapshots
FOR EACH ROW
EXECUTE FUNCTION perception.reject_m9_snapshot_change();

COMMIT;
