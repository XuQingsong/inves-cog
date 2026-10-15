"""Issuer-specific SEC announcement layouts; no statistical/LLM extraction."""

import calendar
import re
from datetime import date
from functools import lru_cache

FIELDS = ("revenue", "gross_profit", "operating_income", "net_income", "eps_diluted")
MONTHS = {name.lower()[:3]: n for n, name in enumerate(calendar.month_name) if n}
NUMBER = r"\(?\s*[+-]?\d[\d,]*(?:\.\d+)?\s*\)?|[—–]"


def text(node):
    return " ".join(node.itertext()).replace("\xa0", " ")


def amount(value):
    value = re.sub(r"[\s,$]", "", value)
    if value in {"—", "–", "-", ""}:
        return None
    return -float(value[1:-1]) if value.startswith("(") else float(value)


def numbers(value):
    return [amount(v) for v in re.findall(NUMBER, value)]


def quarter(token):
    match = re.fullmatch(r"([1-4])Q(\d{2})", token)
    q, year = int(match[1]), 2000 + int(match[2])
    month = q * 3
    return date(year, month, calendar.monthrange(year, month)[1])


def table_rows(document):
    for table in document.xpath("//table[not(.//table)]"):
        rows = []
        for tr in table.xpath(".//tr"):
            cells = [text(td).strip() for td in tr.xpath("./td|./th")]
            if cells:
                rows.append(cells)
        yield rows


def labelled(rows, label):
    for cells in rows:
        if re.fullmatch(label, cells[0], re.I):
            return numbers(" ".join(cells[1:]))
    raise ValueError("Missing statement row: " + label)


def assemble(ends, values, currency, *, indexes=None, scale=1e6):
    output = []
    for pos, end in enumerate(ends):
        index = indexes[pos] if indexes else pos
        row = {"period_end": end, "currency": currency}
        for key in FIELDS:
            value = values[key][index]
            row[key] = value * (scale if key != "eps_diluted" else 1) if value is not None else None
        output.append(row)
    return output


def asml(document):
    content = text(document)
    matches = list(re.finditer(r"Three months ended\s+((?:[A-Z][a-z]{2}\s+\d{1,2},\s*){5})", content))
    if not matches or "€, in millions" not in content:
        raise ValueError("ASML five-quarter EUR summary header missing")
    match = next((m for m in matches if "Total net sales" in content[m.end() : m.end() + 1500]), None)
    if match is None:
        raise ValueError("ASML quarterly statement rows missing")
    section = content[match.end() :]
    years = re.search(r"(20\d{2})\s+(20\d{2})\s+(20\d{2})\s+(20\d{2})\s+(20\d{2})", section)
    dates = re.findall(r"([A-Z][a-z]{2})\s+(\d{1,2}),", match[1])
    ends = [date(int(y), MONTHS[m.lower()], int(d)) for (m, d), y in zip(dates, years.groups(), strict=True)]
    labels = dict(
        zip(
            FIELDS,
            [
                "Total net sales",
                "Gross profit",
                "Income from operations",
                "Net income",
                "Diluted net income per ordinary share",
            ],
            strict=True,
        )
    )
    values = {}
    for key, label in labels.items():
        found = re.search(re.escape(label) + r"\s+((?:" + NUMBER + r"\s*){5})", section)
        if not found:
            raise ValueError("ASML missing row: " + label)
        values[key] = numbers(found[1])
    return assemble(ends, values, "EUR")


def tsm(document):
    for rows in table_rows(document):
        header = " ".join(" ".join(r) for r in rows[:3])
        periods = re.findall(r"\b[1-4]Q\d{2}\b", header)
        if len(periods) != 3 or not any("Gross profit" in r[0] for r in rows):
            continue
        labels = ["Net sales", "Gross profit", "Income from operations", "Net income", r"EPS \(NT\$\)"]
        values = {key: labelled(rows, label) for key, label in zip(FIELDS, labels, strict=True)}
        return assemble([quarter(p) for p in periods], values, "TWD", indexes=[0, 1, 3])
    raise ValueError("TSM reported quarterly NT$ million table missing")


