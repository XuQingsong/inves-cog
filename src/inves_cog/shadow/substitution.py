"""Change one book only; preserve the accepted tier and every independent entry gate."""

from copy import deepcopy

from inves_cog.trading.scoring.curves import finite
from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY


def substitute(snapshot, *, factor_id, book, value):
    if book not in BOOK_KEYS:
        raise ValueError("single-factor substitution requires one known book")
    books = deepcopy(snapshot["books"])
    adjusted = snapshot.get("m31_adjusted_valuation")
    if adjusted is not None:
        books["valuation"] = adjusted
    books[book] = value
    tier = snapshot.get("tier")
    unknown = (
        not finite(value)
        or tier not in ENTRY
        or any(not finite(books.get(key)) for key in BOOK_KEYS)
        or snapshot.get("m32_ok") is None
        or snapshot.get("excluded_red_line") is None
    )
    passed = (
        None
        if unknown
        else bool(
            all(books[key] >= threshold for key, threshold in zip(BOOK_KEYS, ENTRY[tier], strict=True))
            and snapshot["m32_ok"]
            and not snapshot["excluded_red_line"]
        )
    )
    gaps = (
        {}
        if tier not in ENTRY
        else {
            key: None if not finite(books.get(key)) else max(0.0, threshold - books[key])
            for key, threshold in zip(BOOK_KEYS, ENTRY[tier], strict=True)
        }
    )
    return {
        "factor_id": factor_id,
        "books": books,
        "substituted_value": value,
        "would_pass": passed,
        "rule_a_entry_pass": snapshot.get("entry_pass"),
        "n_code": "N9" if snapshot.get("entry_pass") is False and passed is True else None,
        "gap_detail": {
            "book_shortfall": gaps,
            "m32_ok": snapshot.get("m32_ok"),
            "excluded_red_line": snapshot.get("excluded_red_line"),
            "unchanged_tier": tier,
            "null_reason": "单因子输入或原规则门禁缺失" if unknown else None,
        },
    }
