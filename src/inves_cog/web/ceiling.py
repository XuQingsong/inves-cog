"""Presentation of stored reverse-valuation results; never recompute a decision."""

MISSING_LABELS = {
    "rule_a_tier": "风险层级",
    "FY1_consensus": "下一财年一致预期",
    "roic": "投入资本回报率",
    "fy2_eps": "后一年一致预期",
    "gross_margin_trend_pp": "毛利率趋势",
    "rev_growth": "营收增速",
    "fcf_ttm": "自由现金流",
    "net_debt": "净负债",
    "diluted_shares": "稀释后股数",
    "price": "当日价格",
    "ni_ttm": "净利润",
    "rev_ttm": "营收",
    "op_margin_ttm": "经营利润率",
    "listing_units": "上市股本单位",
    "visible_financial_state": "当时已公开财报",
    "positive_enterprise_value": "有效企业价值",
    "band_calibration_not_visible": "当时可用的档位校准",
}


def ceiling_text(row, *, full=False):
    if not isinstance(row, dict):
        return "隐含天花板暂缺"
    method = row.get("method")
    reason = {"cyclical": "周期股", "financial": "金融股", "loss": "亏损或隐含倍数超过40"}.get(method)
    m, r = row.get("m"), row.get("r")
    bits = []
    if reason:
        bits.append("隐含天花板档位不适用（" + reason + "）")
        if r is not None:
            bits.append(f"折现率 {r:.0%}")
        profit = row.get("implied_terminal_profit")
        if profit is not None:
            bits.append(f"现价隐含十年后终局年利润约 {profit / 1e8:.2f} 亿美元")
    elif m is not None and r is not None:
        bits.append(f"现价隐含利润约涨到现在的 {m:.1f} 倍（折现率 {r:.0%}），{row.get('band', '档位暂缺')}")
        if row.get("band") == "严重透支":
            bits.append("长期回报大概率偏低（隐含天花板处于严重透支档）")
        if full:
            lo, hi = row.get("m_r_minus_1"), row.get("m_r_plus_1")
            if lo is not None and hi is not None:
                bits.append(f"折现率低/高1个百分点：{lo:.1f}/{hi:.1f}倍")
            if row.get("fcf_m") is not None:
                bits.append(f"现金口径 {row['fcf_m']:.1f}倍")
            bits.append("利润质量" + str(row.get("quality") or "暂缺"))
    else:
        bits.append("隐含天花板暂缺")
    if full:
        proof = row.get("evidence", {})
        for key, label in (
            ("rev_growth", "营收增速"),
            ("rev_accel_pp", "增速加速度"),
            ("gross_margin", "毛利率"),
            ("roic", "投入资本回报率"),
            ("gross_margin_trend_pp", "毛利率变化"),
        ):
            value = proof.get(key)
            if value is not None:
                bits.append(f"{label} {value:.1f}%")
        if proof.get("fy2_coverage") is not None:
            bits.append(f"后一年预期对终局利润覆盖 {proof['fy2_coverage']:.0%}")
        if proof.get("fcf_net_profit_ratio") is not None:
            bits.append(f"自由现金流/净利润 {proof['fcf_net_profit_ratio']:.2f}")
        if row.get("missing"):
            bits.append("缺失：" + "、".join(MISSING_LABELS.get(k, "相关披露") for k in row["missing"]))
    return "；".join(bits)