def grouped(value, count, expected=None):
    """Resolve Nokia's space-separated thousands only when column count is unique."""
    tokens = re.findall(r"\([^)]*\)|[—–]|[+-]?\d+(?:\.\d+)?", value)

    @lru_cache(None)
    def partitions(pos, remaining):
        if remaining == 0:
            return [()] if pos == len(tokens) else []
        if len(tokens) - pos < remaining:
            return []
        options = []
        for end in range(pos + 1, min(len(tokens) - remaining + 1, pos + 3) + 1):
            group = tokens[pos:end]
            if len(group) > 1 and (
                not re.fullmatch(r"[1-9]\d{0,2}", group[0]) or any(not re.fullmatch(r"\d{3}", v) for v in group[1:])
            ):
                continue
            try:
                number = amount("".join(group))
            except ValueError:
                continue
            options.extend((number, *tail) for tail in partitions(end, remaining - 1))
        return options

    answers = partitions(0, count)
    if expected is not None:
        answers = [
            row
            for row in answers
            if all(
                v is not None and (target is None or abs(v - target) <= 1.5)
                for v, target in zip(row, expected, strict=True)
            )
        ]
    if len(answers) != 1:
        raise ValueError("NOK ambiguous numeric columns: " + value)
    return list(answers[0])


def nok(document):
    content = " ".join(text(document).split())
    start = content.find("Consolidated income statement (condensed)")
    if start < 0:
        raise ValueError("NOK reported income statement missing")
    section = content[start:].split("Consolidated statement of comprehensive", 1)[0]
    header = section.split("Net sales", 1)[0]
    tokens = re.findall(r"(?<![\w-])Q([1-4])['’](\d{2})", header)
    if len(tokens) < 2:
        raise ValueError("NOK quarterly header missing")
    count = len(re.findall(r"(?:Q[1-4]|Q1-Q[1-4])['’]\d{2}", header))

    def row(label, expected=None):
        match = re.search(label + r"\s+([()\d\s,.’—–+\-]+)", section)
        if not match:
            raise ValueError("NOK missing row: " + label)
        return grouped(match[1], count, expected)

    revenue = row(r"Net sales\s+2,\s*[45]")
    gross = row(r"Gross profit\s+2")
    rd = row("Research and development expenses")
    selling = row(r"Selling, general and administrative expenses(?:\(1\))?")
    other = row(r"Other operating income and expenses(?:\(1\))?")
    op = row(
        r"Operating (?:\(loss\)/profit|profit(?:⁽¹⁾)?)\s+2",
        [sum(v) for v in zip(gross, rd, selling, other, strict=True)],
    )
    associates = row("Share of results of associates and joint ventures")
    financial = row(r"Financial income and expenses(?:\(1\))?")
    before_tax = row("Profit before tax", [sum(v) for v in zip(op, associates, financial, strict=True)])
    tax = row(r"Income tax expense\s+\d+")
    continuing = row("Profit from continuing operations", [a + b for a, b in zip(before_tax, tax, strict=True)])
    discontinued = row(r"(?:Loss|Profit/\(loss\)) from discontinued operations\s+\d+")
    group_profit = row(
        "Profit for the period",
        [a + b if b is not None else a for a, b in zip(continuing, discontinued, strict=True)],
    )
    noncontrol = row("Non-controlling interests")
    parent = row("Equity holders of the parent", [a - b for a, b in zip(group_profit, noncontrol, strict=True)])
    diluted = section.split("Diluted earnings per share, EUR", 1)[1]
    eps = grouped(re.search(r"Profit for the period\s+([()\d\s.,—–+\-]+)", diluted)[1], count)
    values = dict(zip(FIELDS, [revenue, gross, op, parent, eps], strict=True))
    output = assemble([quarter(q + "Q" + y) for q, y in tokens[:2]], values, "EUR", indexes=[0, 1])
    if tokens[0][0] == "2":
        for index, year in [(0, tokens[0][1]), (1, tokens[1][1])]:
            derived = {key: [values[key][index + 2] - values[key][index]] for key in FIELDS}
            output.extend(
                dict(row, derivation="ytd6_minus_q2") for row in assemble([quarter("1Q" + year)], derived, "EUR")
            )
    return output


