BEGIN;

-- House of Representatives Periodic Transaction Reports (STOCK Act).
-- One row per PTR filing (FilingType=P in the annual FD index).
-- PIT reads must use filing_date, not collected_at.
-- parse_status: pending (indexed, not downloaded) | parsed |
--   scanned_unparsed (image-only PDF or extractor unavailable/failed) |
--   download_failed (transient fetch failure, retried next run).
CREATE TABLE ingest.congress_ptr (
    doc_id        text PRIMARY KEY,
    filing_date   date NOT NULL,
    member        text NOT NULL,
    state_dst     text,
    source_url    text NOT NULL,
    pdf_sha256    text,
    fetched_at    timestamptz,
    parse_status  text NOT NULL DEFAULT 'pending',
    parse_note    text,
    transactions  jsonb NOT NULL DEFAULT '[]'::jsonb,
    collected_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX congress_ptr_filing_idx ON ingest.congress_ptr (filing_date);

COMMIT;
