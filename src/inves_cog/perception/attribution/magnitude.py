"""Channel implied-magnitude rules. Incompatible is not an emotion label."""

from inves_cog.perception.attribution.rules import m8_rules

ORDER = "订单/积压"
COUNTERPARTY = "融资/对手方"
MULTIPLE = "估值倍数"


def market_move(members):
    """Prior market cap times residual return over TTM PE. Non-positive EPS stays out."""
    total = 0.0
    counted = 0
    for member in members:
        piece = _member_move(member)
        if piece is None:
            continue
        total += piece
        counted += 1
    if counted == 0:
        return {"delta_e_mkt": None, "verdict": "无法检验"}
    return {"delta_e_mkt": total, "verdict": None}


def _member_move(member):
    eps = member.get("eps_ttm")
    pe = member.get("pe_ttm")
    cap = member.get("market_cap_prev")
    resid = member.get("resid")
    if eps is None or eps <= 0 or not pe or cap is None or resid is None:
        return None
    return cap * resid / pe


def implied_magnitude(payload, rules=None):
    rules = rules or m8_rules()
    income_cap = {int(level): value for level, value in rules["income_change_cap"].items()}
    counterparty_cap = {int(level): value for level, value in rules["counterparty_default_cap"].items()}
    delta_market = payload["delta_mktcap"] / payload["pe"]
    channels = []
    for row in payload["channels"]:
        channels.append({**row, "delta_e_evt": _event_limit(row, income_cap, counterparty_cap)})
    present = [row["delta_e_evt"] for row in channels if row["delta_e_evt"] is not None]
    missing = [row for row in channels if row["channel"] != MULTIPLE and row.get("exposure_usd") is None]
    known = [row for row in channels if row.get("exposure_usd") is not None]
    partial = bool(missing and known)
    total = sum(present)
    ratio, verdict = _verdict(delta_market, total, partial, bool(present) or not missing)
    return {
        "delta_e_mkt": delta_market,
        "channels": [{"channel": row["channel"], "delta_e_evt": row["delta_e_evt"]} for row in channels],
        "sum_delta_e_evt": total,
        "R": ratio,
        "verdict": verdict,
        "partial_missing": partial,
    }


def _event_limit(row, income_cap, counterparty_cap):
    if row["channel"] == MULTIPLE:
        return 0.0
    exposure = row.get("exposure_usd")
    if exposure is None:
        return None
    caps = counterparty_cap if row["channel"] == COUNTERPARTY else income_cap
    cap = caps[int(row["source_level"])]
    margin = row.get("incremental_margin") or 0.0
    years = row.get("years_to_realize") or 1
    if row["channel"] == ORDER:
        return exposure * cap / years * margin
    return exposure * cap * margin


def _verdict(delta_market, total, partial, has_number):
    if not has_number:
        return None, "无法检验"
    if total == 0:
        return ("inf", "不相容") if not partial else (None, "无法检验")
    ratio = abs(delta_market) / total
    if partial and ratio > 1.5:
        return None, "无法检验"
    if ratio <= 1.5:
        verdict = "相容"
    elif ratio <= 5:
        verdict = "部分相容"
    else:
        verdict = "不相容"
    return round(ratio, 4), verdict