def arm(document):
    for rows in table_rows(document):
        content = " ".join(" ".join(row) for row in rows)
        match = re.search(r"Three Months Ended\s+(\w+)\s+(\d{1,2}),?\s+(20\d{2})\s+(20\d{2})", content, re.I)
        if not match or not any("Gross profit" in row[0] for row in rows):
            continue
        ends = [date(int(y), MONTHS[match[1].lower()[:3]], int(match[2])) for y in match.groups()[2:]]
        labels = [
            r"Total revenue",
            r"Gross profit \(loss\)",
            r"Operating income \(loss\)",
            r"Net income \(loss\)",
            "Diluted",
        ]
        values = {key: labelled(rows, label) for key, label in zip(FIELDS, labels, strict=True)}
        return assemble(ends, values, "USD")
    return arm_press(document)


def skhy(document):
    content = text(document)
    if "Preliminary Results of Operations" not in content:
        return skhy_full(document)
    match = re.search(r"Second quarter.*?of (20\d{2})", content, re.S)
    if not match:
        raise ValueError("SKHY quarterly period missing")
    values = {}
    for key, label in [
        ("revenue", "Revenue"),
        ("operating_income", r"Operating Profit \(Loss\)"),
        ("net_income", "Controlling Interests"),
    ]:
        found = re.search(label + r".*?Results\s+([\d,]+)", content, re.S)
        values[key] = float(found[1].replace(",", "")) * 1e6 if found else None
    return [
        {
            "period_end": date(int(match[1]), 6, 30),
            "currency": "KRW",
            "gross_profit": None,
            "eps_diluted": None,
            **values,
        }
    ]


def arm_press(document):
    content = text(document)
    match = re.search(r"three months ended\s+(\w+)\s+(\d{1,2}),\s*(20\d{2})", content, re.I)
    if not match:
        raise ValueError("ARM quarter announcement period missing")
    end = date(int(match[3]), MONTHS[match[1].lower()[:3]], int(match[2]))
    for rows in table_rows(document):
        if not any("GAAP" in " ".join(r) for r in rows[:3]) or not any("Gross profit" == r[0] for r in rows):
            continue
        labels = [
            r"Total revenue\s*(?:\(2\))?",
            "Gross profit",
            r"Operating income \(loss\)",
            r"Net income \(loss\)",
            r"Diluted earnings \(loss\) per share \(\$\)",
        ]
        values = {key: labelled(rows, label) for key, label in zip(FIELDS, labels, strict=True)}
        return assemble([end, end.replace(year=end.year - 1)], values, "USD", indexes=[0, 1])
    raise ValueError("ARM GAAP summary missing")


def skhy_full(document):
    for rows in table_rows(document):
        header = " ".join(" ".join(row) for row in rows[:4])
        match = re.search(r"Period Ended\s+(\w+)\s+(\d+)\s+(20\d{2})\s+(20\d{2})", header)
        if not match or not any("Gross profit" == r[0] for r in rows):
            continue
        end = date(int(match[3]), MONTHS[match[1].lower()[:3]], int(match[2]))
        previous = end.replace(year=int(match[4]))
        labels = [
            "Revenue",
            "Gross profit",
            "Operating profit",
            "Owners of the Parent Company",
            r"Diluted earnings per share \(in Korean won\)",
        ]
        values = {}
        for key, label in zip(FIELDS, labels, strict=True):
            cells = next(r for r in rows if re.fullmatch(label, r[0]))
            # The second non-empty column is an optional note reference, not
            # an amount. Four explicit numeric groups start at column five.
            values[key] = numbers(" ".join(cells[4:]))
        output = assemble([end, previous], values, "KRW", indexes=[0, 2])
        if end.month == 6:
            for index, year in [(0, end.year), (2, previous.year)]:
                derived = {key: [values[key][index + 1] - values[key][index]] for key in FIELDS}
                output.extend(
                    dict(row, derivation="ytd6_minus_q2") for row in assemble([date(year, 3, 31)], derived, "KRW")
                )
        return output
    raise ValueError("SKHY supported financial statement layout missing")
