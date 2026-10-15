"""SEC text blocks with real heading boundaries and stable normalized positions."""

import hashlib
import re

from lxml import html

CAPTIONS = (
    r"Business\b|Risk\s*Facto\s*r\s*s\b|Management[’']s\s+Discussion\b|"
    r"Financial\s+Statements\b|Properties\b|Legal\s+Proceedings\b|Unresolved\b|"
    r"Mine\s+Safety\b|Market\s+for\b|Selected\s+Financial\b|Quantitative\s+and\b|"
    r"Changes\s+in\b|Controls\s+and\b|Other\s+Information\b|Disclosure\b|"
    r"Information\s+on\s+the\s+Company\b|Operating\s+and\s+Financial\b|Key\s+Information\b"
)
HEADING = re.compile(r"^Item\s+(\d{1,2}[A-Z]?)\s*[.\-:]?\s*(?:" + CAPTIONS + r")", re.I)


def normalized_text(document):
    pieces, spans = [], {}
    position = 0

    def append(text):
        nonlocal position
        value = " ".join((text or "").split())
        if value:
            if pieces:
                position += 1
            pieces.append(value)
            position += len(value)

    def walk(node):
        if not isinstance(node.tag, str):
            return
        first = position + (1 if pieces else 0)
        append(node.text)
        for child in node:
            walk(child)
            append(child.tail)
        if position >= first:
            spans[node] = (first, position)

    walk(document)
    return " ".join(pieces), spans


def heading_ranges(document, full, spans, form):
    headings = {}
    for node, (start, end) in spans.items():
        if not isinstance(node.tag, str) or end - start > 250:
            continue
        if node.tag.lower() not in {"p", "div", "span", "h1", "h2", "h3", "h4", "b", "strong", "td"}:
            continue
        ancestors = list(node.iterancestors())
        if any(a.tag == "a" for a in ancestors):
            continue
        paragraph = next((a for a in ancestors if a.tag == "p"), None)
        if paragraph is not None and paragraph in spans:
            a, b = spans[paragraph]
            if not HEADING.match(full[a:b]):
                continue
        match = HEADING.match(full[start:end])
        if match:
            code = match[1].upper()
            headings[code] = max(headings.get(code, -1), start)
    positions = sorted(set(headings.values()))
    wanted = {"4", "3D", "5"} if form.startswith("20-F") else {"1", "1A", "7"}
    return {
        code: (start, next((p for p in positions if p > start), len(full)))
        for code, start in headings.items()
        if code in wanted
    }


def extract_sections(raw, *, filing, clock, source_url):
    parsed = re.sub(r"^\s*<\?xml[^>]*\?>", "", raw, count=1) if isinstance(raw, str) else raw
    document = html.fromstring(parsed)
    for node in document.xpath("//script|//style|//*[local-name()='hidden']"):
        node.drop_tree()
    full, spans = normalized_text(document)
    ranges = heading_ranges(document, full, spans, filing["form"])
    # A complete canonical source makes every quoted position independently resolvable.
    ranges["full_filing"] = (0, len(full))
    for index, match in enumerate(
        re.finditer(r"\b(?:customer concentration|remaining performance obligations|revenue recognition)\b", full, re.I)
    ):
        ranges[f"note_{index}"] = (max(0, match.start() - 500), min(len(full), match.end() + 6000))
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
