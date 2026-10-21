"""ET windows and explicit dependency status; never catches up a missed publishing window."""

from datetime import time
from zoneinfo import ZoneInfo

from inves_cog.ingest.market import trading_day
from inves_cog.shadow.settings import settings


def due_stages(clock, *, premarket_ready, plan_ready, source_ready):
    local = clock.now_utc().astimezone(ZoneInfo("America/New_York"))
    start, end = [time.fromisoformat(value) for value in settings()["publish_window_et"]]
    if not trading_day(local.date()) or not start <= local.time() < end:
        return []
    stages = []
    if premarket_ready and source_ready:
        stages.append("overlay")
    if plan_ready:
        stages.append("shadows")
    return stages
