BEGIN;
SET LOCAL ROLE inves_cog_admin;
-- Preserve invalid draft evidence, but exclude it from the review queue and confirmed view.
UPDATE graph.relations SET status='驳回',evidence=evidence||jsonb_build_object('rejected_basis',exposure_basis),
 exposure_basis=NULL WHERE exposure_basis IS NOT NULL
 AND exposure_basis NOT IN ('收入占比','RPO','合同','应收','预付','分部收入') AND reviewed_at IS NULL;
ALTER TABLE graph.entities ADD CONSTRAINT graph_entity_id_nonempty CHECK(length(trim(entity_id))>0);
ALTER TABLE graph.entities ADD CONSTRAINT graph_entity_name_nonempty CHECK(length(trim(name))>0);
ALTER TABLE graph.relations ADD CONSTRAINT graph_exposure_basis_valid
 CHECK(exposure_basis IS NULL OR exposure_basis IN ('收入占比','RPO','合同','应收','预付','分部收入'));
CREATE TABLE graph.cluster_suggestions (
 week_start date PRIMARY KEY,as_of date NOT NULL,proposals jsonb NOT NULL,
 null_reason text,created_at timestamptz NOT NULL
);
COMMIT;
