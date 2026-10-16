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
