"""Research-only selection explanations and whole-pool, single-book counterfactuals."""

from copy import deepcopy
from math import isfinite

from inves_cog.trading.scoring.rules import BOOK_KEYS, ENTRY, EXCLUDED


def effective_books(score):
    books = dict(score.get("books") or {})
    adjusted = score.get("m31_adjusted_valuation")
    if adjusted is not None:
        books["valuation"] = adjusted
    return books


def score_blockers(score, thresholds=None):
    out = []
    tier = score.get("tier")
    if tier not in ENTRY:
        out.append("tier_missing")
    else:
        books = effective_books(score)
        limits = thresholds or dict(zip(BOOK_KEYS, ENTRY[tier], strict=True))
        out.extend(k for k in BOOK_KEYS if books.get(k) is None or books[k] < limits[k])
    if not score.get("tradable", True):
        out.append("untradable")
    if not score.get("m32_ok", False):
        out.append("m32")
    if EXCLUDED.intersection(score.get("red_lines", ())):
        out.append("redline")
    if (score.get("tech") or {}).get("price_vs_ma200") is None:
        out.append("price_history")
    return out


def relax_book(score, book, cutoff):
    """Only lower one numeric threshold; preserve books, M31, missingness and all other guards."""
    if book not in BOOK_KEYS or not isfinite(cutoff):
        raise ValueError("single existing numeric gate required")
    result = deepcopy(score)
    tier = score.get("tier")
    if tier not in ENTRY:
        return result
    limits = dict(zip(BOOK_KEYS, ENTRY[tier], strict=True))
    limits[book] = min(limits[book], cutoff)
    blockers = score_blockers(result, limits)
    result["gate_pass"] = not any(k in blockers for k in BOOK_KEYS)
    result["entry_pass"] = not blockers
    result["research_relaxation"] = dict(book=book, threshold=limits[book], original=ENTRY[tier][BOOK_KEYS.index(book)])
    return result


def quantile(values, probability=0.6):
    values = sorted(v for v in values if v is not None and isfinite(v))
    if not values:
        return None
    index = (len(values) - 1) * probability
    lo = int(index)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (index - lo)


def selection_audit(engine, daily, day, tickers):
    """Include exact engine skip reasons instead of guessing portfolio capacity from final holdings."""
    rows = []
    for ticker in tickers:
        score = daily.get(ticker)
        if score is None:
            rows.append(dict(ticker=ticker, date=day, blockers=["snapshot_missing"]))
            continue
        buys = [o for o in engine.pending if o["ticker"] == ticker and o["action"].startswith("buy")]
        reasons = [s["reason_zh"] for s in engine.skips if s["ticker"] == ticker]
        rows.append(
            dict(
                ticker=ticker,
                date=day,
                price=score["tech"].get("price"),
                tier=score.get("tier"),
                books=score.get("books"),
                blockers=score_blockers(score),
                entry_pass=score.get("entry_pass"),
                held=ticker in engine.positions,
                buy_intents=[o["label"] for o in buys],
                skip_reasons=reasons,
                hold_score=score.get("hold_score"),
                fund_bad=score.get("fund_bad"),
                red_lines=score.get("red_lines"),
                watch_waiting=ticker in engine.watch_first,
                cooldown_sessions=engine.index - engine.exits.get(ticker, (-100, None))[0],
            )
        )
    return rows
