"""Read-only trading comparisons; no order or action-producing interface."""

from collections import defaultdict

from inves_cog.valuation_v1.calculations import LABEL, settings


def curve(x, nodes):
    if x is None or not nodes:
        return None
    if x <= nodes[0][0]:
        return nodes[0][1]
    for (a, av), (b, bv) in zip(nodes, nodes[1:]):
        if x <= b:
            return av + (bv - av) * (x - a) / (b - a)
    return nodes[-1][1]


def shadow(row, *, bear_30d=None, seen_versions=()):
    c = settings()["shadow"]
    p = row.get("p")
    delta = row.get("delta_g")
    usable = row.get("confidence") != "低"
    growth = row.get("type") == "成长"
    vt1 = usable and (
        (p is not None and p >= c["vt1_p"]) or (growth and delta is not None and delta > c["vt1_delta_g_pp"])
    )
    vt2 = usable and p is not None and p >= c["vt2_p"]
    coef = next((v for upper, v in c["v2_nodes"] if p is not None and p <= upper), 0) if p is not None else None
    bear = row.get("bear")
    if (
        p is not None
        and p < 0
        and bear is not None
        and bear_30d is not None
        and bear_30d > 0
        and (bear / bear_30d - 1) * 100 < c["bear_revision_pct"]
    ):
        coef = 0
    score = curve(delta, c["v1_growth_nodes"]) if growth else curve(p, c["v1_p_nodes"])
    return {
        "label": LABEL,
        "ticker": row.get("ticker"),
        "date": row.get("date"),
        "version": row.get("version"),
        "vt1": bool(vt1),
        "vt2": bool(vt2),
        "vt2_cap_multiplier": c["vt2_cap_multiplier"] if vt2 else 1,
        "v1_score": score,
        "v1_reason": "K01：成长类Δg曲线节点待答"
        if growth and not c["v1_growth_nodes"]
        else ("隐含增速缺失" if growth and delta is None else None),
        "v2_coef": coef,
        "v3_trim_flag": p is not None and p >= c["v3_p"] and row.get("version") not in seen_versions,
        "v3_fraction": c["v3_fraction"],
        "difference": "仅影子记录；不影响规则A实际订单",
    }


def panel(row, *, bear_30d=None, seen_versions=()):
    s = shadow(row, bear_30d=bear_30d, seen_versions=seen_versions)
    c = settings()["panel"]
    price, bear, weight = row.get("price"), row.get("bear"), row.get("weight_pct")
    down = max(0, (price - bear) / price * 100) if price is not None and price > 0 and bear is not None else None
    risk = weight * down / 100 if weight is not None and down is not None else None
    target = row.get("target_weight_pct", weight)
    suggested = target * s["v2_coef"] if target is not None and s["v2_coef"] is not None else None
    grey = row.get("confidence") == "低"
    yellow = not grey and (
        (weight is not None and suggested is not None and weight > suggested * c["yellow_shadow_ratio"])
        or (risk is not None and risk >= c["yellow_risk_pct"])
    )
    return {
        **row,
        "label": LABEL,
        "downside_pct": down,
        "valuation_at_risk_pct": risk,
        "shadow_vt1": s["vt1"],
        "shadow_vt2": s["vt2"],
        "shadow_suggested_weight_pct": suggested,
        "flag_yellow": bool(yellow),
        "greyed": grey,
        "below_bear": row.get("p") is not None and row["p"] < 0,
        "panel_reason": "未取得持仓或目标金额" if weight is None else None,
    }


def summarize(rows):
    labels = defaultdict(float)
    l2 = defaultdict(float)
    l3 = defaultdict(float)
    for row in rows:
        if row.get("p_label") is not None and row.get("weight_pct") is not None:
            labels[row["p_label"]] += row["weight_pct"]
        if row.get("valuation_at_risk_pct") is not None:
            l2[row.get("l2") or "未分类"] += row["valuation_at_risk_pct"]
            l3[row.get("l3") or "未分类"] += row["valuation_at_risk_pct"]
    return {
        "label": LABEL,
        "ticker": "__portfolio__",
        "valuation_at_risk_pct": sum(
            r["valuation_at_risk_pct"] for r in rows if r.get("valuation_at_risk_pct") is not None
        ),
        "shadow_weight_pct": sum(
            r["shadow_suggested_weight_pct"]
            for r in rows
            if not r["greyed"] and r.get("shadow_suggested_weight_pct") is not None
        ),
        "weight_by_p_label": dict(labels),
        "risk_by_l2": dict(l2),
        "risk_by_l3": dict(l3),
        "row_count": len(rows),
        "unavailable_risk_tickers": [r["ticker"] for r in rows if r.get("valuation_at_risk_pct") is None],
    }
