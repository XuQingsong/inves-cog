"""Operating-impact gate. A label is not evidence, and missing fields do not pass."""

_TOKEN = object()


class Verdict:
    def __init__(self, outcome, unknowns, token):
        if token is not _TOKEN:
            raise ValueError("截止日结果必须来自经营证据规则")
        self.outcome = outcome
        self.unknowns = list(unknowns)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _row(record):
    if isinstance(record, dict):
        return record
    return {"kind": record}


def _visible(record, as_of):
    published = record.get("published_at")
    if published is None or as_of is None:
        return False
    seen = record.get("first_seen_at") or published
    return max(published, seen) <= as_of


def _flip(direction):
    return {"down": "up", "up": "down"}.get(direction)


def _company_primary(record, as_of, expected):
    if record.get("kind") != "company_primary" or record.get("source_level") != 1:
        return False
    if not record.get("citation") or record.get("falsified") or not _visible(record, as_of):
        return False
    guidance = record.get("form") == "8-K" and record.get("guidance_change") is True
    call = record.get("call_quantitative") is True
    return (guidance or call) and record.get("direction") == expected


def _eps(record, as_of, expected):
    if record.get("kind") != "eps_revision" or record.get("falsified") or not _visible(record, as_of):
        return False
    coverage = record.get("coverage")
    revisions = record.get("same_direction_revisions")
    change = record.get("eps_change")
    if not _number(coverage) or coverage <= 0 or not _number(revisions) or not _number(change):
        return False
    if revisions < 0.30 * coverage:
        return False
    if expected == "down":
        return change <= -0.03
    if expected == "up":
        return change >= 0.03
    return False


def _competitor(record, as_of, expected):
    if record.get("kind") != "competitor_primary" or record.get("source_level") != 1:
        return False
    if not record.get("citation") or record.get("mapped_to_driver") is not True:
        return False
    if record.get("falsified") or not _visible(record, as_of):
        return False
    return record.get("direction") == expected


def _industry_root(record, as_of, expected):
    if record.get("kind") != "industry" or record.get("source_level") not in {2, 3}:
        return None
    if record.get("quantitative") is not True or not record.get("source_root"):
        return None
    if record.get("falsified") or record.get("direction") != expected or not _visible(record, as_of):
        return None
    return record["source_root"]


def _industry(records, as_of, expected):
    roots = set()
    for record in records:
        root = _industry_root(record, as_of, expected)
        if root:
            roots.add(root)
    return len(roots) >= 2


def _supports(records, as_of, expected):
    if expected is None:
        return False
    if any(_company_primary(record, as_of, expected) for record in records):
        return True
    if any(_eps(record, as_of, expected) for record in records):
        return True
    if any(_competitor(record, as_of, expected) for record in records):
        return True
    return _industry(records, as_of, expected)


def operating_verdict(records, *, as_of, expected_direction, unknowns=()):
    rows = [_row(record) for record in records]
    support = _supports(rows, as_of, expected_direction)
    oppose = _supports(rows, as_of, _flip(expected_direction))
    if support and not oppose:
        outcome = "支持"
    elif oppose and not support:
        outcome = "反证"
    else:
        outcome = "条件风险"
    return Verdict(outcome, unknowns, _TOKEN)
