"""Channel implied-magnitude rules. Incompatible is not an emotion label."""

import math

from inves_cog.perception.attribution.rules import m8_rules

ORDER = "订单/积压"
COUNTERPARTY = "融资/对手方"
MULTIPLE = "估值倍数"
SUPPLY = "供给/价格"
INCOME = "直接收入"
_OBSERVED = {"观察到", "有支持", "已确立"}
_CHANNELS = {
    "供给": (SUPPLY,),
    "需求": (INCOME,),
    "竞争": (INCOME,),
    "客户融资": (ORDER, COUNTERPARTY),
    "估值倍数": (MULTIPLE,),
}


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


def ntm_move(members):
    """NTM repeats the TTM member set. One missing forward PE leaves the NTM total blank."""
    if members is None:
        return None
    counted = [member for member in members if _member_move(member) is not None]
    blank = {
        "delta_e_ntm": None,
        "verdict": None,
        "fundamental_standing": None,
        "operating_evidence": False,
    }
    if not counted:
        return blank
    total = 0.0
    for member in counted:
        pe = member.get("pe_ntm")
        if not _usable_pe(pe):
            return blank
        total += member["market_cap_prev"] * member["resid"] / pe
    return {**blank, "delta_e_ntm": total}


def _usable_pe(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value != 0


def exposure_tasks(mechanism, exposures):
    """An observed edge with no dollar exposure is a fill task. It is not a verdict."""
    names = _CHANNELS.get(mechanism)
    if names is None:
        raise ValueError("渠道只接受供给、需求、竞争、客户融资、估值倍数")
    if mechanism == "估值倍数":
        return []
    tasks = []
    for name in names:
        for row in exposures:
            if row.get("channel") != name or row.get("status") not in _OBSERVED:
                continue
            if row.get("exposure_usd") is not None:
                continue
            tasks.append(_exposure_task(name, row))
    return tasks


def channel_rows(mechanism, citations, exposures, *, years_to_realize=None):
    """Mechanism picks the channels. The best cited level is the smallest number."""
    names = _CHANNELS.get(mechanism)
    if names is None:
        raise ValueError("渠道只接受供给、需求、竞争、客户融资、估值倍数")
    if mechanism == "估值倍数":
        return [{"channel": MULTIPLE}]
    level = _best_level(citations)
    return [_channel_row(name, level, exposures, years_to_realize) for name in names]


def channel_lines(result):
    """Each channel gets its own verdict. The word 情绪 is not one of them."""
    lines = []
    for row in result["channels"]:
        delta = row["delta_e_evt"]
        lines.append(
            {
                "channel": row["channel"],
                "delta_e_evt": delta,
                "verdict": _one_channel_verdict(result["delta_e_mkt"], delta),
            }
        )
    return lines


def implied_magnitude(payload, rules=None):
    rules = rules or m8_rules()
    income_cap = {int(level): value for level, value in rules["income_change_cap"].items()}
    counterparty_cap = {int(level): value for level, value in rules["counterparty_default_cap"].items()}
    member_basis = None
    if "members" in payload:
        if "delta_mktcap" in payload or "pe" in payload:
            raise ValueError("市场幅度不能混用逐成员和统一PE输入")
        member_basis = _member_basis(payload["members"])
        delta_market = market_move(payload["members"])["delta_e_mkt"]
    else:
        delta_market = payload["delta_mktcap"] / payload["pe"]
    channels = []
    for row in payload["channels"]:
        channels.append({**row, "delta_e_evt": _event_limit(row, income_cap, counterparty_cap)})
    present = [row["delta_e_evt"] for row in channels if row["delta_e_evt"] is not None]
    missing = [row for row in channels if row["channel"] != MULTIPLE and row.get("exposure_usd") is None]
    known = [row for row in channels if row.get("exposure_usd") is not None]
    partial = bool(missing and known)
    total = sum(present)
    if delta_market is None or _uncomputable(channels):
        ratio, verdict = None, "无法检验"
    else:
        ratio, verdict = _verdict(delta_market, total, partial, bool(present) or not missing)
    result = {
        "delta_e_mkt": delta_market,
        "channels": [{"channel": row["channel"], "delta_e_evt": row["delta_e_evt"]} for row in channels],
        "sum_delta_e_evt": total,
        "R": ratio,
        "verdict": verdict,
        "partial_missing": partial,
    }
    if member_basis is not None:
        result["market_basis"] = member_basis
    return result


def _member_basis(members):
    """Optional per-member input audit; financial aggregation stays in market_move."""
    if not isinstance(members, list) or any(not isinstance(row, dict) for row in members):
        raise ValueError("市场成员输入必须为对象列表")
    eligible, excluded = [], []
    for index, row in enumerate(members):
        for field in ("eps_ttm", "pe_ttm", "market_cap_prev", "resid"):
            value = row.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            ):
                raise ValueError("市场幅度输入必须为有限数值或未知")
        name = row.get("ticker", index)
        reason = None
        if row.get("eps_ttm") is None:
            reason = "缺EPS"
        elif row["eps_ttm"] <= 0:
            reason = "EPS非正"
        elif not row.get("pe_ttm"):
            reason = "缺有效TTM PE"
        elif row.get("market_cap_prev") is None:
            reason = "缺前一日市值"
        elif row.get("resid") is None:
            reason = "缺剩余收益"
        if reason is None:
            eligible.append(name)
        else:
            excluded.append({"ticker": name, "reason": reason})
    return {
        "method": "sum_member_previous_cap_times_residual_over_ttm_pe",
        "scope": "explicit_members",
        "member_count": len(members),
        "eligible": eligible,
        "excluded": excluded,
        "unit": "USD/year-equivalent",
        "actual_profit_loss_or_causation_proven": False,
    }


