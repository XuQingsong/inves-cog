"""Price-independent valuation formulas from specification 8.4 (no trading dependency)."""

import hashlib
import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path
from statistics import median

from inves_cog.params import load_params

LABEL = "估值参考 v1，不参与仓位"
SCENARIOS = ("bear", "neutral", "bull")


@lru_cache(maxsize=1)
def settings():
    return load_params(Path(__file__).resolve().parents[3] / "config/params/p-2026.10").values["m5"]


def clamp(x, low, high):
    return max(low, min(x, high))


def require(data, key, *, positive=False):
    v = data.get(key)
    if v is None:
        raise ValueError("缺少输入：" + key)
    v = float(v)
    if not math.isfinite(v) or (positive and v <= 0):
        raise ValueError("输入无效：" + key)
    return v


def growth_value(e, growth, cap, p90=None):
    c = settings()["growth"]
    eps3 = e * math.prod(1 + decay * growth / 100 for decay in c["decay"])
    pe = clamp(c["exit_pe_intercept"] + c["exit_pe_slope"] * growth, c["exit_pe_floor"], cap)
    if p90 is not None:
        if p90 <= 0:
            raise ValueError("输入无效：pe_p90")
        pe = min(pe, p90)
    return {"growth": growth, "eps3": eps3, "exit_pe": pe, "value": eps3 * pe / (1 + c["discount_rate"]) ** 3}


