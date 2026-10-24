-- A020: existing source/key, append-only raw responses and request accounting.
BEGIN;
CREATE TABLE valuation_v1.consensus_snapshots (
 id uuid PRIMARY KEY, request_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('request','response','estimate')),
 ticker text NOT NULL, fetched_at timestamptz NOT NULL,
 status text NOT NULL CHECK(status IN ('reserved','ok','empty','error','throttled')),
 fiscal_end date, horizon text, eps_avg double precision, eps_count integer,
 revenue_avg double precision, raw jsonb NOT NULL,
 CHECK(kind<>'estimate' OR (fiscal_end IS NOT NULL AND horizon IS NOT NULL AND status='ok')),
 CHECK(eps_count IS NULL OR eps_count>=0)
);
CREATE UNIQUE INDEX consensus_request_phase ON valuation_v1.consensus_snapshots(request_id,kind) WHERE kind IN ('request','response');
CREATE UNIQUE INDEX consensus_estimate_period ON valuation_v1.consensus_snapshots(request_id,horizon,fiscal_end) WHERE kind='estimate';
CREATE INDEX consensus_snapshot_pit ON valuation_v1.consensus_snapshots(ticker,fetched_at DESC);
CREATE INDEX consensus_snapshot_quota ON valuation_v1.consensus_snapshots(fetched_at) WHERE kind IN ('request','response');
CREATE FUNCTION valuation_v1.consensus_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'consensus snapshots are append-only'; END;
$$;
CREATE TRIGGER consensus_snapshots_append_only BEFORE UPDATE OR DELETE ON valuation_v1.consensus_snapshots
 FOR EACH ROW EXECUTE FUNCTION valuation_v1.consensus_append_only();
REVOKE ALL ON valuation_v1.consensus_snapshots FROM PUBLIC;
GRANT SELECT,INSERT ON valuation_v1.consensus_snapshots TO role_valuation;
GRANT USAGE ON SCHEMA valuation_v1 TO role_web,role_trading;
GRANT SELECT ON valuation_v1.consensus_snapshots TO role_web,role_trading;
COMMIT;
