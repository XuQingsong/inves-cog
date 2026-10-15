"""SEC submissions, earnings-event calendar and non-derivative Form 4 parsing."""

import re
from datetime import date, datetime, timezone
from html import unescape
from xml.etree import ElementTree

from inves_cog.ingest.http import SourceError, require_mapping
from inves_cog.ingest.market import NY, next_trading_day, regular_bounds, trading_day


def parse_acceptance_et(value):
    """Verified index Accepted wall time, never a submissions JSON timestamp."""
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is not None:
        raise ValueError("Index Accepted must be local Eastern time without a UTC suffix")
    return stamp.replace(tzinfo=NY).astimezone(timezone.utc)


def accepted_from_index(html):
    match = re.search(
        r"""<div[^>]*class=["']infoHead["'][^>]*>\s*Accepted\s*</div>\s*<div[^>]*class=["']info["'][^>]*>\s*([^<]+)""",
        html,
        re.I,
    )
    if match is None:
        raise SourceError("Official filing index Accepted field missing")
    try:
        return parse_acceptance_et(unescape(match.group(1)).strip())
    except (TypeError, ValueError):
        raise SourceError("Official filing index Accepted field malformed") from None


def earnings_event(filing, *, closes, clock):
    if filing.get("form") != "8-K" or "2.02" not in filing.get("items", []):
        return None
    accepted = filing.get("accepted_at")
    if accepted is None:
        raise SourceError("Earnings filing has no verified acceptance time")
    day = accepted.astimezone(NY).date()
    bounds = regular_bounds(day)
    if bounds is None:
        session, reaction = "closed", next_trading_day(day)
    elif accepted < bounds[0]:
        session, reaction = "pre", day
    elif accepted < bounds[1]:
        session, reaction = "intraday", day
    else:
        session, reaction = "post", next_trading_day(day)
    prior = [d for d in closes if d < reaction]
    return {
        "ticker": filing["ticker"],
        "accession": filing["accession"],
        "item": "2.02",
        "accepted_at": accepted,
        "session": session,
        "reaction_day": reaction,
        "ref_close": closes[max(prior)] if prior else None,
        "fiscal_period": filing.get("fiscal_period"),
        "fallback": False,
        "flags": [],
        "fetched_at": clock.now_utc(),
    }


def earnings_fallback(ticker, data, *, clock):
    day = date.fromisoformat(data["reportDate"])
    session = data.get("session")
    if session not in {None, "pre", "post"}:
        raise SourceError("Unsupported earnings-calendar session")
    reaction = None
    flags = ["earnings_event_fallback"]
    if session is None:
        flags.extend(["earnings_time_unknown", "earnings_event_time_unknown"])
    else:
        reaction = day if session == "pre" and trading_day(day) else next_trading_day(day)
    return {
        "ticker": ticker,
        "accession": None,
        "item": None,
        "accepted_at": None,
        "session": session,
        "reaction_day": reaction,
        "ref_close": None,
        "fiscal_period": None,
        "fallback": True,
        "flags": flags,
        "reported_date": day,
        "fetched_at": clock.now_utc(),
    }


def submissions_rows(data, *, ticker, clock):
    data = require_mapping(data)
    rows = data.get("filings", {}).get("recent", data)
    numbers = rows.get("accessionNumber")
    if not isinstance(numbers, list):
        raise SourceError("Malformed submissions: accessionNumber array absent")
    results = []
    for index, accession in enumerate(numbers):

        def value(key, index=index):
            values = rows.get(key, [])
            return values[index] if index < len(values) else None

        filed = value("filingDate")
        if not filed or filed < "2015-01-01":
            continue
        results.append(
            {
                "ticker": ticker,
                "cik": str(data.get("cik", "")),
                "accession": accession,
                "form": value("form"),
                "filing_date": date.fromisoformat(filed),
                "report_date": date.fromisoformat(value("reportDate")) if value("reportDate") else None,
                "accepted_at": None,
                "items": [part.strip() for part in (value("items") or "").split(",") if part.strip()],
                "primary_document": value("primaryDocument"),
                "is_xbrl": bool(value("isXBRL")),
                "is_inline_xbrl": bool(value("isInlineXBRL")),
                "fetched_at": clock.now_utc(),
                "raw": {
                    key: values[index]
                    for key, values in rows.items()
                    if isinstance(values, list) and index < len(values)
                },
            }
        )
    return results


