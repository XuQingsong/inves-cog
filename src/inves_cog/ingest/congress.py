"""House PTR (Periodic Transaction Report) index, download and parsing.

Index: annual FD zip (tab-separated FD.txt), FilingType=P rows.
PDFs: /public_disc/ptr-pdfs/{year}/{DocID}.pdf fetched serially —
>=20s between requests, at most `max_per_run` per run, and the run
backs off on the first stalled connection. Scanned filings keep
metadata only and are marked scanned_unparsed.
"""

import csv
import hashlib
import io
import json
import re
import time
import zipfile

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

# House PTR transaction types (STOCK Act form): P purchase, S sale,
# S (partial) sale, E exchange. B/E variants appear in older filings.
BUY_TYPES = {"P"}
SELL_TYPES = {"S", "S (partial)"}


def parse_index_text(text):
    """FD.txt is tab-separated; keep only FilingType=P (periodic reports)."""
    out = []
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        if (row.get("FilingType") or "").strip() != "P":
            continue
        doc_id = (row.get("DocID") or "").strip()
        if not doc_id:
            continue
        first = (row.get("First") or "").strip()
        last = (row.get("Last") or "").strip()
        member = f"{first} {last}".strip() or last or doc_id
        m, d, y = (row.get("FilingDate") or "").strip().split("/")
        out.append(
            {
                "doc_id": doc_id,
                "member": member,
                "state_dst": (row.get("StateDst") or "").strip() or None,
                "filing_date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}",
            }
        )
    return out


def collect_index(connection, http, year):
    """Fetch the annual FD zip and enqueue new DocIDs as pending rows."""
    from inves_cog.ingest.http import SourceError

    raw = http.get(INDEX_URL.format(year=year))
    if isinstance(raw, str):
        raise SourceError("House FD index response is not a zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        rows = parse_index_text(zf.read(name).decode("utf-8", "replace"))
    added = 0
    for r in rows:
        cur = connection.execute(
            """
            INSERT INTO ingest.congress_ptr (doc_id, filing_date, member, state_dst, source_url)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (doc_id) DO NOTHING
            """,
            (r["doc_id"], r["filing_date"], r["member"], r["state_dst"], PDF_URL.format(year=year, doc_id=r["doc_id"])),
        )
        added += cur.rowcount or 0
    return {"indexed": len(rows), "enqueued": added}


_TXN_LINE = re.compile(
    r"^(?P<owner>SP|JT|DC|CH)?\s*(?P<type>P|S(?: \(partial\))?|E|B)\s+"
    r"(?P<d1>\d{2}/\d{2}/\d{4})\s*(?P<d2>\d{2}/\d{2}/\d{4})\s*"
    r"(?P<amount>\$[\d,]+\s*-\s*\n?\s*\$[\d,]+|Over \$[\d,]+|\$[\d,]+)",
    re.M,
)
_ASSET = re.compile(
    r"^(?:SP|JT|DC|CH)?\s*(?P<asset>.+?)\s*\((?P<ident>[^)]*)\)\s*\[(?P<kind>[A-Z]+)\]\s*$", re.M | re.S
)
# Section/footer lines that separate the asset block of one row from the
# previous row or the table header inside a PTR page.
_BOUNDARY = re.compile(
    r"^(?:F\s+S:|S\s+O:|I\s+V|L\s*:|\*\s|ID\s+Owner|Cap\.|Gains|Notification|Date$|\$200|.*>$|.*:\s*$)"
)


def _money(text):
    m = re.findall(r"\$([\d,]+)", text)
    if not m:
        return None, None
    low = int(m[0].replace(",", ""))
    high = int(m[1].replace(",", "")) if len(m) > 1 else None
    return low, high


def parse_ptr(pdf_bytes):
    """Parse one electronic PTR. Returns dict with member fields and
    transactions, or None when the PDF carries no extractable text
    (scanned) or pypdf is unavailable/fails."""
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        text = text.replace("\x00", "")
    except Exception:
        return None
    if "Filing ID" not in text or "Name:" not in text:
        return None
    name = re.search(r"Name:\s*(.+)", text)
    district = re.search(r"State/District:\s*(\S+)", text)
    doc_id = re.search(r"Filing ID\s*#(\d+)", text)
    transactions = []
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines):
        m = _TXN_LINE.match(ln)
        if not m:
            continue
        ident, asset = None, None
        prev = lines[max(0, i - 8) : i]
        start = 0
        for j in range(len(prev) - 1, -1, -1):
            if _BOUNDARY.match(prev[j]):
                start = j + 1
                break
        window = "\n".join(prev[start:])
        found = list(_ASSET.finditer(window))
        if found:
            a = found[-1]
            asset = re.sub(r"\s+", " ", a.group("asset")).strip()
            ident = a.group("ident").strip()
        amount = m.group("amount")
        if (amount.rstrip().endswith("-") or ln.rstrip().endswith("-")) and i + 1 < len(lines):
            amount = amount + " " + lines[i + 1]
        low, high = _money(amount)
        transactions.append(
            {
                "owner": m.group("owner"),
                "asset": asset,
                "ticker": ident if ident and re.fullmatch(r"[A-Z.]{1,6}", ident) else None,
                "cusip": ident if ident and re.fullmatch(r"[0-9A-Z]{8,9}", ident) else None,
                "txn_type": m.group("type"),
                "txn_date": _mdy(m.group("d1")),
                "notification_date": _mdy(m.group("d2")),
                "amount_low": low,
                "amount_high": high,
            }
        )
    return {
        "doc_id": doc_id.group(1) if doc_id else None,
        "member": name.group(1).strip() if name else None,
        "state_dst": district.group(1) if district else None,
        "transactions": transactions,
    }


