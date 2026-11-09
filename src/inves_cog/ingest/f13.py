"""Form 13F DERA dataset loading (perception-side data layer).

Streams the quarterly/rolling-window zip: joins SUBMISSION (filing_date,
period, cik), COVERPAGE (amendment fields, filer name), then streams the
multi-GB INFOTABLE keeping only rows whose CUSIP is in cusip_map.

Read semantics live in the migration comment: every filed row is kept;
visible row = greatest filing_date per (filer_cik, period, ticker).
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "config/data/f13_cusip_map.json"


def seed_map() -> dict[str, str]:
    """cusip -> ticker from the bundled, source-recorded seed file."""
    return {r["cusip"]: r["ticker"] for r in json.loads(SEED.read_text())}


def _member(zf: zipfile.ZipFile, name: str) -> str:
    """Some packages nest TSVs under a folder — resolve by suffix."""
    for member in zf.namelist():
        if member.endswith(name):
            return member
    raise KeyError(name)


def _index(zf: zipfile.ZipFile, name: str) -> dict[str, dict[str, str]]:
    """Load a small TSV member into {accession: row}."""
    with zf.open(_member(zf, name)) as fh:
        lines = io.TextIOWrapper(fh, encoding="utf-8")
        header = lines.readline().rstrip("\r\n").split("\t")
        out = {}
        for line in lines:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < len(header):
                parts += [""] * (len(header) - len(parts))
            row = dict(zip(header, parts, strict=False))
            if row.get("ACCESSION_NUMBER"):
                out[row["ACCESSION_NUMBER"]] = row
        return out


def _date(text: str) -> str | None:
    """DERA dates arrive as '30-JUN-2026'; emit ISO."""
    if not text:
        return None
    from datetime import datetime

    return datetime.strptime(text.strip(), "%d-%b-%Y").date().isoformat()


def load_dataset(
    zip_path: Path,
    cusips: dict[str, str] | set[str],
    connection=None,
) -> dict:
    """Stream INFOTABLE, keep mapped CUSIPs only.

    Returns counters; when `connection` is given, upserts rows into
    ingest.f13_holdings via executemany. Always reports scanned/kept/misses.
    """
    ticker_of = cusips if isinstance(cusips, dict) else {c: None for c in cusips}
    stats = {"scanned": 0, "kept": 0, "rows": []}

    with zipfile.ZipFile(zip_path) as zf:
        sub = _index(zf, "SUBMISSION.tsv")
        cov = _index(zf, "COVERPAGE.tsv")
        with zf.open(_member(zf, "INFOTABLE.tsv")) as fh:
            lines = io.TextIOWrapper(fh, encoding="utf-8")
            header = lines.readline().rstrip("\r\n").split("\t")
            for line in lines:
                stats["scanned"] += 1
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) < len(header):
                    continue
                row = dict(zip(header, parts, strict=False))
                cusip = (row.get("CUSIP") or "").upper()
                if cusip not in ticker_of:
                    continue
                acc = row["ACCESSION_NUMBER"]
                s = sub.get(acc) or {}
                c = cov.get(acc) or {}
                stats["rows"].append(
                    {
                        "accession": acc,
                        "infotable_sk": int(row["INFOTABLE_SK"]),
                        "filer_cik": s.get("CIK", ""),
                        "filer_name": c.get("FILINGMANAGER_NAME"),
                        "period": _date(s.get("PERIODOFREPORT")),
                        "filing_date": _date(s.get("FILING_DATE")),
                        "is_amendment": (c.get("ISAMENDMENT") or "").upper() == "Y",
                        "amendment_type": c.get("AMENDMENTTYPE") or None,
                        "cusip": cusip,
                        "ticker": ticker_of.get(cusip),
                        "shares": int(row["SSHPRNAMT"]) if row.get("SSHPRNAMT") else None,
                        "value": int(row["VALUE"]) if row.get("VALUE") else None,
                        "put_call": row.get("PUTCALL") or None,
                    }
                )
                stats["kept"] += 1

    if connection is not None and stats["rows"]:
        cols = [
            "accession",
            "infotable_sk",
            "filer_cik",
            "filer_name",
            "period",
            "filing_date",
            "is_amendment",
            "amendment_type",
            "cusip",
            "ticker",
            "shares",
            "value",
            "put_call",
        ]
        sql = (
            f"INSERT INTO ingest.f13_holdings ({','.join(cols)}) VALUES "
            f"({','.join('%s' for _ in cols)}) "
            "ON CONFLICT (accession, infotable_sk) DO NOTHING"
        )
        with connection.cursor() as cur:
            cur.executemany(sql, [tuple(r[c] for c in cols) for r in stats["rows"]])
    stats["rows"] = len(stats["rows"])
    return stats


def visible_holdings(rows: list[dict]) -> dict[tuple, dict]:
    """Reduce filed rows to the visible row per (filer_cik, period, ticker).

    RESTATEMENT amendments supersede original rows (same key, later
    filing_date); NEW HOLDINGS adds keys absent from the original filing.
    Later filing_date always wins for the same key.
    """
    best: dict[tuple, dict] = {}
    for r in rows:
        key = (r["filer_cik"], r["period"], r["ticker"])
        cur = best.get(key)
        if cur is None or (r["filing_date"], r["accession"]) > (cur["filing_date"], cur["accession"]):
            best[key] = r
    return best
