"""Official S&P announcement facts; standalone HTML parsing without new dependencies."""

import re
from datetime import datetime
from html.parser import HTMLParser


class AnnouncementHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.text, self.links = [], [], []
        self.row, self.cell, self.anchor = None, None, None
        self.hidden = 0
        self.spans = {}
        self.cell_span = (1, 1)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag == "table":
            self.spans = {}
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
            self.cell_span = (int(attrs.get("rowspan", 1)), int(attrs.get("colspan", 1)))
        elif tag == "a":
            self.anchor = [attrs.get("href", ""), []]

    def handle_data(self, data):
        if self.hidden:
            return
        if data.strip():
            self.text.append(data.strip())
            if self.cell is not None:
                self.cell.append(data.strip())
            if self.anchor is not None:
                self.anchor[1].append(data.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("td", "th"):
            if self.row is not None and self.cell is not None:
                self.row.append((" ".join(self.cell), *self.cell_span))
            self.cell = None
        elif tag == "tr":
            if self.row:
                grid = {column: value for column, (value, remaining) in self.spans.items()}
                spans = {
                    column: (value, remaining - 1) for column, (value, remaining) in self.spans.items() if remaining > 1
                }
                column = 0
                for value, rowspan, colspan in self.row:
                    while column in grid:
                        column += 1
                    for c in range(column, column + colspan):
                        grid[c] = value
                        if rowspan > 1:
                            spans[c] = (value, rowspan - 1)
                    column += colspan
                self.spans = spans
                self.rows.append([grid.get(c, "") for c in range(max(grid) + 1)])
            self.row = None
        elif tag == "a":
            if self.anchor:
                self.links.append((self.anchor[0], " ".join(self.anchor[1])))
            self.anchor = None


def effective_date(text):
    for pattern in ("%d-%b-%y", "%d-%b-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.strip(), pattern).date().isoformat()
        except ValueError:
            pass
    months = {
        "Jan": "January",
        "Feb": "February",
        "Mar": "March",
        "Apr": "April",
        "Jun": "June",
        "Jul": "July",
        "Aug": "August",
        "Sep": "September",
        "Sept": "September",
        "Oct": "October",
        "Nov": "November",
        "Dec": "December",
    }
    for abbreviated, full in months.items():
        text = re.sub(r"\b" + abbreviated + r"\.?(?=\s)", full, text, flags=re.I)
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*,?\s*(\d{4})",
        text,
        re.I,
    )
    if match:
        return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date().isoformat()
    return None


def company_ticker(company, text):
    company = re.sub(r"\s+(?:Inc|Corp|Corporation|Co|Ltd|Limited|plc|Company|Holdings)\.?$", "", company, flags=re.I)
    text = text.replace("\u2011", "-").replace("\u2010", "-")
    name = re.escape(company).replace(r"\ ", r"\s+")
    suffix = (
        r"(?:\s*,?\s*(?:Inc|Corp|Corporation|Co|Ltd|Limited|plc|Company|Holdings|Group|Bank|&\s+Associates)\.?){0,3}"
    )
    exchange = r"\s*\((?:NYSE|NASD|NASDAQ|NYSE\s+American)\s*:\s*([A-Z][A-Z0-9.\-]*)"
    match = re.search(r"(?<!\w)" + name + r"(?!\w)" + suffix + exchange, text, re.I)
    return match.group(1).upper() if match else None


def parse_announcement(html, url):
    parsed = AnnouncementHTML()
    parsed.feed(html)
    text = " ".join(parsed.text)
    active, day, previous_action, headers = False, None, None, []
    result = []
    modern_day = None
    for row in parsed.rows:
        joined = " ".join(row)
        if any(c.lower() == "effective date" for c in row) and any(c.lower() == "ticker" for c in row):
            headers = [c.lower() for c in row]
            modern_day = None
            continue
        if "effective date" in headers and len(row) == len(headers):
            index_name = row[headers.index("index name")]
            if not re.fullmatch(r"S&P\s*500", index_name.strip(), re.I):
                continue
            date_value = effective_date(row[headers.index("effective date")]) or modern_day
            modern_day = date_value
            action_value = row[headers.index("action")].lower()
            action_value = {"addition": "added", "deletion": "deleted", "added": "added", "deleted": "deleted"}.get(
                action_value
            )
            if date_value and action_value:
                name_column = "company name" if "company name" in headers else "company"
                result.append(
                    dict(
                        ticker=row[headers.index("ticker")],
                        company=row[headers.index(name_column)],
                        action=action_value,
                        effective=date_value,
                        classification=row[-1],
                        source=url,
                    )
                )
            continue
        if re.search(r"S&P\s+(?:(?:MIDCAP\s+)?500|MIDCAP\s+400|SMALLCAP\s+600|100)\s*(?:INDEX)?\s*[–—-]", joined, re.I):
            active = bool(re.search(r"S&P\s+(?:MIDCAP\s+)?500\b", joined, re.I))
            day = effective_date(joined)
            previous_action = None
            headers = []
            continue
        if not active or day is None:
            continue
        if any(c.upper() == "COMPANY" for c in row):
            headers = [c.lower() for c in row]
            continue
        action = next((c.lower() for c in row if c.upper() in {"ADDED", "DELETED"}), None)
        if action:
            previous_action = action
        else:
            action = previous_action
        if not action or not any(row):
            continue
        if headers and "ticker" in headers and len(row) == len(headers):
            company = row[headers.index("company")]
            ticker = row[headers.index("ticker")]
        else:
            company = row[1] if len(row) >= 4 else row[0] if len(row) == 3 else ""
            ticker = company_ticker(re.sub(r"\s*\([^)]*\)", "", company), text) if company else None
        if not company or company.startswith("*") or company.upper() in {"ADDED", "DELETED", "COMPANY"}:
            continue
        result.append(
            dict(ticker=ticker, company=company, action=action, effective=day, classification=row[-1], source=url)
        )
    return result


def is_member(events, day):
    ordered = sorted(events, key=lambda row: row["effective"])
    if not ordered:
        return None
    active = ordered[0]["action"] == "deleted"
    for row in ordered:
        if row["effective"] > str(day):
            break
        active = row["action"] == "added"
    return active
