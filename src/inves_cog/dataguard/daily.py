"""Daily completeness matrix and a redacted resource-log summary."""

import re
from datetime import datetime, timedelta
from pathlib import Path

from inves_cog.dataguard.calendar import NY, regular_bounds, trading_day


def closed_day(now):
    day = now.astimezone(NY).date()
    bounds = regular_bounds(day)
    if not bounds or now < bounds[1]:
        day -= timedelta(days=1)
        while not trading_day(day):
            day -= timedelta(days=1)
    return day


def matrix(items, results, now):
    day = closed_day(now)
    checked = {item.dataset: days for item, days in results}
    rows = []
    for item in items:
        days = checked.get(item.dataset, {})
        available = [d for d in days if d <= day]
        if not available:
            state = "not_due" if item.dataset in checked else "unknown"
            rows.append(
                dict(
                    dataset=item.dataset,
                    data_date=day,
                    kind=state,
                    status=state,
                    detail={"impact": item.impact},
                    attempts=0,
                )
            )
        else:
            target = max(available)
            found = days[target]
            if found:
                rows.extend(
                    dict(
                        dataset=item.dataset, data_date=target, kind=f.kind, status="open", detail=f.detail, attempts=0
                    )
                    for f in found
                )
            else:
                rows.append(
                    dict(
                        dataset=item.dataset,
                        data_date=target,
                        kind="complete",
                        status="complete",
                        detail={"impact": item.impact},
                        attempts=0,
                    )
                )
    return rows


def resource_log_summary(path, now, *, max_bytes=65536):
    """Only aggregate recent alarm categories. Never return line content, keys or addresses."""
    counts = {"memory": 0, "io": 0, "unclassified": 0, "unknown_time": 0}
    try:
        with Path(path).open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - max_bytes))
            content = stream.read(max_bytes).decode("utf-8", "replace")
    except OSError:
        return "资源告警日志尚无法读取"
    for line in content.splitlines():
        stamp = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", line)
        if not stamp:
            counts["unknown_time"] += 1
            continue
        try:
            at = datetime.fromisoformat(stamp[0].replace("Z", "+00:00"))
        except ValueError:
            counts["unknown_time"] += 1
            continue
        if at.tzinfo is None:
            counts["unknown_time"] += 1
            continue
        if not now - timedelta(days=1) <= at <= now:
            continue
        if re.search(r"oom|memory|内存", line, re.I):
            counts["memory"] += 1
        elif re.search(r"\bio\b|io.pressure|磁盘", line, re.I):
            counts["io"] += 1
        else:
            counts["unclassified"] += 1
    scope = "（仅最近64KB）" if size > max_bytes else ""
    return (
        f"过去24小时告警：内存{counts['memory']}条，IO{counts['io']}条，"
        f"其他{counts['unclassified']}条，时间无法核实{counts['unknown_time']}条{scope}"
    )
