"""Clock-injected data expectations. No provider calls, trading rules, or database writes."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from math import ceil, isfinite
from statistics import median

from inves_cog.dataguard.calendar import NY, next_trading_day, trading_day


@dataclass(frozen=True)
class Expectation:
    dataset: str
    table: str
    date_column: str
    deadline_et: str
    grace_min: int = 30
    cadence: str = "trading_day"
    release_sessions: int = 0
    release_days: int = 0
    weekday: int | None = None
    min_rows: int = 1
    min_coverage: float | None = None
    expected_keys: tuple = ()
    key_column: str | None = None
    value_column: str | None = None
    staleness: bool = False
    sanity: float | None = None
    filter: dict = field(default_factory=dict)
    scope: str | None = None
    timestamp: bool = False
    latest_column: str | None = None
    carry_forward: bool = False
    window_end_et: str = "16:00"
    monthly_day: str = "last"
    basis: str = ""
    impact: str = ""
    backfill: dict = field(default_factory=dict)

    def __post_init__(self):
        if not re.fullmatch(r"[a-z_][a-z_0-9]*\.[a-z_][a-z_0-9]*", self.table):
            raise ValueError("Invalid table identifier")
        for identifier in [self.date_column, self.key_column, self.value_column, self.latest_column, *self.filter]:
            if identifier is not None and not re.fullmatch(r"[a-z_][a-z_0-9]*", identifier):
                raise ValueError("Invalid column identifier")
        if self.scope not in {None, "wide"}:
            raise ValueError("Invalid monitored scope")
        time.fromisoformat(self.deadline_et)
        if self.cadence not in {"trading_day", "weekday", "weekly", "monthly"}:
            if not re.fullmatch(r"intraday:[1-9][0-9]*", self.cadence):
                raise ValueError("Invalid cadence")
        if self.min_rows < 1 or self.grace_min < 0 or self.release_sessions < 0 or self.release_days < 0:
            raise ValueError("Invalid expectation bounds")
        if self.min_coverage is not None and not 0 < self.min_coverage <= 1:
            raise ValueError("Invalid coverage")


def due_dates(item, now, *, lookback=7):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    today = now.astimezone(NY).date()
    result = []
    for offset in range(lookback, -1, -1):
        day = today - timedelta(days=offset)
        if item.cadence == "weekday" and day.weekday() >= 5:
            continue
        if item.cadence not in {"weekday", "monthly"} and not trading_day(day):
            continue
        if item.cadence == "weekly" and day.weekday() != item.weekday:
            continue
        if item.cadence == "monthly" and (day + timedelta(days=1)).month == day.month:
            continue
        release = day + timedelta(days=item.release_days)
        for _ in range(item.release_sessions):
            release = next_trading_day(release)
        deadline = datetime.combine(release, time.fromisoformat(item.deadline_et), NY)
        if now >= deadline + timedelta(minutes=item.grace_min):
            result.append(day)
    return result


@dataclass(frozen=True)
class Finding:
    dataset: str
    data_date: date
    kind: str
    detail: dict


def evaluate(item, day, rows, previous, *, prior_counts=(), actions=frozenset(), row_count=None):
    """One finding per kind/date, with actual input evidence. Missing is never a numeric zero."""
    count = len(rows) if row_count is None else row_count
    detail = {
        "impact": item.impact,
        "rows": count,
        "label": item.dataset,
        "affects_barometer": item.table.startswith("flows.")
        or item.table in {"ingest.bars_daily", "ingest.macro_observations"},
    }
    if not count:
        return [Finding(item.dataset, day, "missing", detail)]
    result = []
    keys = {r["key"] for r in rows if r.get("key") is not None}
    missing = sorted(set(item.expected_keys) - keys)
    expected = item.min_rows
    enough_keys = not missing
    if item.min_coverage and item.expected_keys:
        expected = max(expected, ceil(len(item.expected_keys) * item.min_coverage))
        enough_keys = len(set(item.expected_keys) & keys) >= expected
    elif item.min_coverage and len(prior_counts) >= 5:
        expected = max(expected, ceil(median(prior_counts[-5:]) * item.min_coverage))
    null_keys = [r.get("key") for r in rows if item.value_column and r.get("value") is None]
    if not enough_keys or count < expected or null_keys:
        result.append(
            Finding(
                item.dataset,
                day,
                "partial",
                {**detail, "missing_keys": missing, "null_keys": null_keys, "expected_rows": expected},
            )
        )
    if item.table == "ingest.job_runs":
        failed = [r["key"] for r in rows if r.get("value") not in {"ok", "degraded"}]
        if failed:
            result.append(Finding(item.dataset, day, "job_failed", {**detail, "failed_tasks": failed}))
        return result
    before = {r.get("key"): r.get("value") for r in previous}
    stale, suspect = [], []
    for row in rows:
        key, value = row.get("key"), row.get("value")
        old = before.get(key)
        if old is None or value is None:
            continue
        old, value = float(old), float(value)
        if not isfinite(old) or not isfinite(value):
            suspect.append({"key": key, "reason": "nonfinite"})
            continue
        evidence = {"key": key, "previous": old, "current": value, "corporate_action": key in actions}
        if item.staleness and value == old:
            stale.append(evidence)
        if item.sanity and old > 0 and abs(value / old - 1) > item.sanity and key not in actions:
            suspect.append({**evidence, "change": value / old - 1})
    for kind, evidence in [("stale", stale), ("suspect", suspect)]:
        if evidence:
            result.append(Finding(item.dataset, day, kind, {**detail, "evidence": evidence}))
    return result
