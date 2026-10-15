"""Download filing attachments through the injected shared SEC client."""

import re
from datetime import timedelta
from pathlib import Path

from inves_cog.ingest.fundamentals.segments import context_period, load_instance, numeric, parse_segments


class InstanceLoader:
    def __init__(self, *, sec, cache_dir, offline=False):
        self.sec, self.cache, self.offline = sec, Path(cache_dir), offline

    def path(self, filing):
        accession = filing["accession"]
        cik = str(filing["cik"])
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not cik.isdigit():
            raise ValueError("Unsafe filing identity")
        directory = self.cache / accession
        directory.mkdir(parents=True, exist_ok=True)
        marker = directory / "instance-path"
        if marker.exists():
            name = marker.read_text().strip()
            if Path(name).name == name and (directory / name).is_file():
                return directory / name
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
        listing = self.sec.get(base + "index.json")["directory"]["item"]
        names = [row["name"] for row in listing if Path(row["name"]).name == row["name"]]
        candidates = [name for name in names if name.endswith("_htm.xml") or name.endswith("_html.xml")]
        if not candidates:
            candidates = [
                name
                for name in names
                if name.endswith(".xml")
                and name not in {"FilingSummary.xml", "MetaLinks.xml"}
                and not name.endswith(("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))
            ]
        if not candidates and filing.get("is_inline_xbrl"):
            name = filing["primary_document"].rsplit("/", 1)[-1]
            if name in names:
                candidates = [name]
        if len(candidates) != 1:
            raise ValueError("Filing instance absent or ambiguous: " + accession)
        for name in names:
            if name == candidates[0] or name.endswith((".xml", ".xsd")):
                path = directory / name
                if not path.exists():
                    value = self.sec.get(base + name)
                    if not isinstance(value, str):
                        raise ValueError("Non-text filing attachment")
                    temporary = path.with_suffix(path.suffix + ".part")
                    temporary.write_text(value)
                    temporary.replace(path)
        marker.write_text(candidates[0] + "\n")
        return directory / candidates[0]

    def facts(self, filing):
        from inves_cog.ingest.fundamentals.repairs import dimension_allowed

        controller, model = load_instance(
            self.path(filing), offline=self.offline, cache_dir=self.cache / "taxonomy", fetch=self.sec.get
        )
        try:
            output = {"cik": filing["cik"], "facts": {}}
            for fact in model.factsInInstance:
                if fact.context is None or fact.unit is None or not dimension_allowed(fact, filing.get("ticker", "")):
                    continue
                value = numeric(fact)
                if value is None:
                    continue
                uri = fact.qname.namespaceURI
                tax = (
                    "us-gaap"
                    if "/us-gaap/" in uri
                    else "ifrs-full"
                    if "ifrs" in uri
                    else "dei"
                    if "/dei/" in uri
                    else None
                )
                if tax is None:
                    continue
                measures = fact.unit.measures
                numerator = "*".join(q.localName for q in measures[0])
                denominator = "*".join(q.localName for q in measures[1])
                unit = numerator + ("/" + denominator if denominator else "")
                context = fact.context
                if context.isInstantPeriod:
                    end = (context.instantDatetime - timedelta(days=1)).date()
                    start = None
                    length = None
                else:
                    start, end, length = context_period(context)
                if end is None:
                    continue
                row = {
                    "end": str(end),
                    "filed": str(filing["filing_date"]),
                    "val": value,
                    "accn": filing["accession"],
                    "form": filing["form"],
                    "fp": "FY" if length == "FY" else None,
                    "origin": "instance_parsed",
                }
                if context.qnameDims:
                    row["d9_only"] = True
                    row["dimensions"] = {str(axis): str(value.memberQname) for axis, value in context.qnameDims.items()}
                if start:
                    row["start"] = str(start)
                output["facts"].setdefault(tax, {}).setdefault(fact.qname.localName, {"units": {}})["units"].setdefault(
                    unit, []
                ).append(row)
            return output
        finally:
            model.close()
            controller.close()

    def segments(self, filing, *, ticker, fx=None):
        path = self.path(filing)
        primary = path.parent / "primary-original.html"
        name = filing.get("primary_document")
        if not primary.exists() and not self.offline and name:
            if Path(name).name != name:
                raise ValueError("Unsafe primary document")
            base = (
                f"https://www.sec.gov/Archives/edgar/data/{int(filing['cik'])}/{filing['accession'].replace('-', '')}/"
            )
            value = self.sec.get(base + name)
            if not isinstance(value, str):
                raise ValueError("Non-text primary filing")
            temporary = primary.with_suffix(".html.part")
            temporary.write_text(value)
            temporary.replace(primary)
        return parse_segments(
            path,
            ticker=ticker,
            accession=filing["accession"],
            filed=filing["filing_date"],
            offline=self.offline,
            cache_dir=self.cache / "taxonomy",
            fx=fx,
            fetch=self.sec.get,
            primary_html=primary.read_bytes() if primary.exists() else None,
        )
