-- M8 context evidence uses persisted retrieval roles beyond the original per-anomaly pair.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

ALTER TABLE perception.retrievals DROP CONSTRAINT IF EXISTS retrievals_role_check;
ALTER TABLE perception.retrievals
    ADD CONSTRAINT retrievals_role_check
    CHECK (role IN ('primary', 'background', '板块或宏观', '财报事件'));

COMMIT;
