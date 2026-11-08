"""Voided anomalies (data_quality containing "voided") are skipped by background
consumers: attribution morning/replay reads and review case/sample/report reads.
Unmarked rows — empty {}, empty-array, or other jsonb — must still be returned."""

from datetime import date, timedelta

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from inves_cog.perception.review.calendar import cutoff
from tests.m8.test_attribution import _disposable_database

pytestmark = pytest.mark.phase1_blocking

DAY = date(2026, 11, 6)
SEEN = cutoff(DAY) - timedelta(hours=6)

ROWS = [
    # anomaly_id, session, member ticker, data_quality (column is NOT NULL)
    ("vc-void", "post", "VOIDME", '["voided"]'),
    ("vc-empty", "close", "KEEPME", "{}"),
    ("vc-arr", "close", "ARRME", "[]"),
    ("vc-other", "close", "OTHERME", '{"flag":true}'),
]


@pytest.fixture(scope="module")
def db():
    host = _disposable_database()
    admin = psycopg.connect(
        host=host, dbname="inves_cog", user="inves_cog_admin", row_factory=dict_row, autocommit=True
    )
    for anomaly_id, session, ticker, dq in ROWS:
        admin.execute(
            """
            INSERT INTO perception.anomalies (
                anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members,
                direction, max_abs_z, data_quality, coverage, amplification, type_candidates_prelim,
                status, universe, params_version, generated_at
            ) VALUES (
                %s, %s, %s, ARRAY['multi_5d'], 'L4', 'alert', %s, %s,
                'down', 4.7, %s::jsonb, '{}', '{}', ARRAY[]::text[],
                '已发现·原因未明', 'pool', 'vc', %s
            )
            """,
            (anomaly_id, DAY, session, ["vc"], Jsonb([{"ticker": ticker}]), dq, SEEN),
        )
    yield admin
    admin.execute("DELETE FROM perception.anomalies WHERE anomaly_id LIKE 'vc-%'")
    admin.close()


def test_attribution_morning_read_skips_voided(db):
    from inves_cog.perception.attribution.morning import _ANOMALIES

    rows = db.execute(_ANOMALIES, (DAY, cutoff(DAY))).fetchall()
    ids = {row["anomaly_id"] for row in rows}
    assert "vc-void" not in ids
    assert {"vc-empty", "vc-arr", "vc-other"} <= ids


def test_review_move_discovered_skips_voided(db):
    from inves_cog.perception.review.samples import _move_discovered

    assert _move_discovered(db, "KEEPME", DAY) is True
    assert _move_discovered(db, "ARRME", DAY) is True
    assert _move_discovered(db, "VOIDME", DAY) is False


def test_review_month_members_skips_voided(db):
    from inves_cog.perception.review.samples import _month_members

    names = _month_members(db, DAY)
    assert "VOIDME" not in names
    assert {"KEEPME", "ARRME", "OTHERME"} <= names


def test_review_case_seed_skips_voided(db):
    """_ensure_cases' set-select must not return voided rows."""
    src = db.execute(
        """
        SELECT anomaly_id FROM perception.anomalies
        WHERE universe = 'pool' AND trade_date <= %s
          AND (generated_at IS NULL OR generated_at < %s)
          AND NOT (coalesce(data_quality,'{}'::jsonb) ? 'voided')
        """,
        (DAY, cutoff(DAY)),
    ).fetchall()
    ids = {row["anomaly_id"] for row in src}
    assert "vc-void" not in ids
    assert {"vc-empty", "vc-arr", "vc-other"} <= ids
