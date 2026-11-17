-- M10 business verdicts read prior consensus through the perception writer identity.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

GRANT USAGE ON SCHEMA valuation_v1 TO role_perception;
GRANT SELECT ON TABLE valuation_v1.consensus_snapshots TO role_perception;

COMMIT;
