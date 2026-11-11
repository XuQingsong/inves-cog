-- Attribution context items read member earnings events, earnings cards, and
-- the Nasdaq calendar for the synthetic 财报事件 payload rows.
GRANT SELECT ON ingest.earnings_events TO role_ingest;
GRANT SELECT ON ingest.earnings_calendar TO role_ingest;
GRANT SELECT ON perception.earnings_cards TO role_ingest;