def _mdy(text):
    m, d, y = text.split("/")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def collect_pending(connection, http, *, spacing_seconds=20, max_per_run=30, sleep=time.sleep):
    """Download and parse pending PTR rows serially. Stops the run on the
    first stalled/failed fetch so the rest wait for the next cycle."""
    pending = connection.execute(
        "SELECT doc_id, source_url, filing_date FROM ingest.congress_ptr"
        " WHERE parse_status='pending' ORDER BY filing_date LIMIT %s",
        (max_per_run,),
    ).fetchall()
    done = {"downloaded": 0, "parsed": 0, "scanned_unparsed": 0, "stopped": False}
    for i, row in enumerate(pending):
        if i:
            sleep(spacing_seconds)
        try:
            pdf = http.get(row["source_url"], timeout=30)
        except Exception as exc:
            connection.execute(
                "UPDATE ingest.congress_ptr SET parse_status='download_failed', parse_note=%s WHERE doc_id=%s",
                (f"{type(exc).__name__}: {exc}"[:300], row["doc_id"]),
            )
            done["stopped"] = True
            break
        if isinstance(pdf, str) or not pdf.startswith(b"%PDF"):
            connection.execute(
                "UPDATE ingest.congress_ptr SET parse_status='download_failed',"
                " parse_note='non-pdf response' WHERE doc_id=%s",
                (row["doc_id"],),
            )
            done["stopped"] = True
            break
        done["downloaded"] += 1
        parsed = parse_ptr(pdf)
        if parsed is None:
            status, note, txns = "scanned_unparsed", "扫描件或提取失败，未解析", "[]"
            done["scanned_unparsed"] += 1
        else:
            status, note, txns = "parsed", None, json.dumps(parsed["transactions"], ensure_ascii=False)
            done["parsed"] += 1
        connection.execute(
            """
            UPDATE ingest.congress_ptr
            SET pdf_sha256=%s, fetched_at=now(), parse_status=%s, parse_note=%s, transactions=%s::jsonb
            WHERE doc_id=%s
            """,
            (hashlib.sha256(pdf).hexdigest(), status, note, txns, row["doc_id"]),
        )
    return done
