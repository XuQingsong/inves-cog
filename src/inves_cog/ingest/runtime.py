"""Clock-injected scheduling and isolated source execution."""

from inves_cog.ingest.jobs import JobRunner
from inves_cog.ingest.market import NY, trading_day


def complete_adv20(rows, sessions):
    if len(sessions) != 20 or len(set(sessions)) != 20:
        raise ValueError("ADV20 requires twenty distinct exchange sessions")
    by_day = {}
    for row in rows:
        day = row["trade_date"]
        if day in by_day:
            return None
        by_day[day] = row
    if any(
        day not in by_day or by_day[day].get("close") is None or by_day[day].get("volume") is None for day in sessions
    ):
        return None
    return sum(by_day[day]["close"] * by_day[day]["volume"] for day in sessions) / 20


def due_tasks(clock, last_runs):
    """Restarts use persisted start times; SEC never spills into M2's slot."""
    now = clock.now_utc().astimezone(NY)
    minute = now.hour * 60 + now.minute
    output = []

    def due(name, interval=None, after=None, before=None, session=False):
        if session and not trading_day(now.date()):
            return
        if after is not None and minute < after or before is not None and minute >= before:
            return
        previous = last_runs.get(name)
        if interval:
            bucket = now.replace(minute=now.minute // interval * interval, second=0, microsecond=0)
            if previous is None or previous < bucket:
                output.append(name)
        else:
            slot = after or 0
            scheduled_at = now.replace(hour=slot // 60, minute=slot % 60, second=0, microsecond=0)
            if previous is None or previous < scheduled_at:
                output.append(name)

    due("bars_prefill", after=480, before=490, session=True)
    due("news_prefill", after=480, before=490)
    due("news_poll", interval=10)
    due("intraday_snapshots", interval=30 if minute < 960 else 60, after=240, before=1200, session=True)
    due("yahoo_intraday", interval=30 if minute < 960 else 60, after=240, before=1200, session=True)
    due("news_watchdog", interval=10, after=600, before=1200, session=True)
    due("earnings_calendar", after=360)
    due("econ_calendar", after=360)
    due("vix_daily", after=1245, session=True)
    due("bars_full", after=1220, session=True)
    due("wide_universe", after=1220, session=True)
    due("m6_market_inputs", after=1220, session=True)
    if now.day <= 7:
        previous = last_runs.get("issuer_profiles")
        if previous is None or (previous.year, previous.month) != (now.year, now.month):
            due("issuer_profiles", after=1220, session=True)
    due("news_full", after=1220)
    due("sec_submissions", after=1245, before=1275)
    due("sec_index", after=1245, before=1275)
    if not 1275 <= minute < 1305:
        due("sec_atom", interval=10)
    for name in ("app_free", "app_grossing"):
        due(name, interval=60)
    for name in ("trends", "websites", "fred", "finra", "cboe", "fed_news", "eia_press", "eia_energy"):
        due(name, after=1245)
    return output


class Runtime:
    def __init__(self, *, clock, health, persist_job, tasks, trade_date=None, **runner_options):
        self.clock, self.tasks, self.trade_date = clock, tasks, trade_date
        self.runner = JobRunner(clock=clock, health=health, persist=persist_job, **runner_options)

    def run(self, names):
        unknown = set(names) - set(self.tasks)
        if unknown:
            raise ValueError("Unknown tasks: " + ", ".join(sorted(unknown)))
        result = {}
        for name in names:
            source, operation = self.tasks[name]
            seconds = 1500 if name == "bars_full" else 1800
            if name in {"sec_submissions", "sec_index"}:
                local = self.clock.now_utc().astimezone(NY)
                end = local.replace(hour=21, minute=15, second=0, microsecond=0)
                if not local.replace(hour=20, minute=45, second=0, microsecond=0) <= local < end:
                    result[name] = {"status": "not_due", "note": "M1 SEC slot is 20:45–21:15 ET"}
                    continue
                seconds = min(seconds, (end - local).total_seconds())
            self.runner.timeout_seconds = seconds
            result[name] = self.runner.run(
                name, source, operation, trade_date=self.trade_date() if self.trade_date else None
            )
        return result
