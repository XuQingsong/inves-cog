"""Pure rule A scoring; all financial lookups use the injected PIT interface."""

from datetime import date

from inves_cog.ingest.fundamentals.health import BLOCKING
from inves_cog.trading.scoring.books import build_books, split_suspect
from inves_cog.trading.scoring.curves import finite
from inves_cog.trading.scoring.rules import assign_tier, certainty, entry_rules, holding, red_lines
from inves_cog.trading.scoring.technical import technical_series

FOREIGN = {"ASML", "ARM", "TSM", "SKHY", "NOK"}


def score_fields(
    fields,
    tech,
    *,
    signal_date,
    ticker="SYN",
    extractor="fixed",
    rule_set="A",
    state_filed=None,
    period_end=None,
    health_codes=(),
    previous=None,
    params_version="p-2026.10",
):
    if rule_set != "A" or extractor not in {"legacy", "fixed"}:
        raise ValueError("Only rule A with an explicit approved extractor is supported")
    fields = dict(fields)
    tech = {key: float(value) if finite(value) else None for key, value in tech.items()}
    books, derived, subitems, missing, timing_missing = build_books(fields, tech)
    codes = set(health_codes) - {"ok"}
    end = period_end or fields.get("rev_period")
    if isinstance(end, str):
        end = date.fromisoformat(end)
    if fields.get("fund_unreliable") or end is not None and (signal_date - end).days > 180:
        codes.add("stale_fundamentals")
    blocked = codes & (BLOCKING if extractor == "fixed" else {"stale_fundamentals"})
    if blocked:
        books.update(quality=None, growth=None, valuation=None)
    suspect = "split_suspect" in codes or split_suspect(derived, fields)
    if suspect:
        books["valuation"] = None
        codes.add("split_suspect")
    lines = red_lines(fields, tech, derived)
    volatility = tech.get("vol60") if tech.get("vol60") is not None else tech.get("vol20")
    reassess = (
        not previous
        or previous.get("tier") is None
        or state_filed is not None
        and state_filed > previous["signal_date"]
    )
    tier = assign_tier(books, fields, volatility) if reassess else previous["tier"]
    # M20 / source v18 L209–213: an existing tier survives an aged book until a new filing;
    # assign_tier refuses missing books when reassessment is actually due. Gate remains false.
    changed = signal_date if not previous or previous.get("tier") != tier else previous.get("tier_changed_on")
    points, label = certainty(books, fields)
    entry = entry_rules(books, fields, tier, lines)
    reason = ";".join(sorted(blocked)) or ("split_suspect" if suspect else None)
    if reason is None and any(books[k] is None for k in ("quality", "growth", "valuation")):
        reason = "missing_book:" + ",".join(k for k in ("quality", "growth", "valuation") if books[k] is None)
    if tech.get("price_vs_ma200") is None:
        reason = "insufficient_history"
        entry["entry_pass"] = False
    weights = {"quality": 25, "growth": 32.5, "valuation": 25, "timing": 17.5}
    rank = (
        round(sum(books[k] * w for k, w in weights.items()) / 100, 1)
        if all(books[k] is not None for k in weights)
        else None
    )
    consecutive = ((previous or {}).get("consec_pass", 0) + 1) if entry["entry_pass"] else 0
    return {
        "signal_date": signal_date,
        "ticker": ticker,
        "extractor": extractor,
        "rule_set": "A",
        "params_version": params_version,
        "tech": tech,
        "derived": derived,
        "books": books,
        "timing_subitems": subitems,
        "timing_missing": timing_missing,
        "missing_fields": missing,
        "rank_score": rank,
        "red_lines": lines,
        "tier": tier,
        "tier_changed_on": changed,
        "certainty": label,
        "certainty_points": points,
        **holding(fields),
        **entry,
        "consec_pass": consecutive,
        "tradable": ticker not in FOREIGN and not blocked and tier is not None,
        "null_reason": reason,
        "health_codes": sorted(codes) or ["ok"],
    }


def score_day(ticker, signal_date, *, tech, state_asof, extractor="fixed", previous=None, **kwargs):
    state = state_asof(ticker, signal_date, extractor)
    if state is None:
        return score_fields(
            {},
            tech,
            ticker=ticker,
            signal_date=signal_date,
            extractor=extractor,
            health_codes=["core_field_missing"],
            previous=previous,
            **kwargs,
        )
    return score_fields(
        state.values,
        tech,
        ticker=ticker,
        signal_date=signal_date,
        extractor=extractor,
        state_filed=state.filed,
        period_end=state.period_end,
        health_codes=state.health_codes,
        previous=previous,
        **kwargs,
    )


def score_history(ticker, bars, *, state_asof, extractor="fixed", start=None, end=None, previous=None):
    frame = technical_series(bars)
    result = []
    for day, row in frame.iterrows():
        if start is not None and day < start or end is not None and day > end:
            continue
        current = score_day(
            ticker, day, tech=row.to_dict(), state_asof=state_asof, extractor=extractor, previous=previous
        )
        result.append(current)
        previous = current
    return result