def collect_submissions(client, *, cik, ticker, clock, existing=None, persist=None, verify_limit=None):
    data = client.submissions(cik)
    rows = submissions_rows(data, ticker=ticker, clock=clock)
    for historical in data.get("filings", {}).get("files", []):
        if historical.get("filingTo", "9999-12-31") < "2015-01-01":
            continue
        name = historical["name"]
        if "/" in name or ".." in name:
            raise SourceError("Unsafe historical submissions filename")
        older = client.get("https://data.sec.gov/submissions/" + name)
        for row in submissions_rows(older, ticker=ticker, clock=clock):
            row["cik"] = str(cik)
            rows.append(row)
    rows = list({row["accession"]: row for row in rows}.values())
    existing, checked = existing or {}, 0
    if persist:
        for row in rows:
            previous = existing.get(row["accession"])
            if previous and previous["raw"].get("accepted_index_source", {}).get("verified"):
                row["accepted_at"] = previous["accepted_at"]
                row["raw"]["accepted_index_source"] = previous["raw"]["accepted_index_source"]
            persist(row)
    for row in rows:
        from inves_cog.ingest.deadline import check

        check()
        previous = existing.get(row["accession"])
        if previous and previous["raw"].get("accepted_index_source", {}).get("verified"):
            row["accepted_at"] = previous["accepted_at"]
            row["raw"]["accepted_index_source"] = previous["raw"]["accepted_index_source"]
            continue
        if verify_limit is not None and checked >= verify_limit:
            continue
        checked += 1
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", row["accession"]) or not str(cik).isdigit():
            raise SourceError("Invalid SEC accession or CIK for filing index")
        accession = row["accession"]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}-index.html"
        evidence = {"url": url, "verified": False, "checked_at_utc": clock.now_utc().isoformat()}
        try:
            row["accepted_at"] = accepted_from_index(client.get(url))
            evidence.update(verified=True, accepted_at_utc=row["accepted_at"].isoformat())
        except (SourceError, TypeError, ValueError) as exc:
            # Keep the raw filing and a concrete retryable gap, with no event time.
            evidence.update(
                error_type=type(exc).__name__,
                http_status=getattr(exc, "status_code", None),
                gap="index_accepted_unavailable",
            )
        row["raw"]["accepted_index_source"] = evidence
        if persist:
            persist(row)
    return rows


def parse_form4(xml, *, accession, filed_at):
    root = ElementTree.fromstring(xml)

    def content(path, parent=root):
        found = parent.find(path)
        return found.text.strip() if found is not None and found.text else None

    owner = content(".//rptOwnerName")
    officer = content(".//isOfficer")
    rows = []
    for index, transaction in enumerate(root.findall(".//nonDerivativeTable/nonDerivativeTransaction")):

        def number(path, transaction=transaction):
            text = content(path, transaction)
            return float(text) if text is not None else None

        rows.append(
            {
                "ticker": content(".//issuerTradingSymbol"),
                "filed_at": filed_at,
                "insider_name": owner,
                "is_officer": None if officer is None else officer.lower() in {"1", "true"},
                "transaction_code": content("./transactionCoding/transactionCode", transaction),
                "shares": number("./transactionAmounts/transactionShares/value"),
                "price": number("./transactionAmounts/transactionPricePerShare/value"),
                "accession": accession,
                "transaction_index": index,
            }
        )
    return rows
