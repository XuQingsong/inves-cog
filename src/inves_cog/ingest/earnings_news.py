"""A027 core earnings windows; no changes to news content or model policy."""

from datetime import datetime, timedelta
from pathlib import Path

import yaml

from inves_cog.ingest.http import SourceError
from inves_cog.ingest.market import NY

CORE_FALLBACK = frozenset(
    "MSFT GOOGL AMZN META ORCL CRWV NVDA AMD AVGO MRVL TSM ASML AMAT LRCX KLAC "
    "MU SNDK WDC DELL SMCI ANET CIEN COHR VRT GEV CEG INTC ARM QCOM".split()
)
BACKOFF_KEY = "news-poll-rate-fallback"


def core_tickers(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parents[3] / "config/core_companies.yaml"
    if not path.exists():
        return CORE_FALLBACK
    data = yaml.safe_load(path.read_text())
    return frozenset(row["ticker"] for row in data["companies"])


def news_interval(clock, earnings, *, backoff_until=None):
    now = clock.now_utc().astimezone(NY)
    if backoff_until is not None and clock.now_utc() < backoff_until:
        return 10
    minute = now.hour * 60 + now.minute
    pre, post = 390 <= minute <= 575, 955 <= minute <= 1110
    if not pre and not post:
        return 10
    core = core_tickers()
    for row in earnings:
        if row["ticker"] not in core or row["report_date"] != now.date():
            continue
        slot = row.get("time") or "unknown"
        if (pre and slot in {"pre", "unknown"}) or (post and slot in {"post", "unknown"}):
            return 1
    return 10


def cadence_inputs(repo, clock):
    now = clock.now_utc().astimezone(NY)
    cursor = repo.get_cursor(BACKOFF_KEY)
    until = datetime.fromisoformat(cursor["until"]) if cursor and cursor.get("until") else None
    return repo.core_earnings(now.date()), until


def poll_news(pipeline):
    earnings, until = cadence_inputs(pipeline.repo, pipeline.clock)
    accelerated = news_interval(pipeline.clock, earnings, backoff_until=until) == 1
    try:
        return pipeline.news(accelerated=accelerated)
    except SourceError as exc:
        if exc.status_code == 429:
            now = pipeline.clock.now_utc()
            end = (now.astimezone(NY) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            pipeline.repo.set_cursor(BACKOFF_KEY, {"until": end.isoformat()}, now)
            error = SourceError("News rate limit: fallback to 10 minutes until next ET day", status_code=429)
            error.degraded = True
            error.processed_count = getattr(exc, "processed_count", 0)
            raise error from exc
        raise
