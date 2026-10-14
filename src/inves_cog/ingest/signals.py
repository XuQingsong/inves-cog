"""Rank and search-interest boundaries; provider failures never create observations."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from inves_cog.ingest.info import make_item


def rank_jumps(previous, current, *, chart, clock):
    rows = []
    for app, rank in current.items():
        baseline = previous.get(app, 101)
        if baseline - rank > 20:
            native = f"{chart}:{app}:{clock.now_utc().isoformat()}"
            rows.append(
                make_item(
                    "app_rank",
                    "AppStore",
                    native,
                    headline=f"{app} rank {baseline} → {rank}",
                    body=f"{chart}: {app} {baseline} → {rank}",
                    clock=clock,
                    published_at=clock.now_utc(),
                    payload={"app_id": app, "chart": chart, "rank": rank, "previous_rank": baseline},
                )
            )
    return rows


def trend_event(keyword, history, today_value, *, clock):
    today = clock.now_utc().astimezone(ZoneInfo("America/New_York")).date()
    days = {
        row["date"]: row["value"]
        for row in history
        if today - timedelta(days=90) <= row["date"] < today and row.get("value") is not None
    }
    if len(days) < 60 or today_value is None:
        return None
    mean = sum(days.values()) / len(days)
    if mean == 0 or today_value <= 3 * mean:
        return None
    return make_item(
        "trend",
        "GoogleTrends",
        f"{keyword}:{today}",
        headline=f"{keyword} search interest increased",
        body=f"{keyword}: {today_value}; prior window mean {mean}",
        clock=clock,
        published_at=clock.now_utc(),
        payload={"keyword": keyword, "value": today_value, "baseline": mean, "valid_days": len(days)},
    )


def collect_trends(keywords, *, fetch, health, clock):
    results, failures, succeeded = [], [], 0
    for keyword in keywords:
        try:
            payload = fetch(keyword)
            item = trend_event(keyword, payload["history"], payload["today"], clock=clock)
            if item:
                results.append(item)
            succeeded += 1
        except Exception as exc:
            failures.append((keyword, exc))
    confirmed = (
        bool(failures) and not succeeded and all(getattr(exc, "confirmed_unavailable", False) for _, exc in failures)
    )
    note = "; ".join(f"{keyword}: {type(exc).__name__}: {exc}" for keyword, exc in failures) or None
    health.record(
        "GoogleTrends",
        success=bool(succeeded),
        count=len(results),
        confirmed_unavailable=confirmed,
        degraded=bool(failures),
        note=note,
    )
    return results
