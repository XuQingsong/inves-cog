"""Offline A-030 verification of a bounded read-only production input export."""

import argparse
import json
import resource
import time
from datetime import date, datetime
from datetime import time as wall_time
from pathlib import Path
from zoneinfo import ZoneInfo

from inves_cog.ingest.fundamentals.repository import state_from_row
from inves_cog.valuation_v1.ceiling_daily import band_settings, calculate_ceiling
from inves_cog.valuation_v1.inputs import financial_inputs, selected_consensus
from inves_cog.valuation_v1.lifecycle import classify
from inves_cog.valuation_v1.listed_units import normalize_listing


def verify(raw):
    day = date.fromisoformat(raw["day"])
    cutoff = datetime.combine(day, wall_time(22, 30), ZoneInfo("America/New_York"))
    prices = {r["ticker"]: r["close"] for r in raw["bars"]}
    profiles = {r["ticker"]: r["sic"] for r in raw["profiles"]}
    tiers = {r["ticker"]: {"attack": "进攻", "defense": "防守", "normal": "普通"}.get(r["tier"]) for r in raw["tiers"]}
    states = {}
    for r in raw["states"]:
        r = {
            **r,
            "filed": date.fromisoformat(r["filed"]),
            "period_end": date.fromisoformat(r["period_end"]) if r["period_end"] else None,
        }
        r["field_sources"] = {k: v for k, v in r["field_sources"].items() if v is not None}
        states[r["ticker"]] = state_from_row(r)
    output, manual = [], []
    start = time.perf_counter()
    for e in raw["entities"]:
        ticker = e["ticker"]
        entity = {**e, "sic": profiles.get(ticker)}
        state = states.get(ticker)
        inputs = financial_inputs(state, [state] if state else [], entity, as_of=cutoff)
        inputs["price"] = prices.get(ticker)
        forecast = selected_consensus([r for r in raw["consensus"] if r["ticker"] == ticker], day, cutoff=cutoff)
        inputs = normalize_listing(inputs, state, forecast, day)
        if forecast and not inputs.get("listed_unit_audit") and str(forecast.get("fy_cy") or "") >= str(day):
            inputs.update(fy1_eps=forecast.get("eps_cy"), fy2_eps=forecast.get("eps_ny"))
        kind = classify(inputs)
        row = calculate_ceiling(inputs, day=day, kind=kind, tier=tiers.get(ticker), bands=band_settings(), asof=cutoff)
        output.append(row)
        if ticker in {"NVDA", "GOOGL", "MU", "INTC", "KO"}:
            shares, price, debt = (inputs.get(k) for k in ("diluted_shares", "price", "net_debt"))
            proof = dict(
                ticker=ticker,
                close=price,
                diluted_shares=shares,
                net_debt=debt,
                revenue=inputs.get("rev_ttm"),
                operating_margin_pct=inputs.get("op_margin_ttm"),
                fy1_eps=inputs.get("fy1_eps"),
                method=row["method"],
            )
            if None not in (shares, price, debt):
                proof["manual_ev"] = price * shares + debt
                proof["ev_error"] = proof["manual_ev"] - row["ev"] if row["ev"] is not None else None
            if row["m"] is not None:
                # Independent geometric-series PV arithmetic, rather than calling the inverse again.
                m, r = row["m"], row["r"]
                growth = m**0.1
                q = growth / (1 + r)
                pv_growth = q * (1 - q**10) / (1 - q) if abs(1 - q) > 1e-12 else 10
                multiple = (pv_growth + m / r / (1 + r) ** 10) / growth
                proof.update(
                    manual_multiple=multiple,
                    reported_ev_over_next_profit=row["ev"] / row["next_profit"],
                    multiple_error=multiple - row["ev"] / row["next_profit"],
                )
            manual.append(proof)
    return dict(
        day=str(day),
        source="bounded production read-only export",
        count=len(output),
        compute_seconds=time.perf_counter() - start,
        process_peak_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024,
        rows=output,
        manual_checks=manual,
        limitations=["當日規則A層級缺失時用8%並明示", "先前校准日期不得用於更早的歷史档位"],
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    result = verify(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"rows", "manual_checks"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
