"""Dry-run Visa EPS-only repair and tier-coverage verification on public input exports."""

import argparse
import json
import math
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from inves_cog.clock import SystemClock
from inves_cog.ingest.fundamentals.eps_repair import repair_missing_eps
from inves_cog.ingest.fundamentals.extractors import extract_state
from inves_cog.ingest.fundamentals.instances import InstanceLoader
from inves_cog.ingest.fundamentals.repairs import dimension_allowed, merge_facts
from inves_cog.ingest.fundamentals.repository import state_from_row
from inves_cog.ingest.fundamentals.state import StateStore
from inves_cog.trading.scoring import score_history


def cached_eps_facts(path, filing):
    """Read only disclosed EPS from cached XML; no external schemas or network needed."""
    ns = {}
    for _, (prefix, uri) in ET.iterparse(path, events=["start-ns"]):
        if prefix in ns and ns[prefix] != uri:
            raise ValueError("ambiguous cached EPS namespace")
        ns[prefix] = uri
    root = ET.parse(path).getroot()
    x = "{http://www.xbrl.org/2003/instance}"
    xd = "{http://xbrl.org/2006/xbrldi}"

    def qname(value):
        prefix, _, local = (value or "").rpartition(":")
        return SimpleNamespace(localName=local, namespaceURI=ns.get(prefix, ""))

    contexts = {}
    for context in root.findall(x + "context"):
        issuer = context.findtext(x + "entity/" + x + "identifier", "")
        if not issuer.isdigit() or int(issuer) != int(filing["cik"]):
            continue
        start = context.findtext(x + "period/" + x + "startDate")
        end = context.findtext(x + "period/" + x + "endDate")
        if not start or not end or date.fromisoformat(end) > date.fromisoformat(str(filing["filing_date"])):
            continue
        dims, labels = {}, {}
        for member in context.findall(".//" + xd + "explicitMember"):
            axis, value = qname(member.get("dimension")), qname(member.text)
            dims[SimpleNamespaceKey(axis)] = SimpleNamespace(memberQname=value)
            labels[member.get("dimension")] = member.text
        if context.findall(".//" + xd + "typedMember"):
            continue
        contexts[context.get("id")] = (start, end, dims, labels)
    units = set()
    for unit in root.findall(x + "unit"):
        numerator = unit.findall(x + "divide/" + x + "unitNumerator/" + x + "measure")
        denominator = unit.findall(x + "divide/" + x + "unitDenominator/" + x + "measure")
        if len(numerator) == len(denominator) == 1:
            n, d = qname(numerator[0].text), qname(denominator[0].text)
            if (
                n.localName == "USD"
                and n.namespaceURI == "http://www.xbrl.org/2003/iso4217"
                and d.localName == "shares"
            ):
                units.add(unit.get("id"))
    rows = []
    for fact in root:
        uri, _, name = fact.tag[1:].partition("}")
        if name != "EarningsPerShareDiluted" or not uri.startswith("http://fasb.org/us-gaap/"):
            continue
        if fact.get("unitRef") not in units or fact.get("contextRef") not in contexts:
            continue
        start, end, dims, labels = contexts[fact.get("contextRef")]
        model = SimpleNamespace(qname=SimpleNamespace(localName=name), context=SimpleNamespace(qnameDims=dims))
        if not dimension_allowed(model, "V"):
            continue
        try:
            value = float(fact.text)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        row = dict(
            start=start,
            end=end,
            val=value,
            filed=str(filing["filing_date"]),
            accn=filing["accession"],
            form=filing["form"],
            origin="instance_parsed",
        )
        if dims:
            row.update(d9_only=True, dimensions=labels)
        rows.append(row)
    return (
        {"facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": rows}}}}} if rows else {"facts": {}}
    )


class SimpleNamespaceKey:
    def __init__(self, q):
        self.localName, self.namespaceURI = q.localName, q.namespaceURI


def verify(history, companyfacts, cache):
    def no_network(*args, **kwargs):
        raise ValueError("dry-run requires cached official filing attachments")

    loader = InstanceLoader(sec=SimpleNamespace(get=no_network), cache_dir=cache, offline=True)
    raw = json.loads(companyfacts.read_text())
    originals = []
    for row in history["states"]:
        row = {
            **row,
            "filed": date.fromisoformat(row["filed"]),
            "period_end": date.fromisoformat(row["period_end"]) if row["period_end"] else None,
        }
        row["field_sources"] = {k: v for k, v in row["field_sources"].items() if v is not None}
        originals.append(state_from_row(row))
    filings = [{**f, "filing_date": date.fromisoformat(f["filing_date"])} for f in history["filings"]]
    by_day = {s.filed: s for s in originals}
    accumulated, repairs, missing = {"facts": {}}, {}, []
    for filing in sorted(filings, key=lambda f: f["filing_date"]):
        if not (cache / filing["accession"] / "instance-path").is_file():
            missing.append(str(filing["filing_date"]))
            continue
        accumulated = merge_facts(accumulated, cached_eps_facts(loader.path(filing), filing))
        candidate = extract_state(
            raw, ticker="V", as_of=filing["filing_date"], filings=filings, instance_facts=accumulated
        )
        original = by_day.get(candidate.filed)
        if original is None:
            continue
        patched = repair_missing_eps(original, candidate)
        if patched is not None:
            repairs[original.filed] = patched
    patched = [repairs.get(s.filed, s) for s in originals]
    bars = [{**b, "trade_date": date.fromisoformat(b["trade_date"])} for b in history["bars"]]
    result = {}
    for name, states in [("before", originals), ("after", patched)]:
        store = StateStore(states)
        scores = score_history("V", bars, state_asof=store.state_asof)
        result[name] = {
            "financial_states": len(states),
            "eps_states": sum(s.values.get("eps_ttm") is not None for s in states),
            "tier_days": sum(s["tier"] is not None for s in scores),
            "trading_days": len(scores),
        }
    result.update(
        generated_at=str(SystemClock().now_utc()),
        status="dry_run_only_no_database_writes",
        missing_cached_filing_dates=missing,
        changes=[
            {
                "ticker": "V",
                "filed": str(day),
                "period_end": str(s.period_end),
                "eps_ttm": s.values["eps_ttm"],
                "eps_growth": s.values["eps_growth"],
                "health_codes": s.health_codes,
                "field_sources_patch": {k: s.field_sources[k] for k in ("eps_ttm", "eps_growth", "eps_repair_a030")},
            }
            for day, s in sorted(repairs.items())
        ],
    )
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("history", type=Path)
    p.add_argument("companyfacts", type=Path)
    p.add_argument("cache", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    out = verify(json.loads(a.history.read_text()), a.companyfacts, a.cache)
    a.output.write_text(json.dumps(out, ensure_ascii=False, default=str, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in {"changes", "missing_cached_filing_dates"}}))


if __name__ == "__main__":
    main()
