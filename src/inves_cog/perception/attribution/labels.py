"""Divergence labels exist only on the deadline or once the case is verified."""


def consensus_band(change, downgrades, upgrades, coverage):
    """Missing EPS consensus or coverage stays unknown. It is not 未下修."""
    breadth = coverage is not None and coverage > 0 and downgrades is not None
    if breadth and downgrades >= 0.3 * coverage:
        return "显著下修"
    if change is not None and change <= -0.03:
        return "显著下修"
    if change is None or not breadth or upgrades is None:
        return None
    if change > -0.02 and downgrades <= upgrades:
        return "未下修"
    return "其他"


def divergence_label(moment, price, consensus, fundamental, linkage, *, guidance_cut=False):
    if moment not in {"截止日", "已验证"}:
        return None
    if price is None or fundamental is None or linkage is None:
        return None
    if guidance_cut:
        revision = "显著下修"
    elif consensus is None:
        return None
    else:
        revision = consensus
    table = {
        ("大跌", "未下修", "未变", "已衰减"): "情绪性折价",
        ("大跌", "未下修", "未变", "已证伪"): "情绪性折价",
        ("大跌", "未下修", "未变", "估值倍数类"): "情绪性折价",
        ("大跌", "显著下修", "支持不利", "已验证·有影响"): "合理重定价",
        ("小跌或未跌", "显著下修", "支持不利", "已验证·有影响"): "滞后风险",
        ("大涨", "未上修", "未变", "估值倍数类"): "情绪性溢价",
        ("大涨", "显著上修", "支持有利", "已验证正向"): "基本面驱动上涨",
    }
    return table.get((price, revision, fundamental, linkage))
