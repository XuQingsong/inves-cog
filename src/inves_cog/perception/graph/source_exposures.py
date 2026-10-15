"""Explicit single-business and interim-source exceptions, preserving M2 provenance."""

import hashlib
import json
import math
from datetime import date

from inves_cog.ingest.fundamentals.fx import FXGap
from inves_cog.ingest.fundamentals.interims import quarter_start


def day(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def single_business_hdd(state, *, as_of):
    """Q-M6-9 and user's STX clarification; never generalize to mixed businesses."""
    if not state or state.get("ticker") not in {"STX", "WDC"} or state.get("extractor") != "fixed":
        return None
    if not state.get("period_end") or day(state["filed"]) > as_of or day(state["period_end"]) > as_of:
        return None
    components = state.get("field_sources", {}).get("rev_ttm", {}).get("components", [])
    if (
        state.get("form") != "10-K"
        or not finite(state.get("rev_ttm"))
        or not components
        or any(row.get("unit") != "USD" for row in components)
        or max(day(row["end"]) for row in components) != day(state["period_end"])
    ):
        return None
    return {
        "row_id": f"fin_state:{state['ticker']}:fixed:{state['filed']}",
        "ticker": state["ticker"],
        "accession": state["accession"],
        "filed": state["filed"],
        "period_end": state["period_end"],
        "segment_raw": "HDD（单一业务，合并营收）",
        "revenue": state["rev_ttm"],
        "evidence": {
            "source_table": "fundamentals.fin_state",
            "source_field": "rev_ttm",
            "currency": "USD",
            "components": components,
            "flags": ["single_business_consolidated_revenue"],
            "basis_note": "单一业务；按用户确认的 Q-M6-9 口径以合并营收作为 HDD 暴露，非另行披露的产品分部金额",
        },
    }


def quarterly_ttm_source(rows, *, as_of, fx):
    selected = {}
    for row in rows:
        if (
            row.get("ticker") != "SKHY"
            or row.get("parse_status") != "parsed"
            or not row.get("period_end")
            or not finite(row.get("revenue"))
            or day(row["filed"]) > as_of
            or day(row["period_end"]) > as_of
        ):
            continue
        end = day(row["period_end"])
        old = selected.get(end)
        if old is None or (day(row["filed"]), row["accession"]) > (day(old["filed"]), old["accession"]):
            selected[end] = row
    quarters = [selected[end] for end in sorted(selected)[-4:]]
    report = {"ticker": "SKHY", "source": None, "status": "无法检验", "available_period_ends": sorted(selected)}
    if len(quarters) != 4:
        return {**report, "reason": "insufficient_quarters"}
    gaps = [
        {
            "previous": a["period_end"],
            "next": b["period_end"],
            "days": (day(b["period_end"]) - day(a["period_end"])).days,
        }
        for a, b in zip(quarters, quarters[1:], strict=False)
        if not 80 <= (day(b["period_end"]) - day(a["period_end"])).days <= 120
    ]
    if gaps:
        return {**report, "reason": "nonconsecutive_quarters", "gaps": gaps}
    total, proof = 0.0, []
    try:
        for row in quarters:
            end = day(row["period_end"])
            converted, evidence = fx.convert(
                row["revenue"],
                currency=row["currency"],
                start=quarter_start(end),
                end=end,
                as_of=as_of,
                field="revenue",
            )
            total += converted
            proof.append({**row, "usd_revenue": converted, "fx": evidence})
    except FXGap as exc:
        return {**report, "reason": "fx_gap", "fx_gap": exc.detail}
    latest = max(quarters, key=lambda r: (day(r["filed"]), r["accession"]))
    identity = hashlib.sha256(json.dumps(proof, sort_keys=True, default=str).encode()).hexdigest()
    source = {
        "row_id": "interim_ttm:" + identity,
        "ticker": "SKHY",
        "accession": latest["accession"],
        "filed": latest["filed"],
        "period_end": quarters[-1]["period_end"],
        "segment_raw": "合并营收 TTM（四个连续披露季度）",
        "revenue": total,
        "evidence": {
            "source_table": "fundamentals.interim_results",
            "currency": "USD",
            "quarters": proof,
            "flags": ["four_interim_quarters_ttm"],
        },
    }
    return {**report, "source": source, "status": "ok", "reason": None}
