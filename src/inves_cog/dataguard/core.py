"""Clock-injected data expectations. No provider calls, trading rules, or database writes."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from math import ceil, isfinite
from statistics import median

from inves_cog.dataguard.calendar import NY, ecb_target_holiday, next_trading_day, trading_day


@dataclass(frozen=True)
class Expectation:
    dataset: str
    table: str
    date_column: str
    deadline_et: str
    grace_min: int = 30
    cadence: str = "trading_day"
    calendar_days: bool = False
    failures_only: bool = False
    active_start_et: str = "09:30"
    inactive_windows: tuple = ()
    release_sessions: int = 0
    release_days: int = 0
    period_end: str | None = None
    weekday: int | None = None
    min_rows: int = 1
    min_coverage: float | None = None
    expected_keys: tuple = ()
    key_column: str | None = None
    value_column: str | None = None
    adjustment_column: str | None = None
    quality_column: str | None = None
    corporate_actions: dict = field(default_factory=dict)
    staleness: bool = False
    sanity: float | None = None
    sanity_leverage: dict = field(default_factory=dict)
    holiday_calendar: str | None = None
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
        for identifier in [
            self.date_column,
            self.key_column,
            self.value_column,
            self.adjustment_column,
            self.quality_column,
            self.latest_column,
            *self.filter,
        ]:
            if identifier is not None and not re.fullmatch(r"[a-z_][a-z_0-9]*", identifier):
                raise ValueError("Invalid column identifier")
        if self.period_end not in {None, "week", "month"}:
            raise ValueError("Invalid period boundary")
        if self.failures_only and self.table != "ingest.job_runs":
            raise ValueError("Only job-failure lists can be empty")
        if self.scope not in {None, "wide"}:
            raise ValueError("Invalid monitored scope")
        time.fromisoformat(self.deadline_et)
        if self.cadence not in {"trading_day", "weekday", "weekly", "monthly", "semimonthly"}:
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
        if not item.calendar_days and item.cadence not in {"weekday", "monthly"} and not trading_day(day):
            continue
        if item.holiday_calendar == "ecb" and ecb_target_holiday(day):
            continue
        if item.period_end:
            if not trading_day(day):
                continue
            nxt = next_trading_day(day)
            if item.period_end == "week" and nxt.isocalendar()[:2] == day.isocalendar()[:2]:
                continue
            if item.period_end == "month" and (nxt.year, nxt.month) == (day.year, day.month):
                continue
        else:
            if item.cadence == "weekly" and day.weekday() != item.weekday:
                continue
            if item.cadence == "monthly" and (day + timedelta(days=1)).month == day.month:
                continue
            if item.cadence == "semimonthly" and day != _finra_settlement(day):
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


# value/old ratios matching integer splits (forward 2:1, 3:1 / reverse 1:2, 1:3). A day move that
# lands within 0.05 of one of these with no recorded corporate action is almost surely an
# unrecorded split, so it must be flagged regardless of the sanity threshold.
SPLIT_RATIOS = (0.5, 1 / 3, 2.0, 3.0)


def evaluate(item, day, rows, previous, *, prior_counts=(), actions=frozenset(), row_count=None, now=None):
    """One finding per kind/date, with actual input evidence. Missing is never a numeric zero."""
    count = len(rows) if row_count is None else row_count
    detail = {
        "impact": item.impact,
        "rows": count,
        "label": item.dataset,
        "affects_barometer": item.table.startswith("flows.")
        or item.table in {"ingest.bars_daily", "ingest.macro_observations"},
    }
    if not count and item.failures_only:
        return []
    if not count:
        detail["missing_keys"] = sorted(item.expected_keys)
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
    missing_fields = sorted({str(field) for r in rows for field in (r.get("quality") or [])})
    outdated = [
        {"key": r["key"], "state_filed": str(r["day"]), "expected_filed": str(r["expected_filed"])}
        for r in rows
        if r.get("expected_filed") and r.get("day") and r["expected_filed"] > r["day"]
    ]
    if not enough_keys or count < expected or null_keys or missing_fields or outdated:
        result.append(
            Finding(
                item.dataset,
                day,
                "partial",
                {
                    **detail,
                    "missing_keys": missing,
                    "null_keys": null_keys,
                    "expected_rows": expected,
                    "missing_fields": missing_fields,
                    "outdated_filings": outdated,
                },
            )
        )
    if item.table == "ingest.job_runs":
        return result + _job_findings(item, day, rows, detail, now)
    before_rows = {r.get("key"): r for r in previous}
    before = {key: r.get("value") for key, r in before_rows.items()}
    stale, suspect = [], []
    for row in rows:
        key, value = row.get("key"), row.get("value")
        old = before.get(key)
        if value is not None and not isfinite(float(value)):
            suspect.append({"key": key, "reason": "nonfinite"})
            continue
        if old is None or value is None:
            continue
        old, value = float(old), float(value)
        if not isfinite(old) or not isfinite(value):
            suspect.append({"key": key, "reason": "nonfinite"})
            continue
        evidence = {
            "key": key,
            "previous": old,
            "current": value,
            "corporate_action": key in actions,
            "previous_adjustment": before_rows.get(key, {}).get("adjustment"),
            "current_adjustment": row.get("adjustment"),
        }
        if key in actions:
            evidence["action_evidence"] = item.corporate_actions.get(str(day), {}).get(key)
        if item.staleness and value == old:
            stale.append(evidence)
        if old > 0 and key not in actions:
            ratio = value / old
            leverage = item.sanity_leverage.get(key, 1)
            threshold = (item.sanity or 0) * leverage
            split_like = any(abs(ratio - r) <= 0.05 for r in SPLIT_RATIOS)
            if (item.sanity and abs(ratio - 1) > threshold) or split_like:
                suspect.append({**evidence, "change": ratio - 1, "split_like": split_like})
    for kind, evidence in [("stale", stale), ("suspect", suspect)]:
        if evidence:
            result.append(Finding(item.dataset, day, kind, {**detail, "evidence": evidence}))
    return result


def _job_findings(item, day, rows, detail, now):
    failed = []
    periodic = item.cadence.startswith("intraday:") and not item.failures_only
    effective = now
    if periodic and now:
        end = datetime.combine(day, time.fromisoformat(item.window_end_et), NY)
        effective = min(now, end)
    for row in rows:
        state = row.get("value")
        seen = row.get("seen_at")
        age = (effective - seen).total_seconds() / 60 if effective and seen else None
        if state == "failed":
            failed.append(row["key"])
        elif state == "running":
            if not item.failures_only or age is not None and age > 30:
                failed.append(row["key"])
        elif periodic and age is not None:
            local = effective.astimezone(NY).time()
            inactive = any(time.fromisoformat(a) <= local < time.fromisoformat(b) for a, b in item.inactive_windows)
            if not inactive and age > int(item.cadence.split(":")[1]) + item.grace_min:
                failed.append(row["key"])
    return [Finding(item.dataset, day, "job_failed", {**detail, "failed_tasks": failed})] if failed else []


def _finra_settlement(day):
    """FINRA settles mid-month (15th) and month-end, each rolled back to a trading day."""
    import calendar as _cal

    mid = day.replace(day=15)
    while not trading_day(mid):
        mid = mid - timedelta(days=1)
    last = day.replace(day=_cal.monthrange(day.year, day.month)[1])
    while not trading_day(last):
        last = last - timedelta(days=1)
    return day if day in {mid, last} else None
