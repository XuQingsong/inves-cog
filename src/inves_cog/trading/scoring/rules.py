"""Frozen v18 rule semantics; references are to Muse aacea04, not imported code."""

from pathlib import Path

import yaml

ENTRY = {"defense": (70, 45, 50, 50), "normal": (60, 55, 45, 55), "attack": (50, 70, 30, 50)}
BOOK_KEYS = ("quality", "growth", "valuation", "timing")
EXCLUDED = {"趋势破位", "现金流为负且营收下滑", "营收与EPS同时明显下滑"}


def load_rule_a(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parents[4] / "config/params/rule_a_v18.yaml"
    params = yaml.safe_load(path.read_text())
    if set(params) != {"rule_set", "a_plus_enabled", "tiers", "max_positions"}:
        raise ValueError("Rule A does not accept tracker or additional rule groups")
    expected = {"defensive": (0.12, 0.5, 0.3, 4), "normal": (0.12, 0.4, 0.3, 6), "aggressive": (0.08, 0.3, 0.4, 6)}
    if params["rule_set"] != "A" or params["a_plus_enabled"] or params["max_positions"] != 12:
        raise ValueError("I02/I03: rule A is frozen")
    if set(params["tiers"]) != set(expected):
        raise ValueError("I03: tier constants differ")
    for name, values in expected.items():
        row = params["tiers"][name]
        if set(row) != {"cap", "first_lot", "budget", "budget_buffer", "max_positions"}:
            raise ValueError("I03: extra tier rule groups are not permitted")
        actual = tuple(row.get(key) for key in ("cap", "first_lot", "budget", "max_positions"))
        if actual != values or row.get("budget_buffer") != 1.25:
            raise ValueError("I03: tier constants differ")
    return params


def red_lines(fields, tech, derived):
    result = []

    def less(value, bound):
        return value is not None and value < bound

    if all(less(tech.get(k), bound) for k, bound in (("price_vs_ma200", 0), ("ma50_vs_ma200", 0), ("mom6", -10))):
        result.append("趋势破位")
    # Q-M3-11 compatibility: paper_trade_2026.py L193–203 uses or 0 in these predicates only.
    if less(fields.get("fcf_ttm"), 0) and (fields.get("rev_growth") or 0) < 0:
        result.append("现金流为负且营收下滑")
    if less(fields.get("rev_growth"), -5) and less(fields.get("eps_growth"), -20):
        result.append("营收与EPS同时明显下滑")
    if less(fields.get("current_ratio"), 0.8):
        result.append("流动性偏紧")
    pe = derived.get("pe")
    if pe and pe > 80 and ((fields.get("rev_growth") or 0) < 15 or (fields.get("rev_accel_pp") or 0) < -10):
        result.append("高估值与增长不匹配")
    if tech.get("rsi") is not None and tech.get("dev50") is not None and tech["rsi"] > 80 and tech["dev50"] > 15:
        result.append("短线过热")
    return result


def assign_tier(books, fields, volatility):
    quality, growth = books["quality"], books["growth"]
    if quality is None or growth is None or volatility is None:
        return None
    ni, fcf, rg = (fields.get(k) for k in ("ni_ttm", "fcf_ttm", "rev_growth"))
    loss = ni is not None and fcf is not None and ni < 0 and fcf < 0
    # Rule A compatibility exception Q-M3-11: source v18 L67 treats valuation 0 as 100.
    if volatility > 55 or loss or (rg is not None and rg > 35 and (books["valuation"] or 100) < 45):
        return "attack"
    if (
        volatility < 30
        and fcf is not None
        and fcf > 0
        and (fields.get("fcf_margin") or 0) > 5
        and quality >= 70
        and growth >= 45
        and (rg is None or rg >= 0)
    ):
        return "defense"
    return "normal"


def certainty(books, fields):
    def at_least(key, bound):
        return fields.get(key) is not None and fields[key] >= bound

    def below(key, bound):
        return fields.get(key) is not None and fields[key] < bound

    growth = books["growth"] or 0
    points = 2 if growth >= 85 else int(growth >= 72)
    points += 2 if at_least("rev_growth", 30) else int(at_least("rev_growth", 18))
    accel = fields.get("rev_accel_pp")
    points += 1 if at_least("rev_accel_pp", 3) else (-1 if accel is not None and accel <= -8 else 0)
    points += 1 if at_least("eps_growth", 20) else (-1 if below("eps_growth", 0) else 0)
    return points, "high" if points >= 4 else "medium" if points >= 2 else "low"


HOLD = {
    "rev_q_yoy": ([(20, 15), (10, 12), (0, 8), (-5, 4)], 0, 8, False),
    "rev_accel_pp": ([(0, 15), (-10, 10), (-20, 5)], 0, 0, False),
    "gross_margin_change_pp": ([(0, 15), (-3, 10), (-6, 5)], 0, 8, False),
    "fcf_conversion": ([(1, 20), (0.5, 15), (0, 8)], 0, 8, False),
    "net_debt_fcf": ([(0, 15), (3, 12), (5, 8)], 0, 8, True),
    "current_ratio": ([(1.5, 10), (1, 7), (0.8, 4)], 0, 5, False),
}


def holding(fields):
    total = 0
    for key, (cuts, floor, missing, inverse) in HOLD.items():
        value = fields.get(key)
        if value is None:
            total += missing
            continue
        total += next(
            (points for threshold, points in cuts if (value <= threshold if inverse else value >= threshold)), floor
        )
    qy, gm, conv = (fields.get(k) for k in ("rev_q_yoy", "gross_margin_change_pp", "fcf_conversion"))
    bad = total < 40 or (qy is not None and qy < 0 and gm is not None and gm < 0 and (conv is None or conv < 0.3))
    fcf, cash = fields.get("fcf_ttm"), fields.get("cash")
    runway = fcf is None or fcf >= 0 or (cash is not None and cash >= abs(fcf))
    return {"hold_score": total, "hold_ok": total >= 55, "fund_bad": bool(bad), "runway_ok": bool(runway)}


def entry_rules(books, fields, tier, lines):
    value, adjusted = books["valuation"], None
    if tier == "attack" and (books["growth"] or 0) >= 70 and value is not None and fields.get("rev_growth") is not None:
        adjusted = min(65.0, value + max(0.0, min(20.0, (fields["rev_growth"] - 15) / 3)))
    effective = {**books, "valuation": adjusted if adjusted is not None else value}
    gate = tier in ENTRY and all(
        effective[k] is not None and effective[k] >= bound for k, bound in zip(BOOK_KEYS, ENTRY[tier], strict=True)
    )
    fcf = fields.get("fcf_ttm")
    guard = True
    if tier == "attack" and fcf is not None and fcf < 0:
        guard = (fields.get("rev_growth") or 0) >= 30 and (fields.get("cash") or 0) >= 1.5 * abs(fcf)
    return {
        "m31_adjusted_valuation": adjusted,
        "m32_ok": bool(guard),
        "gate_pass": bool(gate),
        "entry_pass": bool(gate and guard and not EXCLUDED.intersection(lines)),
    }
