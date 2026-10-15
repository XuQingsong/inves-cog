"""Independent financial extraction from SEC facts and visible filing evidence.

Legacy selection semantics were specified from read-only source inspection;
no external project module is loaded or executed.
"""

import calendar
from copy import deepcopy
from datetime import date, timedelta

from inves_cog.ingest.fundamentals.state import FIELDS, FinState

REPAIRS = ("D3", "D1", "D2", "D4", "D5", "D8", "D9")
TAGS = {
    "rev": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "gp": ["GrossProfit"],
    "ni": ["NetIncomeLoss"],
    "eps": ["EarningsPerShareDiluted"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cost": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "op": ["OperatingIncomeLoss"],
}
IFRS = {
    "rev": ["RevenueFromContractsWithCustomers", "Revenue"],
    "gp": ["GrossProfit"],
    "ni": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "eps": ["DilutedEarningsLossPerShare"],
    "ocf": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
    "cost": ["CostOfSales"],
    "op": ["ProfitLossFromOperatingActivities"],
}


def day(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def derive_quarters(annual, *, q1=None, q2=None, q3=None, ytd6=None, ytd9=None):
    output = {"q1": q1, "q2": q2, "q3": q3, "q4": None, "sources": {}, "health_codes": []}
    if q2 is None and ytd6 is not None and q1 is not None:
        output["q2"] = ytd6 - q1
        output["sources"]["q2"] = "ytd_derived"
    if q3 is None and ytd9 is not None and ytd6 is not None:
        output["q3"] = ytd9 - ytd6
        output["sources"]["q3"] = "ytd_derived"
    if annual is not None:
        if ytd9 is not None:
            output["q4"] = annual - ytd9
        elif all(output[q] is not None for q in ("q1", "q2", "q3")):
            output["q4"] = annual - sum(output[q] for q in ("q1", "q2", "q3"))
        if output["q4"] is None:
            output["health_codes"].append("q4_missing")
        else:
            output["sources"]["q4"] = "q4_derived"
    return output


class Facts:
    def __init__(self, data, as_of, *, fixed=False, fx=None, preferred_currency=None):
        self.data = data.get("facts", data)
        self.as_of = as_of
        self.fixed = fixed
        self.fx = fx
        self.preferred_currency = preferred_currency
        from inves_cog.ingest.fundamentals.plausibility import split_events

        self.splits = split_events(self.data, as_of) if fixed else []

    def entries(self, taxonomy, tag, units=("USD", "USD/shares", "shares")):
        node = self.data.get(taxonomy, {}).get(tag, {})
        choices = node.get("units", {})
        unit = next((u for u in units if u in choices), None)
        if unit is None and self.fixed:
            unit = next((u for u in choices if len(u.split("/")[0]) == 3), None)
        if self.fixed and self.preferred_currency:
            unit = next((u for u in choices if u.split("/")[0] == self.preferred_currency), unit)
        output = []
        for source in choices.get(unit, []):
            if (
                self.fixed
                and source.get("form")
                and str(source["form"]).removesuffix("/A") not in {"10-Q", "10-K", "20-F", "40-F", "6-K"}
            ):
                continue
            try:
                end, filed = day(source["end"]), day(source["filed"])
                if end > self.as_of or filed > self.as_of:
                    continue
                value = float(source["val"])
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if not __import__("math").isfinite(value):
                continue
            row = {**source, "end": end, "filed": filed, "val": value, "tag": taxonomy + ":" + tag, "unit": unit}
            if source.get("start"):
                try:
                    row["start"] = day(source["start"])
                except (TypeError, ValueError):
                    continue
            if self.fixed and unit not in {"USD", "USD/shares", "shares"}:
                from inves_cog.ingest.fundamentals.fx import FXGap

                if self.fx is None:
                    raise FXGap(
                        currency=unit.split("/")[0],
                        field=tag,
                        period=(row.get("start"), end),
                        as_of=self.as_of,
                        reason="FRED conversion provider not configured",
                    )
                value, evidence = self.fx.convert(
                    value, currency=unit.split("/")[0], start=row.get("start"), end=end, as_of=self.as_of, field=tag
                )
                row.update(val=value, fx=evidence, original_value=float(source["val"]), original_unit=unit)
            if self.fixed and tag == "EarningsPerShareDiluted":
                from inves_cog.ingest.fundamentals.plausibility import adjust_eps

                row = adjust_eps(row, self.splits)
            output.append(row)
        return output

    def all(self, tags, taxonomy="us-gaap"):
        return [dict(r, priority=rank) for rank, tag in enumerate(tags) for r in self.entries(taxonomy, tag)]

    def quarterly(self, tags, taxonomy="us-gaap"):
        selected = {}
        for row in self.all(tags, taxonomy):
            if "start" not in row or not 80 <= (row["end"] - row["start"]).days <= (120 if self.fixed else 100):
                continue
            old = selected.get(row["end"])
            if (
                old is None
                or row["filed"] > old["filed"]
                or row["filed"] == old["filed"]
                and row.get("origin") == "instance_parsed"
                and old.get("origin") != "instance_parsed"
            ):
                selected[row["end"]] = row
        return selected

    def instant(self, tags, taxonomy="us-gaap", units=("USD", "shares")):
        for tag in tags:
            rows = self.entries(taxonomy, tag, units)
            if rows:
                return max(rows, key=lambda r: (r["end"], r["filed"]))
        return None


def source(row):
    if row is None:
        return {"reason": "tag_or_period_missing"}
    result = {
        key: row.get(key)
        for key in (
            "tag",
            "unit",
            "accn",
            "start",
            "end",
            "filed",
            "derivation",
            "inputs",
            "fx",
            "original_value",
            "original_unit",
            "origin",
            "d9_only",
            "dimensions",
            "split_adjustment",
        )
        if key in row
    }
    return result


def sum_tail(series, n=4, offset=0):
    keys = sorted(series)
    keys = keys[-n - offset : len(keys) - offset if offset else None]
    return sum(series[k]["val"] for k in keys) if len(keys) == n else None


def ratio(a, b, multiplier=1):
    return a / b * multiplier if a is not None and b is not None and b != 0 else None


def month_after(start, n):
    value = start.year * 12 + start.month - 1 + n
    year, month = divmod(value, 12)
    month += 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def repair_flow(facts, tags, series, *, eps=False, taxonomy="us-gaap", calendar_series=None):
    rows = [r for r in facts.all(tags, taxonomy) if "start" in r]
    starts = sorted({r["start"] for r in rows if 170 <= (r["end"] - r["start"]).days <= 380})
    missing = []
    for start in starts:
        group = [r for r in rows if abs((r["start"] - start).days) <= 7]

        def period(low, high, annual=False, group=group):
            matches = [
                r
                for r in group
                if low <= (r["end"] - r["start"]).days <= high
                and (
                    not annual
                    or r.get("fp") == "FY"
                    or str(r.get("form", "")).startswith("10-K")
                    or taxonomy == "ifrs-full"
                )
            ]
            return max(matches, key=lambda r: (r["filed"], -r["priority"])) if matches else None

        annual = period(350, 380, True)
        six = period(170, 200)
        nine = period(260, 290)
        if eps and annual is None:
            continue
        quarters = {}
        for n in (1, 2, 3):
            low, high = ((80, 120 if facts.fixed else 100), (170, 200), (260, 290))[n - 1]
            candidates = [r for end, r in series.items() if low <= (end - start).days <= high]
            quarters[n] = max(candidates, key=lambda r: r["filed"]) if candidates else None
        if facts.fixed:
            from inves_cog.ingest.fundamentals.repairs import fiscal_quarters

            quarters = fiscal_quarters(series, start)
            calendar = fiscal_quarters(calendar_series or series, start)
            for number in (2, 3):
                reference = calendar[number]
                matches = [r for r in group if reference and r["end"] == reference["end"]]
                selected = max(matches, key=lambda r: (r["filed"], -r["priority"])) if matches else None
                if number == 2 and selected:
                    six = selected
                if number == 3 and selected:
                    nine = selected
        stale_nine = (
            facts.fixed
            and nine
            and all(quarters.values())
            and any(q["filed"] > nine["filed"] for q in quarters.values())
        )
        values = derive_quarters(
            annual["val"] if annual else None,
            q1=quarters[1]["val"] if quarters[1] else None,
            q2=quarters[2]["val"] if quarters[2] else None,
            q3=quarters[3]["val"] if quarters[3] else None,
            ytd6=None if eps or six is None else six["val"],
            ytd9=None if eps or nine is None or stale_nine else nine["val"],
        )
        for n in (2, 3, 4):
            if eps and n != 4:
                continue
            parent = annual if n == 4 else six if n == 2 else nine
            if parent is None or parent["end"] in series:
                continue
            if values["q" + str(n)] is None:
                if n == 4:
                    missing.append(parent["end"])
                continue
            selected_inputs = (
                (annual, *quarters.values())
                if n == 4 and (eps or nine is None or stale_nine)
                else (annual, nine)
                if n == 4
                else (six, quarters[1])
                if n == 2
                else (nine, six)
            )
            inputs = [r for r in selected_inputs if r]
            previous = quarters.get(n - 1) or (six if n == 3 else nine if n == 4 else None)
            series[parent["end"]] = {
                **parent,
                "start": (previous["end"] + timedelta(days=1) if previous else month_after(start, (n - 1) * 3)),
                "val": values["q" + str(n)],
                "filed": max(r["filed"] for r in inputs),
                "derivation": "eps_q4_derived" if eps else values["sources"]["q" + str(n)],
                "inputs": [source(r) for r in inputs],
            }
    return missing


def shares(facts):
    candidates = []
    for tax, tag in (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding")):
        rows = facts.entries(tax, tag, ("shares",))
        if rows and (not candidates or max(r["end"] for r in rows) > max(r["end"] for r in candidates)):
            candidates = rows
    instant = None
    if candidates:
        latest = max(r["end"] for r in candidates)
        by_accession = {}
        for row in candidates:
            if row["end"] != latest:
                continue
            accession = row.get("accn", "")
            old = by_accession.get(accession)
            if old is None or row["filed"] > old["filed"]:
                by_accession[accession] = row
        values = sorted(r["val"] for r in by_accession.values())
        value = values[-1] if values[-1] and values[0] / values[-1] > 0.9 else sum(values)
        instant = (
            value,
            latest.isoformat(),
            {"method": "instant", "components": [source(r) for r in by_accession.values()]},
        )
        if value and (facts.as_of - latest).days <= 400:
            return instant
    weighted = facts.quarterly(["WeightedAverageNumberOfDilutedSharesOutstanding"])
    if len(weighted) >= 4:
        last = weighted[max(weighted)]
        return (
            last["val"],
            last["end"].isoformat() + "（稀释加权近似）",
            {"method": "diluted_weighted_approximation", **source(last)},
        )
    return instant or (None, None, {"reason": "share_tags_missing"})


def extract_state(
    companyfacts,
    *,
    ticker,
    as_of,
    extractor="fixed",
    switches=None,
    sic=None,
    foreign=False,
    filings=(),
    instance_facts=None,
    price=None,
    fx=None,
    available_as_of=None,
):
    if extractor not in {"legacy", "fixed"}:
        raise ValueError("Unknown extractor")
    as_of = day(as_of)
    fixed = extractor == "fixed"
    enabled = {k: fixed for k in REPAIRS}
    if switches:
        enabled.update(switches)
    if set(enabled) - set(REPAIRS):
        raise ValueError("Unknown repair toggle")
    if instance_facts and not enabled["D9"]:
        from inves_cog.ingest.fundamentals.repairs import without_d9

        instance_facts = without_d9(instance_facts)
    data = deepcopy(companyfacts)
    codes = []
    relevant = [
        r
        for r in filings
        if str(r.get("form", "")).removesuffix("/A") in {"10-Q", "10-K", "20-F", "40-F", "6-K"}
        and day(r["filing_date"]) <= as_of
    ]
    if fixed and foreign:
        relevant = [r for r in relevant if str(r.get("form", "")).removesuffix("/A") in {"20-F", "40-F"}]
    latest = (
        max(relevant, key=lambda r: (day(r["filing_date"]), str(r.get("accepted_at") or ""), r["accession"]))
        if relevant
        else None
    )
    accession_set = {
        r.get("accn")
        for tax in data.get("facts", {}).values()
        for node in tax.values()
        for rows in node.get("units", {}).values()
        for r in rows
        if r.get("filed") and day(r["filed"]) <= as_of
    }
    if latest and latest["accession"] not in accession_set:
        codes.append("companyfacts_lag")
        if (
            enabled["D3"]
            and day(available_as_of or as_of) >= day(latest["filing_date"]) + timedelta(days=3)
            and instance_facts
        ):
            matching = [
                r
                for tax in instance_facts.get("facts", {}).values()
                for node in tax.values()
                for rows in node.get("units", {}).values()
                for r in rows
                if r.get("accn") == latest["accession"]
            ]
            if matching:
                for tax, nodes in instance_facts["facts"].items():
                    for tag, node in nodes.items():
                        for unit, rows in node.get("units", {}).items():
                            target = (
                                data.setdefault("facts", {})
                                .setdefault(tax, {})
                                .setdefault(tag, {"units": {}})
                                .setdefault("units", {})
                                .setdefault(unit, [])
                            )
                            target.extend(
                                dict(r, origin="instance_parsed") for r in rows if r.get("accn") == latest["accession"]
                            )
                codes.remove("companyfacts_lag")
    from inves_cog.ingest.fundamentals.repairs import merge_facts, scoring_gaps, settings

    d9 = settings().get("d9", {})
    approved_extra = ticker in d9.get("predecessor_ciks", {}) or ticker in d9.get("dimensional_facts", {})
    if enabled["D9"] and approved_extra and instance_facts:
        data = merge_facts(data, instance_facts)
    if fixed and foreign and enabled["D3"] and instance_facts:
        data = merge_facts(data, instance_facts)
    facts = Facts(
        data,
        as_of,
        fixed=fixed,
        fx=fx,
        preferred_currency={"TSM": "TWD", "NOK": "EUR", "ASML": "EUR", "ARM": "USD", "SKHY": "KRW"}.get(ticker)
        if foreign and fixed
        else None,
    )
    tags = deepcopy(TAGS)
    if enabled["D1"]:
        tags["rev"].insert(1, "RevenueFromContractWithCustomerIncludingAssessedTax")
    if enabled["D5"]:
        tags["ni"] += ["NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"]
    if enabled["D9"]:
        tags["rev"].extend(d9.get("revenue_tags", []))
    taxonomy = "ifrs-full" if fixed and foreign and "ifrs-full" in facts.data else "us-gaap"
    if taxonomy == "ifrs-full":
        tags = deepcopy(IFRS)
    series = {name: facts.quarterly(names, taxonomy) for name, names in tags.items()}
    gaps = {}
    if enabled["D2"] and not foreign:
        for name, names in tags.items():
            missing = repair_flow(
                facts, names, series[name], eps=name == "eps", taxonomy=taxonomy, calendar_series=series["rev"]
            )
            if missing:
                gaps[name] = missing
    if enabled["D4"]:
        for end, rev in series["rev"].items():
            cost = series["cost"].get(end)
            if end not in series["gp"] and cost:
                series["gp"][end] = {
                    **rev,
                    "val": rev["val"] - cost["val"],
                    "derivation": "gross_margin_derived",
                    "inputs": [source(rev), source(cost)],
                }
                codes.append("gross_margin_derived")
    if enabled["D5"] and any(r["tag"].split(":")[-1] != "NetIncomeLoss" for r in series["ni"].values()):
        codes.append("ni_tag_fallback")
    if (
        not enabled["D1"]
        and not series["rev"]
        and facts.entries("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax")
    ):
        codes.append("revenue_tag_gap")
    if fixed and foreign:
        codes.append("annual_basis")
        for name, names in tags.items():
            annual = {}
            for r in facts.all(names, taxonomy):
                if "start" not in r or not 350 <= (r["end"] - r["start"]).days <= 380:
                    continue
                old = annual.get(r["end"])
                if old is None or r["filed"] > old["filed"]:
                    annual[r["end"]] = r
            series[name] = annual
        if enabled["D4"]:
            for end, rev in series["rev"].items():
                cost = series["cost"].get(end)
                if end not in series["gp"] and cost:
                    series["gp"][end] = {**rev, "val": rev["val"] - cost["val"], "derivation": "gross_margin_derived"}
                    codes.append("gross_margin_derived")
    n = 1 if fixed and foreign else 4
    totals = {key: sum_tail(value, n) for key, value in series.items()}
    out = {"rev_growth": None, "rev_q_yoy": None, "rev_accel_pp": None, "eps_growth": None}
    sources = {}
    if gaps:
        sources["quarter_gaps"] = {name: [str(end) for end in ends] for name, ends in gaps.items()}
        if scoring_gaps(gaps, series, derive_gross=enabled["D4"]):
            codes.append("q4_missing")
    for name in ("rev", "ni", "eps"):
        if totals[name] is not None:
            out[name + "_ttm"] = totals[name]
    rev, eps = series["rev"], series["eps"]
    rkeys = sorted(rev)
    if totals["rev"] is not None:
        out["rev_period"] = rkeys[-1].isoformat()
        old = sum_tail(rev, n, n)
        out["rev_growth"] = (totals["rev"] / old - 1) * 100 if old else None
        if not foreign and len(rev) >= 8:
            out["rev_q_yoy"] = (
                (rev[rkeys[-1]]["val"] / rev[rkeys[-5]]["val"] - 1) * 100 if rev[rkeys[-5]]["val"] else None
            )
            prior = (rev[rkeys[-2]]["val"] / rev[rkeys[-6]]["val"] - 1) * 100 if rev[rkeys[-6]]["val"] else None
            if prior is not None and out["rev_q_yoy"] is not None:
                out["rev_accel_pp"] = out["rev_q_yoy"] - prior
    prev_eps = sum_tail(eps, n, n)
    if totals["eps"] is not None and totals["eps"] > 0 and prev_eps is not None and prev_eps > 0:
        out["eps_growth"] = (totals["eps"] / prev_eps - 1) * 100
    if totals["eps"] is not None and totals["eps"] > 0 and price is not None:
        out["pe"] = price / totals["eps"]

    def aligned(a, b, offset=0):
        return (
            len(a) >= n + offset
            and len(b) >= n + offset
            and sorted(a)[-n - offset : len(a) - offset if offset else None]
            == sorted(b)[-n - offset : len(b) - offset if offset else None]
        )

    if aligned(series["gp"], rev) and totals["rev"]:
        out["gross_margin"] = totals["gp"] / totals["rev"] * 100
        if aligned(series["gp"], rev, n) and sum_tail(rev, n, n):
            out["gross_margin_change_pp"] = (
                out["gross_margin"] - sum_tail(series["gp"], n, n) / sum_tail(rev, n, n) * 100
            )
    if totals["ocf"] is not None and totals["capex"] is not None:
        if not fixed or aligned(series["ocf"], series["capex"]):
            out["fcf_ttm"] = totals["ocf"] - totals["capex"]
    if out.get("fcf_ttm") is not None:
        if totals["rev"]:
            out["fcf_margin"] = out["fcf_ttm"] / totals["rev"] * 100
        if totals["ni"]:
            out["fcf_conversion"] = out["fcf_ttm"] / totals["ni"]
    instant_tags = {
        "equity": ["StockholdersEquity"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue"],
        "current_debt": ["DebtCurrent", "LongTermDebtCurrent"],
        "long_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
        "current_assets": ["AssetsCurrent"],
        "current_liabilities": ["LiabilitiesCurrent"],
    }
    if taxonomy == "ifrs-full":
        instant_tags.update(
            equity=["EquityAttributableToOwnersOfParent"],
            cash=["CashAndCashEquivalents"],
            current_debt=["CurrentBorrowings"],
            long_debt=["NoncurrentBorrowings"],
            current_assets=["CurrentAssets"],
            current_liabilities=["CurrentLiabilities"],
        )
    inst = {name: facts.instant(names, taxonomy) for name, names in instant_tags.items()}

    def value(name):
        return inst[name]["val"] if inst[name] else None

    if value("equity") and totals["ni"] is not None:
        out["roe"] = totals["ni"] / value("equity") * 100
    if value("cash") is not None:
        out["cash"] = value("cash")
    debt = [value(key) for key in ("current_debt", "long_debt") if value(key) is not None]
    if debt:
        out["debt"] = sum(debt)
        if value("cash") is None and enabled["D8"]:
            out["net_debt"] = out["net_debt_fcf"] = None
            sources["net_debt"] = sources["net_debt_fcf"] = {"reason": "cash_missing"}
        else:
            out["net_debt"] = out["debt"] - (value("cash") if value("cash") is not None else 0)
            if value("cash") is None:
                sources["net_debt"] = {"reason": "cash_missing_as_zero", "legacy_exception": True}
            if out.get("fcf_ttm") is not None and out["fcf_ttm"] > 0:
                out["net_debt_fcf"] = out["net_debt"] / out["fcf_ttm"]
    if value("current_assets") is not None and value("current_liabilities"):
        out["current_ratio"] = value("current_assets") / value("current_liabilities")
    share_value, share_date, share_source = shares(facts)
    if enabled["D9"] and ticker in d9.get("multi_class_issuers", []):
        weighted = facts.quarterly(["WeightedAverageNumberOfDilutedSharesOutstanding"])
        last = weighted[max(weighted)] if weighted else None
        share_value = last["val"] if last else None
        share_date = str(last["end"]) if last else None
        share_source = {"method": "multi_class_diluted", **source(last)}
    sources["shares"] = share_source
    if share_value:
        out.update(shares=share_value, shares_date=share_date)
        if price is not None:
            out["mktcap_asof"] = share_value * price
    if out.get("mktcap_asof") and out.get("rev_ttm"):
        out["ps"] = out["mktcap_asof"] / out["rev_ttm"]
    if out.get("mktcap_asof") and out.get("fcf_ttm") is not None:
        out["fcf_yield"] = out["fcf_ttm"] / out["mktcap_asof"] * 100
    if out.get("pe") and out.get("rev_growth") and out["rev_growth"] > 0:
        out["peg_rev_approx"] = out["pe"] / out["rev_growth"]
    flags = []
    if totals["rev"] is not None:
        if (as_of - rkeys[-1]).days > 180:
            codes.append("stale_fundamentals")
            out["fund_unreliable"] = True
            flags.append(f"营收序列过期（最新只到 {rkeys[-1].isoformat()}），基本面账不可靠")
        elif not foreign and (rkeys[-1] - rkeys[-4]).days > 380:
            flags.append("营收季度序列缺口过大，营收相关因子作废")
            for key in (
                "rev_growth",
                "rev_q_yoy",
                "rev_accel_pp",
                "gross_margin",
                "gross_margin_change_pp",
                "fcf_margin",
                "ps",
                "peg_rev_approx",
            ):
                out.pop(key, None)
    pe, ps, margin = out.get("pe"), out.get("ps"), out.get("gross_margin")
    if pe and pe < 5 and ps and ps < 2 or ps and ps < 3 and margin and margin > 60:
        out["split_suspect"] = True
        flags.append("疑似拆股口径错位，估值账作废待人工核对")
    out["data_flags"] = flags
    oracle = deepcopy(out)
    out["op_margin_ttm"] = ratio(totals["op"], totals["rev"], 100) if aligned(series["op"], rev) else None
    old_ocf, old_capex, old_rev = sum_tail(series["ocf"], n, n), sum_tail(series["capex"], n, n), sum_tail(rev, n, n)
    out["fcf_margin_change_pp"] = (
        out["fcf_margin"] - (old_ocf - old_capex) / old_rev * 100
        if out.get("fcf_margin") is not None and old_ocf is not None and old_capex is not None and old_rev
        else None
    )
    for name, rows in series.items():
        relevant_rows = [rows[k] for k in sorted(rows)[-2 * n :]]
        direct = {
            "rev": "rev_ttm",
            "ni": "ni_ttm",
            "eps": "eps_ttm",
            "gp": "gross_margin",
            "op": "op_margin_ttm",
            "ocf": "fcf_ttm",
            "capex": "fcf_ttm",
        }.get(name, name)
        sources.setdefault(direct, {"components": []})
        sources[direct]["components"] = sources[direct].get("components", []) + [source(r) for r in relevant_rows]
    for name, row in inst.items():
        sources.setdefault(name, source(row))
    for key in FIELDS:
        out.setdefault(key, None)
        if out[key] is None:
            sources.setdefault(key, {}).setdefault("reason", "required_tag_period_or_valid_denominator_missing")
        else:
            sources.setdefault(key, {"formula_inputs": "visible SEC financial fields"})
    if sic is not None and int(sic) in {4911, 4931, 4991}:
        codes.append("industry_basis_na")
    if any(out.get(key) is None for key in ("rev_ttm", "eps_ttm", "shares")):
        codes.append("core_field_missing")
    if fixed:
        from inves_cog.ingest.fundamentals.plausibility import violations

        invalid = violations(out, series)
        if invalid:
            codes.append("implausible_value")
            sources["implausible_value"] = {"violations": invalid}
    visible = [r for rows in series.values() for r in rows.values()] + [r for r in inst.values() if r]
    latest_fact = max(visible, key=lambda r: (r["filed"], r["end"])) if visible else None
    return FinState(
        ticker=ticker,
        extractor=extractor,
        filed=day(latest["filing_date"]) if latest else latest_fact["filed"] if latest_fact else as_of,
        period_end=max(rev) if rev else None,
        accession=latest["accession"] if latest else latest_fact.get("accn") if latest_fact else None,
        form=latest["form"] if latest else latest_fact.get("form") if latest_fact else None,
        fiscal_period=(max(rev).isoformat() if rev else None),
        values=out,
        field_sources=sources,
        health_codes=sorted(set(codes)) or ["ok"],
        oracle_values=oracle,
    )
