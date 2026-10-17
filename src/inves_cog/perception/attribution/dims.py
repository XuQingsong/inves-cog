"""Five linkage dimensions that stay separate. Rules only; no model score."""


def authenticity(sources):
    """Level-1 denial wins, then a revision, then confirmation, then an independent level-2 source."""
    if any(row["level"] == 1 and row.get("action") in {"否认", "矛盾"} for row in sources):
        return "证伪"
    if any(row["level"] == 1 and row.get("action") == "修订" for row in sources):
        return "修订"
    if any(row["level"] == 1 and row.get("action") == "确认" for row in sources):
        return "核实"
    if any(row["level"] == 2 and row.get("independent", True) for row in sources):
        return "部分核实"
    return "未核实"


def narrative_states(counts):
    if not counts:
        return []
    states = ["初现"]
    peak = counts[0]
    previous = counts[0]
    low_days = 0
    faded = False
    for count in counts[1:]:
        peak = max(peak, count)
        state, low_days, faded = _narrative_day(count, previous, peak, low_days, faded)
        states.append(state)
        previous = count
    return states


def _narrative_day(count, previous, peak, low_days, faded):
    if count >= 3 and count >= 1.5 * previous:
        return "扩散", 0, False
    if faded and peak > 0 and count >= 0.8 * peak:
        return "重新活跃", 0, False
    if peak > 0 and count <= 0.5 * peak:
        low_days += 1
    else:
        low_days = 0
    if low_days >= 2:
        return "衰减", 0, True
    if faded:
        return "衰减", low_days, True
    return "稳定", low_days, False


def trade_states(sessions):
    """First two sessions stay in risk release. A new low counts only after repair has started."""
    if not sessions:
        return []
    first_residual = sessions[0]["cumulative"]
    first_close = sessions[0]["close"]
    states = []
    repaired = False
    failed = False
    hold = 0
    for index, session in enumerate(sessions):
        if index < 2:
            states.append("风险释放")
            continue
        if failed:
            states.append("修复失效")
            continue
        state, repaired, failed, hold = _trade_day(session, first_residual, first_close, repaired, hold)
        states.append(state)
    return states


def _trade_day(session, first_residual, first_close, repaired, hold):
    if repaired and session["close"] < first_close:
        return "修复失效", repaired, True, hold
    ratio = _retrace(session["cumulative"], first_residual)
    hold = hold + 1 if ratio >= 0.5 else 0
    if hold >= 5:
        return "持续确认", True, False, hold
    if ratio >= 0.3:
        return "初步修复", True, False, hold
    return "风险释放", repaired, False, hold


def _retrace(cumulative, first_residual):
    if not first_residual:
        return 0.0
    return 1 - cumulative / first_residual


_FUNDAMENTAL_EVIDENCE = {"局部支持", "支持", "冲突"}


def sentiment_amplification(heat, fundamental):
    """Narrative heat outran fundamental evidence. The flag only describes amplification."""
    if heat is None:
        return None
    rising = _heat_rising(heat)
    if rising is None:
        return None
    if not rising:
        return False
    return fundamental not in _FUNDAMENTAL_EVIDENCE


def _heat_rising(heat):
    known = []
    today = heat.get("sources_today")
    yesterday = heat.get("sources_yesterday")
    if today is not None or yesterday is not None:
        if today is None or yesterday is None:
            known.append(None)
        else:
            known.append(today >= 3 and today >= 1.5 * yesterday)
    if heat.get("search_ratio") is not None:
        known.append(heat["search_ratio"] > 3)
    if heat.get("rank_jump") is not None:
        known.append(heat["rank_jump"] > 20)
    if not known or all(item is None for item in known):
        return None
    if any(item is True for item in known):
        return True
    if any(item is None for item in known):
        return None
    return False


_NOT_OPERATING = {"price", "social_heat", "second_hit", "consensus", "flow"}


def rumor_split(item, verifiers=()):
    """A published rumor is narrative. Its content is operating evidence only after an independent check."""
    if item is None:
        return None
    if item.get("kind") != "rumor" and item.get("source_level") != 4:
        return None
    published = bool(item.get("source_root") or item.get("info_id"))
    return {
        "narrative": published,
        "operating_evidence": published and _rumor_verified(item, verifiers),
        "authenticity": None,
        "fundamental_standing": None,
    }


def falsified_rumor(reading):
    """After a level-1 denial, rumor content leaves the operating basis. The price and spread records stay."""
    if reading is None:
        return None
    item = reading.get("item")
    sources = reading.get("sources")
    if item is None or sources is None:
        return None
    if item.get("kind") != "rumor" and item.get("source_level") != 4:
        return None
    if authenticity(sources) != "证伪":
        return None
    root = item.get("source_root") or None
    info_id = item.get("info_id") or None
    price = item.get("price_impact")
    return {
        "operating_evidence": False,
        "price_impact": price,
        "price_impact_retained": None if price is None else True,
        "propagation_retained": None if not (root or info_id) else True,
        "source_root": root,
        "info_id": info_id,
        "fundamental_standing": None,
    }


def _rumor_verified(item, verifiers):
    variable = item.get("variable")
    root = item.get("source_root")
    if not variable or not root:
        return False
    for row in verifiers:
        if row.get("source_root") in (None, root):
            continue
        if row.get("source_level") not in (1, 2):
            continue
        if row.get("kind") in _NOT_OPERATING or row.get("quantity") is None:
            continue
        if row.get("variable") != variable or row.get("contradiction") is True:
            continue
        return True
    return False


_ESTABLISHED = {"核实", "修订"}


def weakest_link(chain):
    """A later link does not fill an earlier one. The discovery price is not transmission."""
    if chain is None:
        return None
    authenticity = chain.get("authenticity")
    transmitted = chain.get("transmission") is True and chain.get("price_as_evidence") is not True
    confirmed = chain.get("market_confirmed") is True
    open_links = []
    if authenticity not in _ESTABLISHED:
        open_links.append("消息真实性")
    if not transmitted:
        open_links.append("盈利传导")
    if not confirmed:
        open_links.append("市场确认")
    return {
        "authenticity": authenticity,
        "market_confirmed": confirmed,
        "transmission": transmitted,
        "open_links": open_links,
        "fundamental_standing": None,
        "operating_impact_proven": False,
    }


_AUDIT = (
    ("原始出处", "source_root"),
    ("完整表述", "body"),
    ("发布时间", "published_at"),
    ("首次取得时间", "first_seen_at"),
    ("是否旧闻重发", "reprint"),
    ("传播关系", "relays"),
    ("独立来源数", "source_roots"),
    ("反方材料", "counter_items"),
)


def source_check(item):
    """Eight falsification fields. A filled checklist does not make the claim true."""
    if item is None:
        return None
    return {
        "checks": [_audit_row(item, label, key) for label, key in _AUDIT],
        "authenticity": None,
        "operating_evidence": False,
        "fundamental_standing": None,
    }


def _audit_row(item, label, key):
    if key == "source_roots":
        roots = item.get("source_roots")
        if not isinstance(roots, (list, tuple)):
            return {"item": label, "status": "未知", "value": None, "is_evidence": False}
        unique = {root for root in roots if root}
        return {"item": label, "status": "有数据", "value": len(unique), "is_evidence": False}
    value = item.get(key)
    present = value is not None and value != ""
    return {"item": label, "status": "有数据" if present else "未知", "is_evidence": False}
