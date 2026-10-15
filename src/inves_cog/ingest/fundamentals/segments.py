"""Arelle instance extraction with explicit dimension and recast boundaries."""

import hashlib
import json
import math
import re
from collections import defaultdict
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

PARSE_CONTRACT = "filing-relations-k16-v2"

REVENUE = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]


def segment_sum_ok(segments, eliminations, consolidated):
    eliminations = eliminations if isinstance(eliminations, list) else [eliminations]
    if consolidated is None or consolidated <= 0 or any(value is None for value in segments + eliminations):
        return False
    difference = abs(sum(segments) + sum(eliminations) - consolidated) / abs(consolidated)
    return difference <= 0.01 or math.isclose(difference, 0.01, rel_tol=0, abs_tol=1e-12)


def load_instance(path, *, offline=True, cache_dir=None, fetch=None):
    from arelle.Cntlr import Cntlr

    controller = Cntlr(logFileName="logToBuffer", disable_persistent_config=True)
    controller.webCache.workOffline = offline
    if cache_dir is not None:
        controller.webCache.cacheDir = str(Path(cache_dir))
    if fetch and not offline:
        original = controller.webCache.getfilename

        def cached(url, *args, **kwargs):
            from urllib.parse import urlparse

            parts = urlparse(url)
            target = Path(controller.webCache.urlToCacheFilepath(url))
            if parts.hostname in {"fasb.org", "www.fasb.org"} and target.is_file():
                return str(target)
            if parts.hostname in {"www.sec.gov", "data.sec.gov", "xbrl.sec.gov"}:
                target = Path(controller.webCache.urlToCacheFilepath(url))
                if not target.exists():
                    value = fetch(url.replace("http://", "https://", 1))
                    if not isinstance(value, str):
                        raise ValueError("SEC taxonomy response is not text")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(value)
                return str(target)
            return original(url, *args, **kwargs)

        controller.webCache.getfilename = cached
    model = controller.modelManager.load(str(path))
    if model is None or model.modelDocument is None:
        controller.close()
        raise ValueError("Arelle could not load the XBRL instance")
    return controller, model


def context_period(context):
    if context.isStartEndPeriod:
        start = context.startDatetime.date()
        end = (context.endDatetime - timedelta(days=1)).date()
        return (
            start,
            end,
            "Q" if 80 <= (end - start).days <= 100 else "FY" if 350 <= (end - start).days <= 380 else None,
        )
    return None, None, None


