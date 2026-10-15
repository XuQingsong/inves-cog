"""Known SEC 6-K layouts, through M1's sole rate-limited SEC client."""

import json
import re
from datetime import timedelta
from pathlib import Path

from inves_cog.ingest.fundamentals.extractors import IFRS, TAGS, day
from inves_cog.ingest.fundamentals.interims import parse_interim, parse_monthly
from inves_cog.ingest.fundamentals.repairs import merge_facts

ISSUERS = {"ASML", "TSM", "NOK", "ARM", "SKHY"}


def eligible(filing):
    name, ticker = filing["primary_document"].lower(), filing["ticker"]
    if ticker == "ASML":
        return "quarterly" in name
    if ticker == "TSM":
        return bool(re.match(r"tsm-\d{8}x6k\.htm", name)) or "revenue" in name
    return ticker in {"NOK", "ARM", "SKHY"}


class ForeignCollector:
    def __init__(self, *, sec, instance_loader, repository, as_of):
        self.sec, self.loader, self.repo, self.as_of = sec, instance_loader, repository, as_of
        self.cache = Path(instance_loader.cache) / "announcements"

    def get(self, filing, name):
        if Path(name).name != name:
            raise ValueError("Unsafe SEC exhibit filename")
        directory = self.cache / filing["accession"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        base = f"https://www.sec.gov/Archives/edgar/data/{int(filing['cik'])}/{filing['accession'].replace('-', '')}/"
        if not path.exists():
            value = self.sec.get(base + name)
            path.write_text(json.dumps(value) if isinstance(value, dict) else value)
        raw = path.read_text()
        return (json.loads(raw) if name == "index.json" else raw), base + name

    def exhibits(self, filing):
        ticker = filing["ticker"]
        if ticker in {"NOK", "SKHY"}:
            return [filing["primary_document"]]
        listing, _ = self.get(filing, "index.json")
        names = [r["name"] for r in listing["directory"]["item"]]
        if ticker == "ASML":
            return [n for n in names if "financial" in n and "us" in n and n.endswith(".htm")]
        if ticker == "TSM":
            return [n for n in names if "guidance" in n and n.endswith(".htm")]
        return [n for n in names if "exhibit992" in n and n.endswith(".htm")] or [filing["primary_document"]]

    def annual(self, filings):
        candidates = [
            f
            for f in filings
            if str(f["form"]).removesuffix("/A") in {"20-F", "40-F"} and day(f["filing_date"]) <= self.as_of
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda f: (day(f["filing_date"]), f["accession"]))
        # Persist the parsed original alongside the SEC cache, never in another
        # project's database. Older PIT cutoffs still filter each fact's filed.
        directory = self.cache / latest["accession"]
        path = directory / "annual-facts.json"
        if not path.exists():
            data = self.loader.facts(latest)
            directory.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        return json.loads(path.read_text())

    def collect(self, ticker, filings):
        rows, months, failures, checked = [], [], [], []
        first = self.as_of - timedelta(days=450)
        from inves_cog.ingest.deadline import check

        for filing in filings:
            check()
            if (
                str(filing["form"]).removesuffix("/A") != "6-K"
                or not first <= day(filing["filing_date"]) <= self.as_of
                or not eligible(filing)
            ):
                continue
            checked.append({key: str(filing.get(key)) for key in ["form", "filing_date", "accession"]})
            try:
                if ticker == "TSM" and "revenue" in filing["primary_document"].lower():
                    raw, _ = self.get(filing, filing["primary_document"])
                    row = parse_monthly(raw, accession=filing["accession"], filed=filing["filing_date"])
                    self.repo.put_monthly(row)
                    months.append(row)
                    continue
                for name in self.exhibits(filing):
                    raw, url = self.get(filing, name)
                    if ticker in {"NOK", "SKHY"} and not any(
                        term in raw
                        for term in [
                            "Consolidated income statement",
                            "Preliminary Results of Operations",
                            "interim consolidated financial statements",
                        ]
                    ):
                        continue
                    parsed = parse_interim(
                        raw,
                        ticker=ticker,
                        accession=filing["accession"],
                        filed=filing["filing_date"],
                        source_exhibit=url,
                    )
                    for row in parsed:
                        self.repo.put_interim(row)
                    rows.extend(parsed)
            except Exception as exc:
                failures.append({"accession": filing["accession"], "reason": type(exc).__name__ + ": " + str(exc)})
        return {"ticker": ticker, "rows": rows, "months": months, "failures": failures, "checked": checked}

    def annual_data(self, data, filings):
        annuals = [
            f
            for f in filings
            if str(f["form"]).removesuffix("/A") in {"20-F", "40-F"} and day(f["filing_date"]) <= self.as_of
        ]
        latest = max(annuals, key=lambda f: (day(f["filing_date"]), f["accession"]), default=None)
        target = latest.get("report_date") if latest else None
        if target:
            for taxonomy, names in [("ifrs-full", IFRS["rev"]), ("us-gaap", TAGS["rev"])]:
                for tag in names:
                    for rows in data.get("facts", {}).get(taxonomy, {}).get(tag, {}).get("units", {}).values():
                        if any(
                            r.get("start")
                            and day(r["end"]) == day(target)
                            and 350 <= (day(r["end"]) - day(r["start"])).days <= 380
                            and day(r["filed"]) <= self.as_of
                            for r in rows
                        ):
                            return data
        if latest and self.as_of < day(latest["filing_date"]) + timedelta(days=3):
            return data
        parsed = self.annual(filings)
        return merge_facts(data, parsed) if parsed else data
