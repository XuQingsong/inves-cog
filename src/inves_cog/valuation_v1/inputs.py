"""Explicit M2 fixed input transformations; never substitute scores or share classes."""

from datetime import date, datetime, time, timedelta, timezone
from statistics import median

from inves_cog.valuation_v1.calculations import settings


def day(value):
    return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


def consensus_inputs(rows, as_of, *, cutoff=None):
    cutoff = cutoff or datetime.combine(as_of + timedelta(days=1), time.min, timezone.utc)
    visible = []
    for r in rows:
        captured = r.get("captured_at")
        if isinstance(captured, str):
            captured = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if day(r["as_of"]) <= as_of and (captured is None or (captured.tzinfo is not None and captured < cutoff)):
            visible.append(r)
    out = {
        "eps_ntm": None,
        "rev_ntm_consensus": None,
        "consensus_next_year_eps_growth": None,
        "consensus_reason": "没有当时可见的一致预期快照",
    }
    if not visible:
        return out
    latest = max(
        visible, key=lambda r: (day(r["as_of"]), r.get("captured_at") or datetime.min.replace(tzinfo=timezone.utc))
    )
    out.update(consensus_as_of=str(latest["as_of"]), consensus_source=latest.get("source"))
    cy, ny = latest.get("fy_cy"), latest.get("fy_ny")
    if cy is None or ny is None or day(cy) < as_of or day(ny) <= day(cy):
        out["consensus_reason"] = "快照财年缺失或已过期"
        return out
    cy = day(cy)
    months = max(0, min(12, (cy.year - as_of.year) * 12 + cy.month - as_of.month))
    weight = months / 12
    out["ntm_current_year_weight"] = weight
    for prefix, output in [("eps", "eps_ntm"), ("rev", "rev_ntm_consensus")]:
        current, future = latest.get(prefix + "_cy"), latest.get(prefix + "_ny")
        if current is not None and future is not None:
            out[output] = current * weight + future * (1 - weight)
    eps, future = latest.get("eps_cy"), latest.get("eps_ny")
    if eps is not None and eps > 0 and future is not None:
        out["consensus_next_year_eps_growth"] = (future / eps - 1) * 100
    out["consensus_reason"] = None if out["eps_ntm"] is not None else "最新快照缺当年或次年EPS；不使用更早快照替代"
    return out


def diluted_shares(value, source):
    if value is None or value <= 0:
        return None
    methods = {"diluted_weighted_approximation", "diluted_weighted_multiclass"}
    components = source.get("components", [])
    tags = [r.get("tag", "") for r in components] + [source.get("tag", "")]
    return (
        value
        if source.get("method") in methods
        or any("WeightedAverageNumberOfDilutedSharesOutstanding" in tag for tag in tags)
        else None
    )


def financial_inputs(state, states, entity):
    if state is None:
        return {"ticker": entity["ticker"], "input_reason": "M2 fixed状态缺失"}
    values = state.values
    out = {
        **values,
        "ticker": state.ticker,
        "sic": entity.get("sic"),
        "financial_filed": str(state.filed),
        "financial_period": str(state.period_end),
        "financial_health_codes": state.health_codes,
        "share_basis": state.field_sources.get("shares", {}),
    }
    out["diluted_shares"] = diluted_shares(values.get("shares"), out["share_basis"])
    if out["diluted_shares"] is None:
        out["diluted_shares_reason"] = "M2仅有期末普通股或缺股本，未提供可核实的稀释加权股本"
    out["fcf_per_share"] = (
        values["fcf_ttm"] / out["diluted_shares"]
        if values.get("fcf_ttm") is not None and out["diluted_shares"] is not None
        else None
    )
    annual = {}
    for row in states:
        if (
            row.filed > state.filed
            or row.period_end is None
            or str(row.form).removesuffix("/A") not in {"10-K", "20-F", "40-F"}
        ):
            continue
        if row.period_end not in annual or row.filed > annual[row.period_end].filed:
            annual[row.period_end] = row
    years = [annual[k] for k in sorted(annual)][-10:]
    out["annual_sequence"] = [
        {
            "filed": str(r.filed),
            "period_end": str(r.period_end),
            "rev_ttm": r.values.get("rev_ttm"),
            "ni_ttm": r.values.get("ni_ttm"),
            "eps_ttm": r.values.get("eps_ttm"),
            "gross_margin": r.values.get("gross_margin"),
        }
        for r in years
    ]
    margins = [
        r.values["ni_ttm"] / r.values["rev_ttm"]
        for r in years
        if r.values.get("ni_ttm") is not None and r.values.get("rev_ttm") is not None and r.values["rev_ttm"] > 0
    ]
    out.update(
        annual_eps=[r.values.get("eps_ttm") for r in years],
        annual_gross_margins=[r.values.get("gross_margin") for r in years],
    )
    industry = (
        entity["sector"]
        if entity["sector"] in settings()["cyclical"]["pe"]
        else settings()["inputs"]["subindustry_by_ticker"].get(state.ticker)
    )
    out["subindustry"] = industry
    if len(margins) >= settings()["cyclical"]["minimum_years"]:
        out["normal_net_margin"] = median(margins)
    else:
        out["normal_net_margin"] = settings()["cyclical"]["fallback_net_margin"].get(industry)
        out["insufficient_annual_history"] = True
        out["normal_margin_reason"] = f"仅{len(margins)}个可核实年度净利率，少于7年；无已确认板块净利率参数"
    revenues = [r.values.get("rev_ttm") for r in years]
    out["normal_revenue"] = (
        sum(revenues[-3:]) / 3 if len(revenues) >= 3 and all(v is not None for v in revenues[-3:]) else None
    )
    out["rev_cagr_10y_pct"] = None
    if len(years) >= 10 and all(v is not None and v > 0 for v in (revenues[0], revenues[-1])):
        span = (years[-1].period_end - years[0].period_end).days / 365.2425
        out["rev_cagr_10y_pct"] = ((revenues[-1] / revenues[0]) ** (1 / span) - 1) * 100
    revenue = values.get("rev_ttm")
    ni = values.get("ni_ttm")
    out["ttm_net_margin"] = ni / revenue if ni is not None and revenue is not None and revenue > 0 else None
    out["rev_cagr_3y"] = None
    if state.period_end is not None and revenue is not None and revenue > 0:
        target = state.period_end.replace(year=state.period_end.year - 3, day=min(state.period_end.day, 28))
        matches = [
            r
            for r in states
            if r.filed <= state.filed
            and r.period_end
            and abs((r.period_end - target).days) <= settings()["inputs"]["annual_period_tolerance_days"]
        ]
        old = max(matches, key=lambda r: r.filed, default=None)
        if old and old.values.get("rev_ttm") is not None and old.values["rev_ttm"] > 0:
            out["rev_cagr_3y"] = ((revenue / old.values["rev_ttm"]) ** (1 / 3) - 1) * 100
            out["rev_cagr_3y_source"] = {
                "filed": str(old.filed),
                "period_end": str(old.period_end),
                "rev_ttm": old.values["rev_ttm"],
            }
    out["foreign_annual_only"] = bool(entity.get("foreign") and "interim_unaudited" not in state.health_codes)
    # ROE and ordinary equity are not substitutes for ROTE and tangible book value.
    out["rote_5y_avg"] = values.get("rote_5y_avg")
    out["tbv_per_share"] = values.get("tbv_per_share")
    return out
