"""Independent scheduler watchdog; supervised separately from long-running jobs."""

import time

from inves_cog.clock import SystemClock
from inves_cog.ingest.cli import connect
from inves_cog.ingest.market import NY, trading_day
from inves_cog.ingest.repository import Repository, json_text
from inves_cog.ingest.settings import read_environment


def check_bars_start(repo, clock):
    now = clock.now_utc()
    local = now.astimezone(NY)
    if not trading_day(local.date()) or (local.hour, local.minute) < (20, 30):
        return None
    slot = local.replace(hour=20, minute=20, second=0, microsecond=0)
    started = repo.last_runs(trade_date=local.date()).get("bars_full")
    healthy = started is not None and slot <= started <= now
    old = repo.health_rows().get("Scheduler:bars_full", {})
    row = {
        "source": "Scheduler:bars_full",
        "last_attempt_at": now,
        "last_success_at": now if healthy else old.get("last_success_at"),
        "status": "ok" if healthy else "unavailable",
        "latency_sec": None,
        "items_last_run": 1 if healthy else 0,
        "consecutive_failures": 0 if healthy else old.get("consecutive_failures", 0) + 1,
        "note": f"{local.date()} bars_full started at {started}"
        if healthy
        else f"{local.date()} ET 20:30: no bars_full start at/after 20:20",
    }
    repo.write_health(row)
    return row


def main():
    clock = SystemClock()
    while True:
        with connect(read_environment()) as connection:
            result = check_bars_start(Repository(connection), clock)
            if result:
                print(json_text(result), flush=True)
            news = check_news_gap(Repository(connection), clock)
            if not news["healthy"]:
                print(json_text(news), flush=True)
        time.sleep(30)


def check_news_gap(repo, clock):
    """Two-hour absence after ET10 on exchange sessions; independent of models."""
    from datetime import timedelta

    now = clock.now_utc()
    local = now.astimezone(NY)
    latest = repo.latest_news_at()
    active = trading_day(local.date()) and 10 <= local.hour < 20
    healthy = not active or latest is not None and now - latest < timedelta(hours=2)
    old = repo.health_rows().get("AlpacaNews", {})
    if active and not healthy:
        repo.write_health(
            dict(
                source="AlpacaNews",
                last_attempt_at=now,
                last_success_at=old.get("last_success_at"),
                status="unavailable",
                latency_sec=None,
                items_last_run=0,
                consecutive_failures=old.get("consecutive_failures", 0) + 1,
                note="No Alpaca news inserted in past 2h; latest_data_at=" + (latest.isoformat() if latest else "none"),
            )
        )
    return {"processed_count": 0, "healthy": healthy, "status": "ok" if healthy else "degraded"}


if __name__ == "__main__":
    main()
