"""PIT foreign announcements, isolated from legacy and monthly revenue."""

from copy import deepcopy
from datetime import date, timedelta

from lxml import html

from inves_cog.ingest.fundamentals import interim_parse as rules
from inves_cog.ingest.fundamentals.extractors import day

BASIS = {
    "TSM": "ordinary share; 1 ADS = 5 ordinary shares",
    "ASML": "ordinary share; NASDAQ registered ordinary share 1:1; ADS not applicable",
    "NOK": "ordinary share; 1 ADS = 1 ordinary share",
    "ARM": "ordinary share; 1 ADS = 1 ordinary share",
    "SKHY": "ordinary share; ADS ratio not established by this announcement",
}


def parse_interim(raw, *, ticker, accession, filed, source_exhibit):
    base = dict(
        ticker=ticker, accession=accession, filed=day(filed), eps_basis=BASIS[ticker], source_exhibit=source_exhibit
    )
    try:
        records = {"ASML": rules.asml, "TSM": rules.tsm, "NOK": rules.nok, "ARM": rules.arm, "SKHY": rules.skhy}[
            ticker
        ](html.fromstring(raw.encode() if isinstance(raw, str) else raw))
    except (ValueError, TypeError, IndexError, AttributeError, KeyError, StopIteration) as exc:
        records = [
            {
                "period_end": None,
                "currency": None,
                **dict.fromkeys(rules.FIELDS),
                "parse_status": "interim_unparsed:" + str(exc),
            }
        ]
    for row in records:
        missing = [key for key in rules.FIELDS if row.get(key) is None]
        if row.get("derivation"):
            row["eps_basis"] = base["eps_basis"] + "; " + row["derivation"]
        row.setdefault("parse_status", "interim_unparsed:missing " + ",".join(missing) if missing else "parsed")
    return [{**base, **row} for row in records]


