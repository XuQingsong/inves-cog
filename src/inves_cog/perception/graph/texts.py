"""SEC original-text extraction with stable positions in normalized filing text."""

import hashlib
import re

from lxml import html


def extract_sections(raw, *, filing, clock, source_url):
    document = html.fromstring(raw.encode() if isinstance(raw, str) else raw)
    for node in document.xpath("//script|//style|//*[local-name()='hidden']"):
        node.drop_tree()
    full = " ".join(" ".join(document.itertext()).split())
    codes = "4|3D|5" if filing["form"].startswith("20-F") else "1A|1|7"
    headings = list(re.finditer(r"\bItem\s+(" + codes + r")\s*[.\-:]?\s+", full, re.I))
    ranges = {}
    for match in headings:
        next_heading = re.search(r"\bItem\s+\d+[A-Z]?\s*[.\-:]?\s+", full[match.end() :], re.I)
        end = match.end() + next_heading.start() if next_heading else len(full)
        if end - match.start() > ranges.get(match[1].upper(), (0, 0))[1] - ranges.get(match[1].upper(), (0, 0))[0]:
            ranges[match[1].upper()] = (match.start(), end)
    for index, match in enumerate(
        re.finditer(r"\b(?:customer concentration|remaining performance obligations|revenue recognition)\b", full, re.I)
    ):
        ranges[f"note_{index}"] = (max(0, match.start() - 500), min(len(full), match.end() + 6000))
    if not ranges:
        ranges["filing"] = (0, len(full))
    digest = hashlib.sha256(raw.encode() if isinstance(raw, str) else raw).hexdigest()
    return [
        {
            "ticker": filing["ticker"],
            "accession": filing["accession"],
            "section": section,
            "text": full[start:end],
            "char_start": start,
            "char_end": end,
            "fetched_at": clock.now_utc(),
            "source_url": source_url,
            "source_sha256": digest,
        }
        for section, (start, end) in ranges.items()
    ]
