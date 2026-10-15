"""Explicit D9 rules and current-window diagnostics; legacy stays untouched."""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def settings():
    return yaml.safe_load((Path(__file__).resolve().parents[4] / "config/params/p-2026.10/m2.yaml").read_text())["m2"]


def merge_facts(base, extra):
    result = deepcopy(base)
    for tax, tags in extra.get("facts", {}).items():
        for tag, node in tags.items():
            for unit, rows in node.get("units", {}).items():
                result.setdefault("facts", {}).setdefault(tax, {}).setdefault(tag, {"units": {}})["units"].setdefault(
                    unit, []
                ).extend(deepcopy(rows))
    return result


def without_d9(data):
    result = deepcopy(data)
    for tags in result.get("facts", {}).values():
        for node in tags.values():
            for unit, rows in node.get("units", {}).items():
                node["units"][unit] = [r for r in rows if not r.get("d9_only")]
    return result


def scoring_gaps(gaps, series, *, derive_gross):
    core = {"rev", "ni", "ocf", "capex", "eps", "gp"}
    if derive_gross and not series["gp"]:
        core.add("cost")
    ends = sorted(
        {end for name in core for end in series[name]} | {end for name in core for end in gaps.get(name, [])}
    )[-8:]
    return bool(ends) and any(end >= ends[0] and end not in series[name] for name in core for end in gaps.get(name, []))


def fiscal_quarters(series, start):
    from datetime import timedelta

    result = {1: None, 2: None, 3: None}
    cursor = start
    for number in (1, 2, 3):
        candidates = [
            row
            for row in series.values()
            if row.get("start")
            and abs((row["start"] - cursor).days) <= 7
            and 80 <= (row["end"] - row["start"]).days <= 120
        ]
        if not candidates:
            break
        result[number] = min(candidates, key=lambda row: (abs((row["start"] - cursor).days), row["end"]))
        cursor = result[number]["end"] + timedelta(days=1)
    return result


def dimension_allowed(fact, ticker):
    context = fact.context
    if not context.qnameDims:
        return True
    rules = settings().get("d9", {}).get("dimensional_facts", {}).get(ticker, [])
    if len(context.qnameDims) != 1:
        return False
    axis, dimension = next(iter(context.qnameDims.items()))
    member = dimension.memberQname
    if member is None:
        return False
    for rule in rules:
        if (
            fact.qname.localName == rule["tag"]
            and axis.localName == rule["axis"]
            and axis.namespaceURI.startswith(rule["axis_namespace_prefix"])
            and member.localName == rule["member"]
            and member.namespaceURI.startswith(rule["member_namespace_prefix"])
        ):
            return True
    return False