def calculate(kind, data):
    """Calculate an economic range without accepting or inspecting a current price."""
    cfg = settings()
    d = {k: v for k, v in data.items() if k != "price"}
    version = hashlib.sha256(
        json.dumps([kind, d, cfg], sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()[:20]
    out = {
        "type": kind,
        "method_version": cfg["method_version"],
        "params_version": cfg["params_version"],
        "version": version,
        "label": LABEL,
        "status": "ok",
        "reason": None,
        "confidence": "高",
        "downgrade_reasons": [],
        "inputs": d,
        "details": {},
        "pending_review": False,
    }
    reasons = out["downgrade_reasons"]
    if d.get("insufficient_pe_history"):
        reasons.append("倍数历史不足5年")
    if d.get("type_disagreement"):
        reasons.append("最近两期类型不一致")
    if d.get("foreign_annual_only"):
        reasons.append("外国申报人只有年度数据")
    try:
        if kind == "困境":
            raise ValueError("不估值：亏损且无增长")
        if kind == "稳定":
            c = cfg["stable"]
            ttm = require(d, "eps_ttm")
            ntm = d.get("eps_ntm")
            if ntm is None:
                reasons.append("一致预期缺失")
                e = ttm
            else:
                e = c["eps_weights"][0] * ttm + c["eps_weights"][1] * require(d, "eps_ntm")
            fcf = d.get("fcf_per_share")
            if fcf is None:
                fcf = require(d, "fcf_ttm") / require(d, "diluted_shares", positive=True)
            pe = [
                e * c["pe_bear"] * require(d, "pe_p25", positive=True),
                e * require(d, "pe_p50", positive=True),
                e * c["pe_bull"] * require(d, "pe_p75", positive=True),
            ]
            cash = [fcf / rate for rate in c["fcf_yields"]]
            denom = min(pe[1], cash[1])
            divergence = abs(pe[1] - cash[1]) / denom * 100 if denom > 0 else None
            downgrade = divergence is None or divergence > c["divergence_pct"]
            if downgrade:
                reasons.append("两法分歧超过40%" if divergence is not None else "两法中性值非正，无法比较")
            out.update(
                E=e,
                pe_method=pe,
                fcf_method=cash,
                method_divergence_pct=divergence,
                confidence_downgrade_divergence=downgrade,
            )
            values = [c["pe_weight"] * a + (1 - c["pe_weight"]) * b for a, b in zip(pe, cash, strict=False)]
        elif kind == "成长":
            c = cfg["growth"]
            ntm = d.get("eps_ntm")
            if ntm is None or d.get("consensus_next_year_eps_growth") is None:
                reasons.append("一致预期缺失")
            e = require(d, "eps_ntm" if ntm is not None else "eps_ttm", positive=True)
            growth_key = (
                "consensus_next_year_eps_growth"
                if d.get("consensus_next_year_eps_growth") is not None
                else "eps_growth"
            )
            g = min(require(d, growth_key), require(d, "rev_cagr_3y"), c["cap_pct"])
            detail = [
                growth_value(e, min(f * g, c["bull_cap_pct"]) if i == 2 else f * g, cap, d.get("pe_p90"))
                for i, (f, cap) in enumerate(zip(c["scenario_factors"], c["exit_pe_caps"], strict=False))
            ]
            out.update(E=e, g=g, details=dict(zip(SCENARIOS, detail, strict=False)))
            values = [r["value"] for r in detail]
        elif kind == "周期":
            c = cfg["cyclical"]
            margin = require(d, "normal_net_margin")
            revenue = require(d, "normal_revenue", positive=True)
            cagr = d.get("rev_cagr_10y_pct")
            if cagr is not None and cagr > c["revenue_cagr_threshold_pct"]:
                revenue *= 1 + cagr / 100
            e = margin * revenue / require(d, "diluted_shares", positive=True)
            industry = d.get("subindustry")
            if industry not in c["pe"]:
                raise ValueError("缺少周期子行业PE参数：" + str(industry))
            values = [e * f * pe for f, pe in zip(c["scenario_factors"], c["pe"][industry], strict=False)]
            out.update(
                normal_eps=e,
                normal_net_margin=margin,
                normal_revenue=revenue,
                cycle_position_pp=(d["ttm_net_margin"] - margin) * 100 if d.get("ttm_net_margin") is not None else None,
            )
            if d.get("insufficient_annual_history"):
                reasons.append("年度利润率不足7年，使用明确板块参数")
        elif kind == "未盈利成长":
            c = cfg["unprofitable"]
            growth = require(d, "rev_growth")
            revenue = d.get("rev_ntm_consensus")
            if revenue is None:
                reasons.append("一致预期缺失")
                revenue = require(d, "rev_ttm", positive=True) * (1 + min(growth, c["revenue_growth_cap_pct"]) / 100)
            mults = next((r[1:] for r in c["ev_revenue"] if growth >= r[0]), None)
            if mults is None:
                raise ValueError("不估值：亏损且无增长")
            gm = clamp(require(d, "gross_margin") / c["gm_base_pct"], *c["gm_multiplier_bounds"])
            ev = [revenue * m * gm for m in mults]
            shares = require(d, "diluted_shares", positive=True)
            debt = require(d, "net_debt")
            values = [(v - debt) / (shares * (c["bear_dilution"] if i == 0 else 1)) for i, v in enumerate(ev)]
            fcf = require(d, "fcf_ttm")
            runway = require(d, "cash") / abs(fcf) if fcf != 0 else None
            out["runway_reason"] = "FCF为0，跑道比值无法计算" if fcf == 0 else None
            haircut = runway is not None and runway < c["runway_years"]
            if haircut:
                values[0] *= c["runway_haircut"]
                reasons.append("现金跑道不足1.5年")
            out.update(gm_multiplier=gm, ev=ev, runway_years=runway, runway_haircut=haircut, confidence_max="中")
        elif kind == "金融":
            c = cfg["financial"]
            rote = require(d, "rote_5y_avg")
            tbv = require(d, "tbv_per_share", positive=True)
            values = [
                tbv * clamp((rote + adj - c["perpetual_growth_pct"]) / (r - c["perpetual_growth_pct"]), *c["pb_bounds"])
                for adj, r in zip(c["rote_adjustments_pp"], c["discount_pct"], strict=False)
            ]
        else:
            raise ValueError("未知估值类型：" + str(kind))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("估值计算出现非有限值")
        out["method_anomaly"] = values != sorted(values)
        if out["method_anomaly"]:
            out.update(pending_review=True, reason="方法异常：三档已升序重排")
        out.update(zip(SCENARIOS, sorted(values), strict=False))
    except (ValueError, TypeError, OverflowError) as exc:
        out.update(status="unvalued", reason=str(exc), **dict.fromkeys(SCENARIOS))
    from inves_cog.valuation_v1.requirements import missing_inputs

    out["blocking_inputs"] = missing_inputs(kind, d) if out["status"] != "ok" else []
    if out["blocking_inputs"]:
        out["reason"] += "; 全部阻塞输入：" + ", ".join(r["field"] for r in out["blocking_inputs"])
    return confidence(out, kind, d)


def confidence(out, kind, inputs):
    reasons = out["downgrade_reasons"]
    out["confidence"] = ("高", "中", "低")[min(len(reasons), 2)]
    if kind == "未盈利成长" and out["confidence"] == "高":
        out["confidence"] = "中"
    if out.get("runway_haircut") or inputs.get("foreign_annual_only"):
        out["confidence"] = "低"
    if out["status"] != "ok":
        out["confidence"] = "低"
    return out


def mark_price(result, price):
    out = dict(result)
    out.update(
        price=price,
        p=None,
        p_label=None,
        implied_growth=None,
        delta_g=None,
        delta_g_label=None,
        implied_exceeds_cap=False,
        implied_reason=None,
    )
    bands = settings()["position"]
    p_low, p_mid_low, p_mid_high, p_high = bands["p_label_limits"]
    g_low, g_mid, g_high = bands["delta_label_limits_pp"]
    if out["bear"] is not None and price is not None and math.isfinite(price) and price > 0:
        spread = out["bull"] - out["bear"]
        if spread != 0:
            p = (price - out["bear"]) / spread
            out["p"] = p
            out["p_label"] = (
                "低于悲观"
                if p < p_low
                else "偏低"
                if p <= p_mid_low
                else "中性"
                if p <= p_mid_high
                else "偏高"
                if p <= p_high
                else "高于乐观"
            )
        else:
            out["position_reason"] = "三档区间为0，无法计算p"
        if out["type"] == "成长" and out.get("E") is not None:
            c = settings()["growth"]
            lo, hi = c["implied_bounds"]
            p90 = out["inputs"].get("pe_p90")

            def value(g):
                return growth_value(out["E"], g, c["exit_pe_caps"][1], p90)["value"]

            if not value(lo) <= price <= value(hi):
                out["implied_reason"] = "无法反解：价格不在[-50,200]增速对应的价值区间"
            else:
                for _ in range(c["implied_iterations"]):
                    mid = (lo + hi) / 2
                    if value(mid) < price:
                        lo = mid
                    else:
                        hi = mid
                g = (lo + hi) / 2
                delta = g - out["g"]
                out.update(
                    implied_growth=g,
                    delta_g=delta,
                    implied_exceeds_cap=g > c["cap_pct"],
                    delta_g_label="现价隐含增速低于一致预期"
                    if delta <= g_low
                    else "与一致预期相当"
                    if delta <= g_mid
                    else "现价隐含增速高于一致预期"
                    if delta <= g_high
                    else "现价隐含增速远高于一致预期",
                )
    else:
        out["position_reason"] = "价格缺失或无有效估值"
    return out


def evaluate(kind, data):
    return mark_price(calculate(kind, data), data.get("price"))


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    x = (len(values) - 1) * q
    low = math.floor(x)
    high = math.ceil(x)
    return values[low] + (values[high] - values[low]) * (x - low)


def pe_percentiles(rows, as_of, *, peer_p50=()):
    c = settings()["pe"]
    begin = date(as_of.year - c["lookback_years"], as_of.month, min(as_of.day, 28))
    valid = [
        r
        for r in rows
        if begin <= r["date"] <= as_of
        and r.get("eps_ttm") is not None
        and r["eps_ttm"] > 0
        and r.get("close") is not None
        and r["close"] > 0
    ]
    values = sorted(r["close"] / r["eps_ttm"] for r in valid)
    count = len(values)
    trim = math.floor(count * c["trim_fraction"])
    sample = values[trim : count - trim] if trim else values
    span = (max(r["date"] for r in valid) - min(r["date"] for r in valid)).days / 365.2425 if valid else 0
    insufficient = span < c["minimum_years"]
    peers = [v for v in peer_p50 if v is not None and v > 0]
    fallback = median(peers) if peers else None
    result = {f"pe_p{int(q * 100)}": fallback if insufficient else percentile(sample, q) for q in c["quantiles"]}
    result.update(
        insufficient_pe_history=insufficient,
        eligible_count=count,
        trim_each=trim,
        coverage_years=span,
        own_p50=percentile(sample, 0.5),
        pe_basis="L2成员P50中位数" if insufficient else "本股十年PIT截尾PE",
    )
    if insufficient and fallback is None:
        result["pe_reason"] = "倍数历史不足5年，且无可用L2成员P50"
    return result
