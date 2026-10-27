"""UD-COORD-36 queue boundary, retention and zero old-news model dispatch."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from inves_cog.clock import FrozenClock
from inves_cog.ingest.info import make_item
from inves_cog.ingest.repository import Repository
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking
CUTOFF = datetime(2026, 10, 21, 4, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 24, 15, tzinfo=timezone.utc)


@pytest.fixture
def queue():
    host = _disposable_database()
    with psycopg.connect(host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row) as db:
        # Harness-only transaction; rollback restores every prior fixture and version.
        db.execute("TRUNCATE ingest.info_items CASCADE")
        repo = Repository(db)
        yield repo, db
        db.rollback()


def put(repo, name, published, *, kind="news", status="pending"):
    row = make_item(
        kind,
        "Reuters" if kind == "news" else "SEC",
        name,
        headline="Queue fixture " + name,
        body="Recorded offline fixture",
        clock=FrozenClock(NOW),
        published_at=published,
    )
    row["extraction_status"] = status
    row["extraction_source"] = {"existing_evidence": "retained"}
    repo.put_info(row)
    return row


def test_ud36_exact_et_boundary_unknown_date_and_non_news_queue(queue):
    repo, db = queue
    old = put(repo, "old", CUTOFF - timedelta(microseconds=1))
    at = put(repo, "at", CUTOFF)
    recent = put(repo, "recent", NOW)
    unknown = put(repo, "unknown", None)
    sec = put(repo, "sec", CUTOFF - timedelta(days=20), kind="sec_8k")
    put(repo, "sec-null", None, kind="sec_8k")
    rows = repo.pending_info(32, as_of=NOW)
    ids = {r["info_id"] for r in rows}
    assert old["info_id"] not in ids and unknown["info_id"] not in ids
    assert {at["info_id"], recent["info_id"], sec["info_id"]} <= ids
    assert len(rows) == 4
    # Exercise the actual pipeline dispatch with a counting extraction client.
    from inves_cog.ingest.pipeline import Pipeline

    class CountingExtractor:
        def __init__(self):
            self.calls = []

        def process(self, items):
            for item in items:
                self.calls.append(item["info_id"])
                yield item

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.repo, pipeline.clock, pipeline.triage = repo, FrozenClock(NOW), CountingExtractor()
    result = pipeline.enrich_pending()
    # A-026: pending sec_8k rows are converted to rules-only first and never
    # reach the model path; the two news items still go through triage.
    assert result["processed_count"] == 4
    assert len(pipeline.triage.calls) == 2
    assert old["info_id"] not in pipeline.triage.calls and sec["info_id"] not in pipeline.triage.calls


def test_ud36_marks_old_without_mutating_original_content_or_claiming_extracted(queue):
    repo, db = queue
    old = put(repo, "retained", CUTOFF - timedelta(days=3))
    before = deepcopy(
        dict(db.execute("SELECT * FROM ingest.info_items WHERE info_id=%s", (old["info_id"],)).fetchone())
    )
    repo.pending_info(1, as_of=NOW)
    after = dict(db.execute("SELECT * FROM ingest.info_items WHERE info_id=%s", (old["info_id"],)).fetchone())
    marker = after["extraction_source"].pop("backfill_skip")
    assert marker["reason"] == "补采未提取（UD-COORD-36）"
    assert marker["decision"] == "UD-COORD-36"
    assert datetime.fromisoformat(marker["marked_at"]) == NOW
    assert after == before and after["extraction_status"] == "pending"
    first = db.execute("SELECT extraction_source FROM ingest.info_items WHERE info_id=%s", (old["info_id"],)).fetchone()
    assert not repo.has_pending_info(as_of=NOW + timedelta(minutes=1))
    second = db.execute(
        "SELECT extraction_source FROM ingest.info_items WHERE info_id=%s", (old["info_id"],)
    ).fetchone()
    assert second == first  # No timestamp churn or repeated reclassification.


def test_ud36_poll_marks_old_only_queue_and_leaves_already_extracted_evidence(queue):
    repo, db = queue
    old = put(repo, "old-only", CUTOFF - timedelta(days=1))
    complete = put(repo, "already-ok", CUTOFF - timedelta(days=1), status="ok")
    assert not repo.has_pending_info(as_of=NOW)
    saved = db.execute("SELECT extraction_source FROM ingest.info_items WHERE info_id=%s", (old["info_id"],)).fetchone()
    assert saved["extraction_source"]["backfill_skip"]["decision"] == "UD-COORD-36"
    saved = db.execute(
        "SELECT extraction_source FROM ingest.info_items WHERE info_id=%s", (complete["info_id"],)
    ).fetchone()
    assert saved["extraction_source"] == complete["extraction_source"]