def quarter_start(end):
    month = ((end.month - 1) // 3) * 3 + 1
    # ASML fiscal quarters use 52/53 weeks rather than calendar quarter ends.
    return date(end.year, month, 1)


def visible_quarters(rows, as_of):
    chosen = {}
    for row in rows:
        end = row.get("period_end")
        if row.get("parse_status") != "parsed" or not end or day(row["filed"]) > as_of or day(end) > as_of:
            continue
        end = day(end)
        old = chosen.get(end)
        if old is None or (day(row["filed"]), row["accession"]) > (day(old["filed"]), old["accession"]):
            chosen[end] = row
    return [chosen[end] for end in sorted(chosen)[-4:]]


def apply_interims(state, rows, *, as_of, fx):
    result = deepcopy(state)
    as_of = day(as_of)
    if state.extractor != "fixed":
        return result
    selected = visible_quarters(rows, as_of)
    if state.period_end and selected and day(selected[-1]["period_end"]) <= state.period_end:
        return result
    if len(selected) != 4 or any(
        not 80 <= (day(b["period_end"]) - day(a["period_end"])).days <= 120
        for a, b in zip(selected, selected[1:], strict=False)
    ):
        return result
    totals = dict.fromkeys(rules.FIELDS, 0.0)
    evidence = []
    series = {key: {} for key in ("rev", "gp", "op", "ni", "eps")}
    aliases = dict(zip(rules.FIELDS, series, strict=True))
    for row in selected:
        end = day(row["period_end"])
        prior = [
            day(r["period_end"])
            for r in rows
            if r.get("period_end") and day(r["filed"]) <= as_of and day(r["period_end"]) < end
        ]
        if state.ticker == "ASML":
            if not prior or not 80 <= (end - max(prior)).days <= 120:
                raise ValueError("ASML fiscal quarter start is not established by prior disclosed end")
            start = max(prior) + timedelta(days=1)
        else:
            start = quarter_start(end)
        converted = {}
        for key in rules.FIELDS:
            value, proof = fx.convert(row[key], currency=row["currency"], start=start, end=end, as_of=as_of, field=key)
            totals[key] += value
            series[aliases[key]][end] = {
                "val": value,
                "derivation": "ytd_derived" if "ytd6_minus_q2" in row["eps_basis"] else None,
            }
            converted[key] = proof
        evidence.append({**row, "period_start": start, "fx": converted})
    revenue = totals["revenue"]
    result.values.update(
        rev_ttm=revenue,
        ni_ttm=totals["net_income"],
        eps_ttm=totals["eps_diluted"],
        rev_period=str(selected[-1]["period_end"]),
        gross_margin=totals["gross_profit"] / revenue * 100 if revenue else None,
        op_margin_ttm=totals["operating_income"] / revenue * 100 if revenue else None,
    )
    # Annual cash flows and growth cannot be labelled as the new quarterly TTM.
    for key in [
        "rev_growth",
        "rev_q_yoy",
        "rev_accel_pp",
        "eps_growth",
        "fcf_ttm",
        "fcf_margin",
        "fcf_conversion",
        "fcf_yield",
        "fcf_margin_change_pp",
        "gross_margin_change_pp",
        "roe",
        "net_debt_fcf",
        "pe",
        "ps",
        "peg_rev_approx",
    ]:
        result.values[key] = None
        result.field_sources[key] = {
            "reason": "interim statement does not supply aligned cash flows, valuation or prior TTM"
        }
    result.field_sources["interim_ttm"] = {
        "annual_accession": state.accession,
        "annual_period_end": state.period_end,
        "annual_values": {k: state.values.get(k) for k in ("rev_ttm", "ni_ttm", "eps_ttm")},
        "method": "four disclosed quarters anchored to latest annual; each quarter translated separately",
        "quarters": evidence,
    }
    result.period_end = day(selected[-1]["period_end"])
    result.filed = max(state.filed, *(day(r["filed"]) for r in selected))
    result.accession = max(selected, key=lambda r: (day(r["filed"]), r["accession"]))["accession"]
    result.form, result.fiscal_period = "6-K", "TTM"
    codes = set(state.health_codes) - {"annual_basis", "stale_fundamentals", "ok"}
    codes.add("interim_unaudited")
    result.values.pop("fund_unreliable", None)
    result.values["data_flags"] = []
    if (as_of - result.period_end).days > 180:
        codes.add("stale_fundamentals")
    from inves_cog.ingest.fundamentals.plausibility import violations

    failed = violations(result.values, series)
    codes.discard("implausible_value")
    if failed:
        codes.add("implausible_value")
        result.field_sources["implausible_value"] = {"violations": failed}
    for field in ("rev_ttm", "ni_ttm", "eps_ttm", "gross_margin", "op_margin_ttm"):
        result.field_sources[field] = {"method": "interim_ttm", "quarters": evidence}
    if all(result.values.get(k) is not None for k in ("rev_ttm", "eps_ttm", "shares")):
        codes.discard("core_field_missing")
    result.health_codes = sorted(codes)
    return result


def parse_monthly(raw, *, accession, filed):
    import re

    content = rules.text(html.fromstring(raw.encode() if isinstance(raw, str) else raw))
    title = re.search(r"TSMC\s+(\w+)\s+(20\d{2})\s+Revenue Report", content)
    if not title:
        raise ValueError("TSM monthly revenue header missing")
    month = date(int(title[2]), rules.MONTHS[title[1].lower()[:3]], 1)
    # The detailed statutory table is in NT$ thousands; the press summary is
    # rounded to NT$ millions and is deliberately not preferred.
    section = content.split("Revenue (in NT$ thousands)", 1)
    if len(section) != 2:
        raise ValueError("TSM monthly statutory NT$ thousand table missing")
    value = re.search(r"(?<!~)\b" + title[1][:3] + r"\.?\s+Net Revenue\s+([\d,]+)", section[1])
    if not value:
        raise ValueError("TSM monthly current-period revenue missing")
    return dict(
        ticker="TSM",
        month=month,
        revenue=float(value[1].replace(",", "")) * 1000,
        currency="TWD",
        filed=day(filed),
        accession=accession,
    )
