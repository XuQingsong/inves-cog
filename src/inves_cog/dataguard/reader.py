"""Parameterized, date/key bounded reads; no arbitrary SQL is accepted from configuration."""

from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path

import yaml

from inves_cog.dataguard.core import Expectation, evaluate
from inves_cog.ingest.market import NY, regular_bounds, trading_day


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
    predicate = " AND ".join(where)
    if item.value_column:
        latest = item.latest_column or column
        sql = (
            f"SELECT DISTINCT ON ({bucket},{key}) {bucket} AS day,{key} AS key,"
            f"{item.value_column} AS value,1 AS n FROM {item.table} WHERE {predicate} "
            f"ORDER BY {bucket},{key},{latest} DESC"
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
            f"SELECT k.key,r.{item.date_column} AS day,1 AS n,NULL AS value "
            f"FROM unnest(%s::text[]) AS k(key) JOIN LATERAL "
            f"(SELECT {item.date_column} FROM {item.table} WHERE {item.key_column}=k.key "
            f"AND {item.date_column}<=%s{suffix} ORDER BY {item.date_column} DESC LIMIT 1) r ON true"
        )
        rows = connection.execute(sql, (keys, end, *filter_args)).fetchall()
        return {end: rows}
    if item.timestamp:
        lower = datetime.combine(start, time(), NY)
        upper = min(datetime.combine(end + timedelta(days=1), time(), NY), now)
        if item.cadence.startswith("intraday:"):
            bounds = regular_bounds(now.astimezone(NY).date())
            if not bounds or not bounds[0] <= now <= bounds[1]:
                return {}
            minutes = int(item.cadence.split(":")[1])
            if now < bounds[0] + timedelta(minutes=minutes + item.grace_min):
                return {}
            lower, upper = now - timedelta(minutes=minutes + item.grace_min), now
    else:
        lower, upper = start, end + timedelta(days=1)
    sql, args = query(item, lower, upper)
    rows = connection.execute(sql, args).fetchall()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["day"]].append(row)
    return grouped


def findings(item, day, grouped):
    previous = day - timedelta(days=1)
    while not trading_day(previous):
        previous -= timedelta(days=1)
    rows, prior = grouped.get(day, []), grouped.get(previous, [])
    counts = [sum(r["n"] for r in values) for d, values in sorted(grouped.items()) if d < day][-5:]
    return evaluate(item, day, rows, prior, prior_counts=counts, row_count=sum(r["n"] for r in rows))
