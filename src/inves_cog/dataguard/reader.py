"""Parameterized, date/key bounded reads; no arbitrary SQL is accepted from configuration."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path

import yaml

from inves_cog.dataguard.calendar import NY, regular_bounds, trading_day
from inves_cog.dataguard.core import Expectation, Finding, evaluate


def load(path):
    config = yaml.safe_load(Path(path).read_text())
    items = [Expectation(**r) for r in config["datasets"]]
    if len({r.dataset for r in items}) != len(items):
        raise ValueError("Duplicate dataset")
    if any(not item.basis or not item.impact for item in items):
        raise ValueError("Every deadline needs evidence and an affected user function")
    return config, items


def query(item, lower, upper):
    column = item.date_column
    bucket = f"({column} AT TIME ZONE 'America/New_York')::date" if item.timestamp else column
    key = item.key_column or "'all'"
    where, args = [f"{column}>=%s", f"{column}<%s"], [lower, upper]
    for name, values in sorted(item.filter.items()):
        where.append(f"{name}=ANY(%s)")
        args.append(list(values))
    if item.table == "ingest.job_runs" and item.cadence.startswith("intraday:") and not item.failures_only:
        where.extend(["status<>'running'", "ended_at IS NOT NULL"])
    predicate = " AND ".join(where)
    if item.value_column:
        latest = item.latest_column or column
        sql = (
            f"SELECT DISTINCT ON ({bucket}"
            + (f",{key}" if item.key_column else "")
            + f") {bucket} AS day,{key} AS key,"
            f"{item.value_column} AS value,1 AS n"
            + (f",{latest} AS seen_at" if item.table == "ingest.job_runs" else "")
            + (f",{item.adjustment_column} AS adjustment" if item.adjustment_column else "")
            + (f",{item.quality_column} AS quality" if item.quality_column else "")
            + f" FROM {item.table} WHERE {predicate} "
            f"ORDER BY {bucket}" + (f",{key}" if item.key_column else "") + f",{latest} DESC"
        )
    else:
        sql = (
            f"SELECT {bucket} AS day,{key} AS key,count(*) AS n,NULL AS value FROM {item.table} "
            f"WHERE {predicate} GROUP BY {bucket}" + (f",{key}" if item.key_column else "")
        )
    return sql, args


def read(connection, item, start, end, now):
    if item.carry_forward:
        # One index seek per known ticker; no history-wide aggregate or table scan.
        keys = list(item.expected_keys)
        conditions = []
        filter_args = []
        for name, values in sorted(item.filter.items()):
            conditions.append(f"{name}=ANY(%s)")
            filter_args.append(list(values))
        suffix = " AND " + " AND ".join(conditions) if conditions else ""
        sql = (
            f"SELECT k.key,r.{item.date_column} AS day,1 AS n,NULL AS value,f.filing_date AS expected_filed "
            f"FROM unnest(%s::text[]) AS k(key) JOIN LATERAL "
            f"(SELECT {item.date_column} FROM {item.table} WHERE {item.key_column}=k.key "
            f"AND {item.date_column}<=%s{suffix} ORDER BY {item.date_column} DESC LIMIT 1) r ON true "
            "LEFT JOIN LATERAL (SELECT filing_date FROM ingest.sec_filings WHERE ticker=k.key AND filing_date<=%s "
            "AND form IN ('10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A') "
            "ORDER BY filing_date DESC LIMIT 1) f ON true"
        )
        rows = connection.execute(sql, (keys, end, *filter_args, end)).fetchall()
        return {end: rows}
    if item.timestamp:
        lower = datetime.combine(start, time(), NY)
        upper = min(datetime.combine(end + timedelta(days=1), time(), NY), now)
        if item.cadence.startswith("intraday:"):
            bounds = regular_bounds(end)
            if not bounds or now < bounds[0]:
                return {}
            minutes = int(item.cadence.split(":")[1])
            if now < bounds[0] + timedelta(minutes=minutes + item.grace_min):
                return {}
            upper = min(now, bounds[1])
            lower = upper - timedelta(minutes=minutes + item.grace_min)
    else:
        lower, upper = start, end + timedelta(days=1)
    if not item.value_column and item.min_coverage is None:
        return presence(connection, item, start, end, now, lower, upper)
    sql, args = query(item, lower, upper)
    rows = connection.execute(sql, args).fetchall()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["day"]].append(row)
    return grouped


def findings(item, day, grouped, *, now=None):
    previous = day - timedelta(days=1)
    while not trading_day(previous):
        previous -= timedelta(days=1)
    rows, prior = grouped.get(day, []), grouped.get(previous, [])
    counts = [sum(r["n"] for r in values) for d, values in sorted(grouped.items()) if d < day][-5:]
    return evaluate(
        item,
        day,
        rows,
        prior,
        prior_counts=counts,
        row_count=sum(r["n"] for r in rows),
        actions=set(item.corporate_actions.get(str(day), {})),
        now=now,
    )


def presence(connection, item, start, end, now, lower, upper):
    """Bounded index seeks: presence checks do not aggregate millions of option strikes."""
    sessions = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    sessions = [d for d in sessions if trading_day(d)]
    keys = list(item.expected_keys) or list(item.filter.get(item.key_column, ())) or ["all"]
    days, lowers, uppers, names = [], [], [], []
    for day in sessions:
        for key in keys:
            days.append(day)
            names.append(key)
            if item.timestamp:
                lo = datetime.combine(day, time(), NY)
                hi = datetime.combine(day + timedelta(days=1), time(), NY)
                if item.cadence.startswith("intraday:"):
                    lo, hi = lower, upper
                lowers.append(lo)
                uppers.append(min(hi, now))
            else:
                lowers.append(day)
                uppers.append(day + timedelta(days=1))
    if not days:
        return {}
    typename = "timestamptz" if item.timestamp else "date"
    predicates = [f"{item.date_column}>=p.lo", f"{item.date_column}<p.hi"]
    arguments = [days, lowers, uppers, names]
    for name, values in sorted(item.filter.items()):
        predicates.append(f"{name}=ANY(%s)")
        arguments.append(list(values))
    if item.key_column and keys != ["all"]:
        predicates.append(f"{item.key_column}=p.key")
    where = " AND ".join(predicates)
    sql = (
        f"SELECT p.day,p.key,r.n,NULL AS value FROM unnest(%s::date[],%s::{typename}[],%s::{typename}[],%s::text[]) "
        f"AS p(day,lo,hi,key) JOIN LATERAL (SELECT count(*) AS n FROM (SELECT 1 FROM {item.table} "
        f"WHERE {where} LIMIT %s) bounded) r ON r.n>0"
    )
    arguments.append(item.min_rows)
    rows = connection.execute(sql, arguments).fetchall()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["day"]].append(row)
    return grouped


def wide_scope(connection, day):
    latest = connection.execute(
        "SELECT trade_date FROM ingest.wide_universe WHERE trade_date<=%s ORDER BY trade_date DESC LIMIT 1", (day,)
    ).fetchone()
    if not latest:
        raise ValueError("Wide monitored pool is unavailable")
    rows = connection.execute(
        "SELECT ticker FROM ingest.wide_universe WHERE trade_date=%s AND included", (latest["trade_date"],)
    ).fetchall()
    return tuple(r["ticker"] for r in rows)


def barometer_drift(dataset, day, saved, current):
    if current is None:
        return None
    try:
        same = saved is not None and abs(float(saved) - float(current)) < 1e-8
    except (TypeError, ValueError):
        same = False
    if same:
        return None
    return Finding(
        dataset,
        day,
        "stale",
        {
            "impact": "来源波动率已更新，但该日晴雨表读数尚未修订",
            "affects_barometer": True,
            "cached_value": saved,
            "source_value": current,
            "source": "VIX_CBOE",
        },
    )


def barometer_drifts(connection, item, first, last):
    rows = connection.execute(
        "SELECT b.date,b.inputs->>'VIX' AS cached,r.value FROM flows.barometer_daily b "
        "LEFT JOIN LATERAL (SELECT value FROM ingest.macro_observations "
        "WHERE series_id='VIX_CBOE' AND observation_date=b.date ORDER BY fetched_at DESC LIMIT 1) r ON true "
        "WHERE b.date>=%s AND b.date<=%s",
        (first, last),
    ).fetchall()
    result = {}
    for row in rows:
        finding = barometer_drift(item.dataset, row["date"], row["cached"], row["value"])
        if finding:
            result[row["date"]] = finding
    return result