def _event_limit(row, income_cap, counterparty_cap):
    if row["channel"] == MULTIPLE:
        return 0.0
    exposure = row.get("exposure_usd")
    level = row.get("source_level")
    margin = row.get("incremental_margin")
    if exposure is None or level not in (1, 2, 3, 4) or margin is None:
        return None
    caps = counterparty_cap if row["channel"] == COUNTERPARTY else income_cap
    cap = caps[int(level)]
    if row["channel"] == ORDER:
        years = row.get("years_to_realize")
        if not years:
            return None
        return exposure * cap / years * margin
    return exposure * cap * margin


def _exposure_task(channel, row):
    return {
        "channel": channel,
        "relation_id": row.get("relation_id"),
        "ticker": row.get("ticker"),
        "from_entity": row.get("from_entity"),
        "to_entity": row.get("to_entity"),
        "reason": "缺美元暴露",
    }


def _channel_row(name, level, exposures, years):
    dollars, margin = _observed_exposure(name, exposures)
    row = {
        "channel": name,
        "source_level": level,
        "exposure_usd": dollars,
        "incremental_margin": margin,
    }
    if name == ORDER:
        row["years_to_realize"] = years
    return row


def _best_level(citations):
    levels = [row.get("source_level") for row in citations if row.get("source_level") in (1, 2, 3, 4)]
    if not levels:
        return None
    return min(levels)


def _observed_exposure(name, exposures):
    rows = [row for row in exposures if row.get("channel") == name and row.get("status") in _OBSERVED]
    if not rows or any(row.get("exposure_usd") is None for row in rows):
        return None, None
    dollars = [row["exposure_usd"] for row in rows]
    margins = [_margin(row) for row in rows]
    total = sum(dollars)
    if any(margin is None for margin in margins):
        return total, None
    if total == 0:
        return 0.0, 0.0
    weighted = sum(amount * margin for amount, margin in zip(dollars, margins, strict=True))
    return total, weighted / total


def _margin(row):
    if row.get("basis") == "分部收入":
        return row.get("segment_margin")
    return row.get("op_margin_ttm")


def _uncomputable(channels):
    return any(
        row["channel"] != MULTIPLE and row.get("exposure_usd") is not None and row["delta_e_evt"] is None
        for row in channels
    )


def _one_channel_verdict(delta_market, delta):
    if delta_market is None or delta is None:
        return "无法检验"
    _ratio, verdict = _verdict(delta_market, delta, False, True)
    return verdict


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
