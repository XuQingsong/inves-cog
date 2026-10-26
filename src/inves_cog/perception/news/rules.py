"""Deterministic news rules layer: primary tickers, tags, importance, dedup.

Read-time computation only; nothing is written back to ingest. The rules were
tuned against the production dump in docs/phase1/design/prototype-v2/build.py.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

STRONG_RATING = re.compile(r"upgrade|downgrade|initiates? coverage", re.I)

TAG_RULES = [
    ("财报", r"\b(earnings|EPS|revenue|quarterly results|Q[1-4] results|financial results)\b|reports? (third|second|first|fourth) quarter"),
    ("财报前瞻", r"earnings preview|what to expect|ahead of earnings|earnings (on deck|this week)|priced for .* swings|earnings volatility"),
    ("评级", r"upgrade|downgrade|initiates? coverage|price target|\bPT\b|reiterat"),
    ("指引", r"guidance|outlook|raises? (FY|full-year)|lowers? (FY|full-year)|cuts? forecast"),
    ("并购", r"merger|acquisition|acquires?|takeover|buyout|to buy\b"),
    ("监管关税", r"tariff|export control|sanction|antitrust|\bFTC\b|\bDOJ\b|regulat"),
    ("诉讼召回", r"lawsuit|litigation|\bsues?\b|recall|settlement"),
    ("宏观", r"\b(Fed|FOMC|Powell|CPI|PCE|payrolls|jobs report|treasury yields?|inflation|GDP)\b"),
    ("产品合作", r"partnership|partners with|collaborat|launch|unveil|deploy|contract"),
]
MACRO_RULES = [
    ("利率", r"Fed|FOMC|yield|rate cut|rate hike|treasur"),
    ("关税", r"tariff|trade war|export control"),
    ("原油", r"\boil\b|crude|OPEC|Brent|WTI"),
    ("加密", r"bitcoin|crypto|ethereum"),
]
HOT_TAGS = {"财报", "指引", "并购"}

ECON_KEY = re.compile(
    r"FOMC|Fed Interest Rate|Fed Chair|Powell|CPI|PCE|Nonfarm|Unemployment Rate|\bGDP\b(?!Now)|ISM|"
    r"Retail Sales|Initial Jobless|Consumer Confidence|Michigan|JOLTS|PPI",
    re.I,
)


@dataclass
class NewsRule:
    primary_tickers: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    macro: str = None
    importance: int = 0
    held: bool = False
    weak_rating_only: bool = False
    dedup_key: tuple = ()


def classify(headline, symbols, universe, holdings):
    """Classify one headline. universe = pool ∪ held tickers; holdings ⊂ universe."""
    headline = headline or ""
    tickers = [t for t in (symbols or []) if isinstance(t, str)]
    primary = [t for t in tickers if t in universe]
    if len(tickers) > 5:
        primary = [t for t in primary if re.search(rf"\b{re.escape(t)}\b", headline)]
    tags = [name for name, pat in TAG_RULES if re.search(pat, headline, re.I)]
    if "并购" in tags and "产品合作" in tags:
        tags.remove("产品合作")
    macro = next((name for name, pat in MACRO_RULES if re.search(pat, headline, re.I)), None)
    score = 0
    held_hit = any(t in holdings for t in primary)
    if held_hit:
        score += 3
    elif primary:
        score += 2
    strong = (HOT_TAGS & set(tags)) or ({"评级"} & set(tags) if STRONG_RATING.search(headline) else set())
    if strong:
        score += 2
    elif set(tags) - {"评级"}:
        score += 1
    if len(tickers) > 5 and not primary:
        score -= 2
    return NewsRule(
        primary_tickers=primary,
        tags=tags,
        macro=macro,
        importance=score,
        held=held_hit,
        weak_rating_only=set(tags) == {"评级"} and not STRONG_RATING.search(headline),
        dedup_key=(tuple(sorted(primary)), " ".join(headline.lower().split()[:8])),
    )


def rank_day(items, universe, holdings, day):
    """Classify + dedup a day's news rows.

    items: iterable of dicts with headline, tickers, published_at, first_seen_at,
    info_id, source, url. Returns list sorted by published_at desc, each dict
    extended with the rule fields and 'late' (first_seen after day 16:00 ET).
    """
    late_cut = datetime.combine(day, time(16, 0), tzinfo=NY)
    classified = []
    for item in items:
        rule = classify(item.get("headline"), item.get("tickers"), universe, holdings)
        published = _ts(item.get("published_at"))
        seen = _ts(item.get("first_seen_at")) or published
        classified.append({**item, "rule": rule, "published": published, "seen": seen, "late": seen is not None and seen > late_cut})
    best = {}
    for item in sorted(classified, key=lambda x: (x["published"] or datetime.min.replace(tzinfo=NY))):
        best.setdefault(item["rule"].dedup_key, item)
    return sorted(best.values(), key=lambda x: (x["published"] or datetime.min.replace(tzinfo=NY)), reverse=True)


def _ts(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def theme_of(item, pool_theme, holdings):
    """Theme for hot-topic grouping: held primary's theme first, else the pool
    ticker earliest in the headline, else the first primary, else macro."""
    rule = item["rule"]
    if not rule.primary_tickers:
        return rule.macro
    held_p = [t for t in rule.primary_tickers if t in holdings]
    if held_p:
        headline = item.get("headline") or ""
        in_title = [t for t in held_p if re.search(rf"\b{re.escape(t)}\b", headline)]
        pick = in_title[0] if in_title else held_p[0]
        return pool_theme.get(pick) or pick
    headline = item.get("headline") or ""
    in_title = [t for t in rule.primary_tickers if re.search(rf"\b{re.escape(t)}\b", headline)]
    pick = in_title[0] if in_title else rule.primary_tickers[0]
    return pool_theme.get(pick) or pick
