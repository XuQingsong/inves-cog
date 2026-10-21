"""Independent factor values and counterfactuals; never orders or portfolio simulation."""

from datetime import date

from inves_cog.shadow.settings import settings
from inves_cog.shadow.substitution import substitute
from inves_cog.trading.scoring.curves import CURVES, finite, interp


def weighted(items):
    valid = [(score, weight) for score, weight in items if finite(score)]
    total = sum(weight for _, weight in valid)
    return sum(score * weight for score, weight in valid) / total if total else None


def f01(inputs):
    c = settings()["f01"]
    ps, rev = inputs.get("ps"), inputs.get("rev_growth")
    psg = ps / rev if finite(ps) and finite(rev) and rev > 0 else None
    pe, growth = inputs.get("pe"), inputs.get("eps_growth")
    previous_eps, previous_margin = inputs.get("prev_eps_ttm"), inputs.get("prev_net_margin_pct")
    eps_ok = all(finite(x) for x in (pe, growth, previous_eps, previous_margin)) and (
        pe > 0
        and growth > 0
        and previous_eps > 0
        and previous_margin >= c["previous_margin_min"]
        and (inputs.get("eps_ttm") is None or inputs["eps_ttm"] > 0)
    )
    peg = pe / min(growth, c["eps_growth_cap"]) if eps_ok else None
    scores = [
        interp(psg, c["psg_curve"]),
        interp(peg, c["eps_pe_curve"]),
        interp(inputs.get("fcf_yield"), CURVES["fcf_yield"]),
    ]
    return {
        "psg": psg,
        "psg_score": scores[0],
        "eps_adj_pe_score": scores[1],
        "fcf_yield_score": scores[2],
        "f01_score": weighted(zip(scores, c["weights"], strict=True)),
    }


def f02(inputs):
    c = settings()["f02"]
    positive = inputs.get("ni_ttm_positive")
    profit = (
        (c["positive_profit_score"] if positive else c["negative_profit_score"]) if type(positive) is bool else None
    )
    scores = [
        interp(inputs.get("gm_change_pp"), c["gm_curve"]),
        interp(inputs.get("fcf_margin_change_pp"), c["fcf_curve"]),
        profit,
    ]
    return {
        "f02_score": weighted(zip(scores, c["weights"], strict=True)),
        "gross_margin_score": scores[0],
        "fcf_margin_score": scores[1],
        "profit_score": profit,
    }


def s10(inputs):
    c = settings()["s10"]
    output = {
        "eligible": None,
        "secondary_price": None,
        "shadow_sell_fraction": None,
        "maximum_sessions": c["maximum_sessions"],
        "systemic_event_tag": inputs.get("systemic_event_tag"),
        "conditions": {},
        "null_reason": None,
    }
    rule = inputs.get("rule_id")
    if rule not in {"M-51", "M-55"} or inputs.get("already_reviewed") is True:
        return {**output, "eligible": False, "null_reason": "非本阶段规则A价格型卖出或本持仓冲击已复核"}
    if rule == "M-55" and inputs.get("panic_gate") is True:
        return {**output, "eligible": False, "null_reason": "恐慌闸门已覆盖M55，未形成该笔实际卖出"}
    resid, sigma = inputs.get("resid_5d"), inputs.get("sigma_5d")
    beta = resid >= -c["residual_sigma_multiplier"] * sigma if finite(resid) and finite(sigma) and sigma >= 0 else None
    earnings, s4 = inputs.get("earnings_reaction_5d"), inputs.get("s4_triggered")
    m50, s1 = inputs.get("m50_triggered"), inputs.get("new_s1")
    no_company = not earnings and not s4 if type(earnings) is bool and type(s4) is bool else None
    fundamentals = not m50 and not s1 if type(m50) is bool and type(s1) is bool else None
    conditions = {
        "systemic_shock": inputs.get("shock_flag"),
        "beta_driven": beta,
        "not_company_event": no_company,
        "fundamentals_intact": fundamentals,
    }
    loss = inputs.get("loss_equity_pct")
    hard = m50 is True or s4 is True or (finite(loss) and loss >= c["hard_loss_equity_pct"])
    eligible = False if hard or any(value is False for value in conditions.values()) else None
    complete = all(type(value) is bool for value in conditions.values()) and finite(loss)
    complete = complete and bool(inputs.get("holding_id")) and bool(inputs.get("shock_id"))
    if eligible is not False and complete:
        eligible = True
    output.update(eligible=eligible, conditions=conditions, null_reason="S10资格输入缺失" if eligible is None else None)
    price, tier = inputs.get("price"), inputs.get("tier")
    if eligible and finite(price) and tier in c["secondary_drop"]:
        output.update(secondary_price=price * (1 - c["secondary_drop"][tier]), shadow_sell_fraction=0.5)
    elif eligible:
        output.update(eligible=None, null_reason="S10二级线价格或层级缺失")
    return output


