-- B-064: cached Chinese translations of page-visible news headlines.
BEGIN;
SET LOCAL ROLE inves_cog_admin;

CREATE TABLE IF NOT EXISTS perception.news_translations (
    info_id text PRIMARY KEY,
    title_zh text NOT NULL,
    model text NOT NULL,
    translated_at timestamptz NOT NULL
);

REVOKE SELECT, INSERT, UPDATE, DELETE ON perception.news_translations
FROM PUBLIC, role_ingest, role_trading, role_marketstate, role_valuation, role_perception, role_overlay, role_shadow, role_web;

GRANT SELECT, INSERT, UPDATE, DELETE ON perception.news_translations TO role_perception;
GRANT SELECT ON perception.news_translations TO role_web;

COMMIT;
