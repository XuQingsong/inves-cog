"""Raw-file archiving + upserts + health for flows.* tables."""

import gzip
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path

from inves_cog.ingest.http import HTTPClient

log = logging.getLogger(__name__)
DEFAULT_RAW = Path("/home/claudeuser/inves-cog-data/flows/raw")
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def polite_http(**kw):
    return HTTPClient(retries=2, timeout=30, send=kw.get("send"))


def save_raw(raw_dir, source, url, period, content, connection=None):
    """Always-gzip original bytes under raw/<source>/<yyyy-mm-dd>/, record row."""
    if isinstance(content, str):
        content = content.encode()
    sha = hashlib.sha256(content).hexdigest()
    folder = Path(raw_dir) / source / str(period)[:10]
    folder.mkdir(parents=True, exist_ok=True)
    name = folder / f"{sha[:16]}.gz"
    if not name.exists():
        name.write_bytes(gzip.compress(content))
    row_id = None
    if connection is not None:
        r = connection.execute(
            "INSERT INTO flows.raw_files (source,url,period,sha256,path,bytes) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING raw_file_id",
            (source, url, str(period), sha, str(name), len(content)),
        ).fetchone()
        row_id = r["raw_file_id"] if r else None
    return {"sha256": sha, "path": str(name), "raw_file_id": row_id, "bytes": len(content)}


def upsert_many(connection, table, cols, rows, conflict="nothing"):
    """executemany upsert; conflict 'nothing'|'update'."""
    if not rows:
        return 0
    sql = f"INSERT INTO flows.{table} ({','.join(cols)}) VALUES ({','.join('%s' for _ in cols)})"
    if conflict == "update":
        pk = {
            "option_chain": ("underlying", "snapshot_at", "expiry", "strike", "cp", "source"),
            "observations": ("series_id", "obs_date", "vintage"),
            "etf_daily": ("ticker", "date"),
            "derived_daily": ("metric_id", "date"),
            "option_volume_occ": ("date", "underlying", "account_type", "cp"),
            "short_volume": ("date", "ticker"),
            "raw_files": ("raw_file_id",),
            "cftc_positions": ("report_date", "market", "trader_class"),
        }.get(table, ())
        non_pk = [c for c in cols if c not in pk]
        if non_pk:
            sql += " ON CONFLICT (" + ",".join(pk) + ") DO UPDATE SET " + ",".join(f"{c}=EXCLUDED.{c}" for c in non_pk)
        else:
            sql += " ON CONFLICT DO NOTHING"
    else:
        sql += " ON CONFLICT DO NOTHING"
    with connection.cursor() as cur:
        cur.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
    log.info("flows.%s upserted %d rows", table, len(rows))
    return len(rows)


def record_health(connection, source, ok, items=0, note="", latency=0.0, now=None):
    """Upsert ingest.source_health like phase-1 write_health (no dup key)."""
    try:
        stamp = now.strftime("%Y-%m-%d %H:%M:%S") if now else ""
        connection.execute(
            "INSERT INTO ingest.source_health "
            "(source,last_success_at,last_attempt_at,status,latency_sec,items_last_run,note,consecutive_failures) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (source) DO UPDATE SET "
            "last_attempt_at=EXCLUDED.last_attempt_at, status=EXCLUDED.status, "
            "latency_sec=EXCLUDED.latency_sec, items_last_run=EXCLUDED.items_last_run, "
            "note=EXCLUDED.note, "
            "consecutive_failures=CASE WHEN EXCLUDED.status='ok' THEN 0 "
            "ELSE ingest.source_health.consecutive_failures+1 END, "
            "last_success_at=CASE WHEN EXCLUDED.status='ok' THEN EXCLUDED.last_success_at "
            "ELSE ingest.source_health.last_success_at END",
            (
                source,
                stamp if ok else None,
                stamp,
                "ok" if ok else "degraded",
                latency,
                items,
                note[:500],
                0 if ok else 1,
            ),
        )
    except Exception as exc:
        log.warning("health write failed %r", exc)
