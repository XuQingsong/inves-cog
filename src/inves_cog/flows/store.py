"""Raw-file archiving + polite HTTP + upserts for flows.* tables."""

import gzip
import hashlib
import logging
from pathlib import Path

from inves_cog.ingest.http import HTTPClient

DEFAULT_RAW = Path("/home/claudeuser/inves-cog-data/flows/raw")


def polite_http(**kw):
    return HTTPClient(retries=2, timeout=30, send=kw.get("send"))


def save_raw(raw_dir, source, url, period, content, connection=None):
    """gzip original bytes to raw/<source>/<yyyy-mm-dd>/<file>, record raw_files row."""
    sha = hashlib.sha256(content).hexdigest()
    day = period[:10] if isinstance(period, str) else str(period)
    folder = Path(raw_dir) / source / day
    folder.mkdir(parents=True, exist_ok=True)
    ext = ".gz" if not content.endswith(b"\x1f\x8b") else ""
    name = folder / f"{sha[:16]}{ext}"
    if not name.exists():
        name.write_bytes(gzip.compress(content) if not ext else content)
    row_id = None
    if connection is not None:
        r = connection.execute(
            "INSERT INTO flows.raw_files (source,url,period,sha256,path,bytes) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING raw_file_id",
            (source, url, str(period), sha, str(name), len(content)),
        ).fetchone()
        row_id = r["raw_file_id"] if r else None
    return {"sha256": sha, "path": str(name), "raw_file_id": row_id, "bytes": len(content)}


def upsert_many(connection, table, cols, rows, conflict=""):
    """Simple executemany upsert; returns count written."""
    n = 0
    for row in rows:
        connection.execute(
            f"INSERT INTO flows.{table} ({','.join(cols)}) "
            f"VALUES ({','.join('%s' for _ in cols)}) ON CONFLICT DO NOTHING",
            tuple(row.get(c) for c in cols),
        )
        n += 1
    logging.getLogger(__name__).info("flows.%s upserted %d rows", table, n)
    return n


def record_health(connection, source, status, detail=""):
    try:
        connection.execute(
            "INSERT INTO ingest.source_health (source, status, detail, checked_at) VALUES (%s,%s,%s,now())",
            (source, status, detail),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("health write failed %r", exc)