def _replacement(factor_id, snapshot, inputs, day):
    c = settings()
    books = snapshot.get("books") or {}
    if factor_id == "F-01":
        cfg = c["f01"]
        if not (
            finite(books.get("growth"))
            and books["growth"] >= cfg["growth_min"]
            and finite(inputs.get("rev_growth"))
            and inputs["rev_growth"] >= cfg["revenue_min"]
        ):
            return None, None, None, "F01不适用或成长/营收输入缺失"
        value = f01(inputs)["f01_score"]
        raw = books.get("valuation")
        adjusted = max(raw, min(cfg["effective_cap"], value)) if finite(raw) and finite(value) else None
        return value, adjusted, "valuation", None if adjusted is not None else "F01估值子项或原估值账缺失"
    if factor_id == "F-02":
        cfg = c["f02"]
        growth, accel, qy, margin = (
            books.get("growth"),
            inputs.get("rev_accel_pp"),
            inputs.get("rev_q_yoy"),
            inputs.get("gm_change_pp"),
        )
        applicable = (
            finite(growth) and growth >= cfg["growth_entry"] and finite(margin) and margin >= cfg["gross_margin_min"]
        )
        applicable = applicable and ((finite(accel) and accel >= 0) or (finite(qy) and qy >= cfg["revenue_q_min"]))
        if not applicable:
            return None, None, None, "F02不适用或适用条件输入缺失"
        value = f02(inputs)["f02_score"]
        raw = books.get("quality")
        effective = max(raw, min(cfg["effective_cap"], value)) if finite(raw) and finite(value) else None
        return value, effective, "quality", None if effective is not None else "F02子项或原质量账缺失"
    if factor_id in ("F-03", "F-04", "F-05"):
        return _new_book(factor_id, snapshot, inputs, day)
    return None, None, None, "非账本替换因子"


def _new_book(factor_id, snapshot, inputs, day):
    c, books = settings(), snapshot.get("books") or {}
    if factor_id == "F-03":
        if date.fromisoformat(str(day)) < date.fromisoformat(c["f03"]["mature_on"]):
            return None, None, None, "快照不足"
        value = interp(inputs.get("eps_revision_30d_pct"), c["f03"]["curve"])
        book, weight = "growth", c["f03"]["weight"]
    else:
        segments = inputs.get("segments")
        if not isinstance(segments, list) or len(segments) < 2:
            return None, None, None, "单分部或分部输入缺失"
        eligible = [
            row
            for row in segments
            if len(row.get("revenue_4q") or []) == 4 and all(finite(v) for v in row["revenue_4q"])
        ]
        if len(eligible) != len(segments):
            return None, None, None, "核心分部最近四季收入不完整"
        core = max(eligible, key=lambda row: sum(row["revenue_4q"]))
        if factor_id == "F-04":
            value = interp(core.get("margin_change_pp"), c["f04"]["curve"])
            book, weight = "quality", c["f04"]["weight"]
        else:
            value = interp(core.get("revenue_yoy_pct"), CURVES["rev_growth"])
            book, weight = "growth", c["f05"]["weight"]
    raw = books.get(book)
    adjusted = (raw * (100 - weight) + value * weight) / 100 if finite(raw) and finite(value) else None
    return value, adjusted, book, None if adjusted is not None else factor_id + "新增项或原账本缺失"


def evaluate_factors(snapshot, inputs, *, day):
    rows = []
    c = settings()
    for number in range(1, 9):
        factor_id = f"F-{number:02}"
        row = {
            "date": str(day),
            "ticker": snapshot["ticker"],
            "factor_id": factor_id,
            "version": c["factor_version"],
            "value": None,
            "substituted_value": None,
            "would_pass": None,
            "rule_a_entry_pass": snapshot.get("entry_pass"),
            "gap_detail": {"null_reason": None},
        }
        if number <= 5:
            value, adjusted, book, reason = _replacement(factor_id, snapshot, inputs, day)
            row.update(value=value, substituted_value=adjusted)
            if book is not None:
                result = substitute(snapshot, factor_id=factor_id, book=book, value=adjusted)
                row.update(would_pass=result["would_pass"], gap_detail=result["gap_detail"])
                row["gap_detail"]["n_code"] = result["n_code"]
            if reason:
                row["gap_detail"]["null_reason"] = reason
            if number == 3:
                row["gap_detail"]["raw_revision_pct"] = inputs.get("eps_revision_30d_pct")
        elif number == 6:
            vol = inputs.get("vol60") if finite(inputs.get("vol60")) else inputs.get("vol20")
            cap, tier = inputs.get("cap"), snapshot.get("tier")
            if finite(cap) and finite(vol) and vol > 0 and tier in c["f06"]["target_volatility"]:
                cfg = c["f06"]
                multiplier = max(
                    cfg["minimum_multiplier"], min(cfg["maximum_multiplier"], cfg["target_volatility"][tier] / vol)
                )
                row["value"] = {"cap_eff": cap * multiplier, "multiplier": multiplier}
                amount = inputs.get("plan_buy_amount")
                row["substituted_value"] = amount * multiplier if finite(amount) else None
                row["gap_detail"].update(
                    plan_buy_amount=amount, null_reason=None if finite(amount) else "无当日基础买入金额"
                )
            else:
                row["gap_detail"]["null_reason"] = "F06仓位上限或波动率缺失"
        elif number == 7:
            valuation = inputs.get("valuation_shadow")
            if isinstance(valuation, dict) and any(valuation.get(key) is not None for key in ("vt1", "vt2")):
                row["value"] = {key: valuation.get(key) for key in ("vt1", "vt2", "version", "observed_at")}
                row["gap_detail"]["source"] = "valuation_v1.shadow_rules；未重新计算"
            else:
                row["gap_detail"]["null_reason"] = "M5当时可见V-T1/V-T2缺失"
        else:
            result = s10(inputs.get("s10") or {})
            row["value"] = result["eligible"] if inputs.get("s10") else None
            row["gap_detail"].update(result)
            if row["value"] is None and not row["gap_detail"]["null_reason"]:
                row["gap_detail"]["null_reason"] = "无当日规则A价格型卖出记录"
        rows.append(row)
    return rows
