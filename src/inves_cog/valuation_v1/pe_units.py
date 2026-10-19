"""Reviewed source-unit repairs; no price target, formula or trading change."""

import json
from functools import lru_cache
from pathlib import Path

from inves_cog.valuation_v1.calculations import pe_percentiles
from inves_cog.valuation_v1.eps_units import normalize_eps
from inves_cog.valuation_v1.listed_units import historical_eps


@lru_cache(maxsize=1)
def contract():
    return json.loads((Path(__file__).resolve().parents[3] / "config/valuation_pe_units.json").read_text())


def historical_multiples(source, ticker, as_of):
    rows, repaired = [], []
    events = [e for e in contract()["events"] if e["ticker"] == ticker]
    changed = unknown = 0
    cache = {}
    for bar in source["bars"].get(ticker, []):
        if bar["trade_date"] >= as_of:
            continue
        state = source["store"].state_asof(ticker, bar["trade_date"], "fixed")
        eps = historical_eps(state, ticker, bar["trade_date"])
        row = {"date": bar["trade_date"], "close": bar["close"], "eps_ttm": eps}
        rows.append(row)
        if not events or state is None:
            repaired.append(row)
            continue
        # A daily raw close changes units on the first split-adjusted trading
        # session, not the record date, announcement or preceding after-close.
        active = [e for e in events if e["split_trading_on"] <= str(bar["trade_date"])]
        key = (state.filed, state.period_end, tuple(e["id"] for e in active))
        if key in cache:
            value, audit = cache[key]
        else:
            value, audit = normalize_eps(eps, state.field_sources.get("eps_ttm", {}), active, bar["trade_date"])
            # Valid provenance is fixed within one filing and trading-unit
            # interval. Unknown/future provenance is never cached as valid.
            if audit["status"] != "unknown":
                cache[key] = value, audit
        changed += value is not None and value != eps
        unknown += audit["status"] == "unknown"
        repaired.append({**row, "eps_ttm": value})
    baseline = pe_percentiles(rows, as_of)
    result = pe_percentiles(repaired, as_of) if events else baseline
    if events:
        result["historical_pe_unit_audit"] = {
            "contract": contract()["contract"],
            "events": [e["id"] for e in events],
            "changed_samples": changed,
            "unknown_samples_excluded": unknown,
            "peer_inputs": "unchanged A012 scope; own historical samples repaired only",
        }
    return result, baseline


def annual_basis_errors(state, states, ticker, as_of):
    if ticker not in contract()["annual_basis_review_scope"] or state is None or state.period_end is None:
        return []
    anchors = [(s.field_sources.get("interim_ttm", {}).get("annual_period_end"), s) for s in states if s.filed <= as_of]
    newer = [(end, s) for end, s in anchors if end and str(state.period_end) < end <= str(as_of)]
    if not newer:
        return []
    end, evidence = max(newer, key=lambda pair: (pair[0], pair[1].filed))
    return [
        {
            "field": "financial_annual_basis",
            "reason": (
                f"年度输入过时：当前{state.period_end}，已可见年报锚点{end}；"
                "现有状态未提供该年度对齐的现金流、稀释股本与单位来源，不混用旧年度或期末普通股"
            ),
            "source": {"accession": evidence.accession, "filed": str(evidence.filed), "annual_period_end": end},
        }
    ]