def numeric(fact):
    if fact.isNil:
        return None
    try:
        value = float(fact.value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def parse_segments(
    path, *, ticker, accession, filed, offline=True, cache_dir=None, fx=None, fetch=None, primary_html=None
):
    controller, model = load_instance(path, offline=offline, cache_dir=cache_dir, fetch=fetch)
    try:
        from inves_cog.ingest.fundamentals.segment_structure import (
            calculation_components,
            descendants,
            fact_positions,
            inline_positions,
            member_graph,
            plain_reconciliations,
            qkey,
            rendered_weight,
            same_column,
        )

        business_graph, business_members, business_roles, business_edges = member_graph(
            model, "StatementBusinessSegmentsAxis"
        )
        conso_graph, conso_members, conso_roles, conso_edges = member_graph(model, "ConsolidationItemsAxis")
        positions = inline_positions(primary_html)
        primary_sha256 = (
            hashlib.sha256(primary_html.encode("utf-8") if isinstance(primary_html, str) else primary_html).hexdigest()
            if primary_html
            else None
        )
        grouped = defaultdict(list)
        consolidated = {}
        all_totals = defaultdict(list)
        single = False
        basis_by_fact = {}
        conso_by_fact = {}
        member_by_fact = {}

        for fact in model.factsInInstance:
            context = fact.context
            if context is None:
                continue
            start, end, length = context_period(context)
            dims = list(context.qnameDims.items())
            name = fact.qname.localName
            if name in {"NumberOfReportableSegments", "NumberOfOperatingSegments"} and not dims and numeric(fact) == 1:
                single = True
            if length is None:
                continue
            if not dims:
                if name in REVENUE:
                    key = (start, end)
                    all_totals[key].append(fact)
                    old = consolidated.get(key)
                    if old is None or REVENUE.index(name) < REVENUE.index(old.qname.localName):
                        consolidated[key] = fact
                continue
            basis = None
            conso = None
            compound = False
            if len(dims) == 2:
                business = [pair for pair in dims if pair[0].localName == "StatementBusinessSegmentsAxis"]
                auxiliary = [
                    pair
                    for pair in dims
                    if pair[0].localName == "ConsolidationItemsAxis"
                    and re.fullmatch(r"https?://fasb\.org/srt/\d{4}", pair[0].namespaceURI)
                    and pair[1].isExplicit
                ]
                if len(business) != 1 or len(auxiliary) != 1:
                    continue
                auxiliary_member = auxiliary[0][1].memberQname
                normal = auxiliary_member.localName == "OperatingSegmentsMember" and re.fullmatch(
                    r"https?://fasb\.org/us-gaap/\d{4}", auxiliary_member.namespaceURI
                )
                gev = (
                    ticker == "GEV"
                    and auxiliary_member.localName == "OperatingSegmentsExcludingIntersegmentEliminationMember"
                    and re.fullmatch(r"https?://www\.gevernova\.com/\d{8}", auxiliary_member.namespaceURI)
                )
                if normal or gev:
                    basis = qkey(auxiliary_member)
                    dims = business
                elif qkey(auxiliary_member) in conso_members and conso_roles & business_roles:
                    conso = qkey(auxiliary_member)
                    compound = True
                    dims = business
                else:
                    continue
            if len(dims) != 1:
                continue
            axis, dimension = dims[0]
            if not dimension.isExplicit:
                continue
            kind = {
                "StatementBusinessSegmentsAxis": "business",
                "ConsolidationItemsAxis": "elimination",
                "ProductOrServiceAxis": "product",
            }.get(axis.localName)
            if kind is None:
                continue
            member = dimension.memberQname
            if compound:
                kind = "elimination"
            if kind == "elimination" and not compound:
                conso = qkey(member)
                if (
                    member.localName
                    not in {"IntersegmentEliminationMember", "CorporateNonSegmentMember", "OperatingSegmentsMember"}
                    and qkey(member) not in conso_members
                ):
                    continue
            basis_by_fact[id(fact)] = basis
            conso_by_fact[id(fact)] = (conso, compound)
            member_by_fact[id(fact)] = qkey(member)
            grouped[(start, end, length, kind, member.localName, str(member))].append(fact)

        def converted(fact, start, end, field):
            value = numeric(fact) if fact is not None else None
            currency = fact.unit.measures[0][0].localName if fact is not None and fact.unit is not None else None
            if value is not None and currency and currency != "USD":
                from inves_cog.ingest.fundamentals.fx import FXGap

                if fx is None:
                    raise FXGap(
                        currency=currency,
                        field=field,
                        period=(start, end),
                        as_of=filed,
                        reason="FRED conversion provider not configured",
                    )
                return fx.convert(value, currency=currency, start=start, end=end, as_of=filed, field=field)
            return value, {}

        totals = {period: converted(fact, *period, "consolidated_revenue") for period, fact in consolidated.items()}
        output = []
        selected_facts = {}
        selected_bases = {}
        for (start, end, length, axis, member, qname), facts in sorted(grouped.items()):
            revenues = [f for f in facts if f.qname.localName in REVENUE]
            bases = {basis_by_fact[id(f)] for f in revenues if basis_by_fact.get(id(f))}
            selected_basis = min(bases) if bases else None
            if axis == "business" and selected_basis:
                revenues = [f for f in revenues if basis_by_fact.get(id(f)) == selected_basis]
            revenue_fact = (
                min(revenues, key=lambda f: (REVENUE.index(f.qname.localName), f.context.id)) if revenues else None
            )
            selected_bases[(start, end)] = selected_basis or selected_bases.get((start, end))

            profits = [f for f in facts if f.qname.localName == "OperatingIncomeLoss"]
            if not profits:
                profits = [f for f in facts if f.qname.localName == "SegmentProfitLoss"]
            if not profits:
                profits = [
                    f
                    for f in facts
                    if re.search(r"(?:Profit|Income)", f.qname.localName)
                    and not re.search(r"(?:Tax|Interest|Comprehensive|PerShare)", f.qname.localName)
                ]
            if not revenues and not profits:
                continue
            profit_fact = profits[0] if len(profits) == 1 else None
            revenue = numeric(revenue_fact) if revenue_fact is not None else None
            profit = numeric(profit_fact) if profit_fact is not None else None
            currency = None
            if revenue_fact is not None and revenue_fact.unit is not None:
                currency = revenue_fact.unit.measures[0][0].localName
            revenue, fx_evidence = converted(revenue_fact, start, end, "segment_revenue")
            profit, profit_fx = converted(profit_fact, start, end, "segment_profit")
            total, total_fx = totals.get((start, end), (None, {}))
            row = {
                "ticker": ticker,
                "accession": accession,
                "filed": filed,
                "period_end": end,
                "period_start": start,
                "period_len": length,
                "axis": axis,
                "segment_raw": member,
                "segment_qname": qname,
                "segment_std": None,
                "revenue": revenue,
                "segment_profit": profit,
                "profit_basis": str(profit_fact.qname) if profit_fact is not None else None,
                "margin_pct": profit / revenue * 100
                if profit is not None and revenue is not None and revenue > 0
                else None,
                "yoy_pct": None,
                "share_pct": revenue / total * 100 if revenue is not None and total is not None and total > 0 else None,
                "recast_group": None,
                "health_codes": ["segment_unmapped"] if axis == "business" else [],
                "evidence": {
                    "currency": currency,
                    "fx": fx_evidence,
                    "profit_fx": profit_fx,
                    "consolidated_fx": total_fx,
                    "profit_reason": "multiple_profit_elements"
                    if len(profits) > 1
                    else "profit_element_missing"
                    if not profits
                    else None,
                    "member_identity": member_by_fact[id(facts[0])],
                    "revenue_basis": str(revenue_fact.qname) if revenue_fact is not None else None,
                    "revenue_context": revenue_fact.context.id if revenue_fact is not None else None,
                    "revenue_disclosure": "reported_nil"
                    if revenue_fact is not None and revenue_fact.isNil
                    else "reported"
                    if revenue_fact is not None
                    else "profit_only",
                    "sum_included": revenue_fact is not None,
                    "revenue_sum_weight": 1,
                    "auxiliary_basis": selected_basis,
                },
            }
            output.append(row)
            selected_facts[id(row)] = revenue_fact
        for key, _initial_total in consolidated.items():
            rows = [
                r
                for r in output
                if (r["period_start"], r["period_end"]) == key and r["axis"] in {"business", "elimination"}
            ]
            business = [r for r in rows if r["axis"] == "business"]
            members = {r["evidence"]["member_identity"] for r in business}
            for row in business:
                children = descendants(business_graph, row["evidence"]["member_identity"]) & members
                if children:
                    row["axis"] = "summary"
                    row["evidence"].update(
                        sum_included=False,
                        summary_members=sorted(children),
                        hierarchy_roles=sorted(
                            {
                                role
                                for child in children
                                for role in business_edges.get((row["evidence"]["member_identity"], child), [])
                            }
                        ),
                    )
            business = [r for r in business if r["axis"] == "business"]
            if not business:
                continue
            revenue_names = {
                selected_facts[id(r)].qname.localName for r in business if selected_facts[id(r)] is not None
            }
            candidates = [f for f in all_totals[key] if f.qname.localName in revenue_names] or all_totals[key]
            total_fact = min(candidates, key=lambda f: (REVENUE.index(f.qname.localName), f.context.id))
            total, total_fx = converted(total_fact, *key, "consolidated_revenue")
            basis = selected_bases.get(key)
            if basis is None:
                operating = {
                    r["evidence"]["member_identity"]
                    for r in rows
                    if r["axis"] == "elimination" and r["segment_raw"] == "OperatingSegmentsMember"
                }
                if len(operating) == 1:
                    basis = next(iter(operating))
            subtotal_facts = [
                selected_facts[id(r)]
                for r in rows
                if r["axis"] == "elimination"
                and r["evidence"]["member_identity"] == basis
                and selected_facts[id(r)] is not None
            ]
            business_positions = [p for r in business for p in fact_positions(positions, selected_facts[id(r)])]
            subtotal_positions = [p for f in subtotal_facts for p in fact_positions(positions, f)]
            scopes = {(p["table"], p["section"]) for p in business_positions + subtotal_positions}
            singles = {
                conso_by_fact.get(id(selected_facts[id(r)]), (None, False))[0]
                for r in rows
                if r["axis"] == "elimination"
                and selected_facts[id(r)] is not None
                and not conso_by_fact.get(id(selected_facts[id(r)]), (None, False))[1]
            }
            for row in rows:
                fact = selected_facts[id(row)]
                row["share_pct"] = (
                    row["revenue"] / total * 100
                    if row["revenue"] is not None and total is not None and total > 0
                    else None
                )
                row["evidence"].update(
                    consolidated_revenue=total, consolidated_basis=str(total_fact.qname), consolidated_fx=total_fx
                )
                if row["axis"] != "elimination" or fact is None:
                    continue
                conso, compound = conso_by_fact.get(id(fact), (None, False))
                if conso == basis or conso and basis and conso in descendants(conso_graph, basis):
                    row["evidence"].update(sum_included=False, sum_exclusion="within_selected_operating_subtotal")
                    row["axis"] = "summary"
                    continue
                if compound and conso in singles:
                    row["evidence"].update(sum_included=False, sum_exclusion="reconciliation_component_has_total")
                    row["axis"] = "summary"
                    continue
                locations = fact_positions(positions, fact)
                if (
                    scopes
                    and locations
                    and not any(same_column(p, b) for p in locations for b in business_positions + subtotal_positions)
                ):
                    row["evidence"].update(
                        sum_included=False, sum_exclusion="different_original_revenue_section_or_column"
                    )
                    continue
                weight, weight_evidence = rendered_weight(
                    fact,
                    positions,
                    subtotal_positions=subtotal_positions,
                    total_positions=fact_positions(positions, total_fact),
                    member=conso.split("}")[-1] if conso else None,
                )
                row["evidence"].update(revenue_sum_weight=weight, weight_source=weight_evidence)
            # An explicit monetary reconciliation takes priority. When the
            # filing instead reports a dimensionless revenue component, use
            # its original calculation arc and fact, never the residual.
            if not any(r["axis"] == "elimination" and r["evidence"]["sum_included"] for r in rows):
                components = calculation_components(model, total_fact, set(REVENUE))
                plain = plain_reconciliations(model, primary_html, rows, total_fact, components, key)
                supplements = (
                    [(anchor, 1, evidence, member, value) for member, anchor, value, evidence in plain]
                    if plain
                    else [(fact, weight, evidence, None, None) for fact, weight, evidence in components]
                )
                for fact, weight, evidence, table_member, table_value in supplements:
                    value, fx_evidence = converted(fact, *key, "segment_reconciliation")
                    if table_member is not None:
                        value = value * table_value / numeric(fact)
                    row = {
                        "ticker": ticker,
                        "accession": accession,
                        "filed": filed,
                        "period_start": key[0],
                        "period_end": key[1],
                        "period_len": context_period(fact.context)[2],
                        "axis": "elimination",
                        "segment_raw": table_member.split("}")[-1] + ":TableRevenue"
                        if table_member
                        else fact.qname.localName,
                        "segment_qname": str(fact.qname),
                        "segment_std": None,
                        "revenue": value,
                        "segment_profit": None,
                        "profit_basis": None,
                        "margin_pct": None,
                        "yoy_pct": None,
                        "share_pct": value / total * 100 if value is not None and total else None,
                        "recast_group": None,
                        "health_codes": [],
                        "evidence": {
                            "member_identity": qkey(fact.qname),
                            "revenue_basis": str(fact.qname),
                            "revenue_context": fact.context.id,
                            "revenue_disclosure": "original_table"
                            if table_member
                            else "reported_nil"
                            if fact.isNil
                            else "reported",
                            "sum_included": True,
                            "revenue_sum_weight": weight,
                            "weight_source": evidence,
                            "fx": fx_evidence,
                            "consolidated_revenue": total,
                            "consolidated_basis": str(total_fact.qname),
                            "consolidated_fx": total_fx,
                        },
                    }
                    rows.append(row)
                    output.append(row)
            participating = [r for r in rows if r["evidence"]["sum_included"]]
            if total is None or total <= 0:
                for row in rows:
                    row["evidence"]["sum_check_reason"] = "consolidated_revenue_nonpositive_or_missing"
            elif not segment_sum_ok(
                [r["revenue"] for r in participating if r["axis"] == "business"],
                [
                    r["revenue"] * r["evidence"]["revenue_sum_weight"] if r["revenue"] is not None else None
                    for r in participating
                    if r["axis"] == "elimination"
                ],
                total,
            ):
                for row in rows:
                    row["health_codes"].append("segment_sum_mismatch")
        if not any(row["axis"] == "business" for row in output):
            code = "single_segment" if single else "segment_missing"
            output.append(
                {
                    "ticker": ticker,
                    "accession": accession,
                    "filed": filed,
                    "period_end": max((k[1] for k in consolidated), default=None),
                    "period_start": None,
                    "period_len": None,
                    "axis": "evidence",
                    "segment_raw": None,
                    "segment_std": None,
                    "revenue": None,
                    "segment_profit": None,
                    "profit_basis": None,
                    "margin_pct": None,
                    "yoy_pct": None,
                    "share_pct": None,
                    "recast_group": None,
                    "health_codes": [code],
                    "evidence": {"single_segment_count": 1 if single else None},
                }
            )
        for row in output:
            row["evidence"]["parse_contract"] = PARSE_CONTRACT
            row["evidence"]["primary_sha256"] = primary_sha256
            row["evidence"]["original_revenue_positions"] = fact_positions(positions, selected_facts.get(id(row)))
        return output
    finally:
        model.close()
        controller.close()


def apply_recast(current, previous, *, comparative):
    result = deepcopy(current)
    old = {r["segment_raw"]: r for r in previous if r.get("axis") == "business"}
    new = {r["segment_raw"] for r in current if r.get("axis") == "business"}
    comparable = {r["segment_raw"]: r for r in comparative if r.get("axis") == "business"}
    changed = bool(old) and (set(old) != new or comparable and set(comparable) != set(old))
    for name, row in comparable.items():
        prior = old.get(name)
        if prior and prior.get("revenue") is not None and row.get("revenue") is not None:
            base = prior["revenue"]
            delta = abs(row["revenue"] - base)
            if (base == 0 and delta != 0) or base != 0 and delta / abs(base) > 0.01 + 1e-12:
                changed = True
    old_group = next((r.get("recast_group") for r in previous if r.get("recast_group")), None)
    group = (
        old_group
        if old_group and not changed
        else hashlib.sha256(
            json.dumps(sorted(new)).encode()
            + str([(r.get("period_end"), r.get("accession")) for r in current]).encode()
        ).hexdigest()[:20]
    )
    for row in result:
        row["recast_group"] = group
        row.setdefault("health_codes", [])
        row["yoy_pct"] = None
        if changed:
            row["health_codes"].append("segment_recast")
        prior = old.get(row.get("segment_raw"))
        if (
            not changed
            and prior
            and prior.get("recast_group") == group
            and prior.get("revenue")
            and row.get("revenue") is not None
        ):
            row["yoy_pct"] = (row["revenue"] / prior["revenue"] - 1) * 100
    return result
