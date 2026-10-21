"""Persist anomalies and the two job_runs rows. The clock is injected."""

import json

from psycopg.types.json import Jsonb

INSERT_JOB = """
INSERT INTO ingest.job_runs (
    task_name, trade_date, started_at, ended_at, status, processed_count, error_summary, params_version
) VALUES (%s, %s, %s, NULL, 'failed', 0, NULL, %s)
RETURNING id
"""

UPDATE_JOB = """
UPDATE ingest.job_runs
SET ended_at = %s, status = %s, processed_count = %s, error_summary = %s
WHERE id = %s
"""

INSERT_ANOMALY = """
INSERT INTO perception.anomalies (
    anomaly_id, trade_date, session, entry_paths, layer, severity, baskets, members, direction,
    max_abs_z, data_quality, coverage, amplification, type_candidates_prelim, status, universe, params_version,
    generated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

INSERT_PREMARKET = """
INSERT INTO perception.premarket_review (
    trade_date, ticker, prev_close, premarket_last, premarket_ret, premarket_z, reason, flag, params_version
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def run_recorded(connection, *, clock, task_name, trade_date, params_version, operation):
    started = clock.now_utc()
    inserted = connection.execute(INSERT_JOB, (task_name, trade_date, started, params_version)).fetchone()
    row_id = inserted["id"] if isinstance(inserted, dict) else inserted[0]
    try:
        count = operation()
    except Exception as exc:
        connection.execute(UPDATE_JOB, (clock.now_utc(), "failed", 0, str(exc), row_id))
        raise
    connection.execute(UPDATE_JOB, (clock.now_utc(), "ok", count, None, row_id))
    return row_id


def write_anomalies(connection, anomalies, *, generated_at):
    if generated_at is None or getattr(generated_at, "tzinfo", None) is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be a timezone-aware timestamp from the injected clock")
    for anomaly in anomalies:
        connection.execute(
            INSERT_ANOMALY,
            (
                anomaly["anomaly_id"],
                anomaly["trade_date"],
                anomaly["session"],
                anomaly["entry_paths"],
                anomaly["layer"],
                anomaly["severity"],
                anomaly["baskets"],
                Jsonb(anomaly["members"]),
                anomaly["direction"],
                anomaly["max_abs_z"],
                Jsonb(anomaly["data_quality"]),
                Jsonb(anomaly["coverage"]),
                Jsonb(anomaly["amplification"]),
                anomaly["type_candidates_prelim"],
                anomaly["status"],
                anomaly["universe"],
                anomaly["params_version"],
                generated_at,
            ),
        )
    return len(anomalies)


def write_premarket(connection, trade_date, rows, params_version):
    for row in rows:
        connection.execute(
            INSERT_PREMARKET,
            (
                trade_date,
                row["ticker"],
                row["prev_close"],
                row["premarket_last"],
                row["premarket_ret"],
                row["premarket_z"],
                row["reason"],
                row["flag"],
                params_version,
            ),
        )
    return len(rows)


def job_sql():
    return json.dumps({"insert": INSERT_JOB, "update": UPDATE_JOB})
