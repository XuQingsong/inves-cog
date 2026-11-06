# ruff: noqa: E501
"""Render corrected R1 evidence and retain the observed coverage limitations."""

import json
from pathlib import Path
from statistics import median

E = Path("handoff/A031/evidence")


def num(value):
    return "缺失" if value is None else f"{value:.2f}"


def amend(text):
    summary = json.loads((E / "r1-corrected/individual-summary.json").read_text())
    portfolios = json.loads((E / "r1-corrected/portfolios-summary.json").read_text())
    audit = json.loads((E / "r1-corrected/data-audit.json").read_text())
    source = json.loads((E / "r1-source-audit.json").read_text())["resolution"]
    progress = json.loads((E / "r1-corrected/progress.json").read_text())
    lines = [
        "## R1 历史成员日期修正后的风险检验",
        "",
        f"按UD-A-58核对121份标普官方公告，形成{source['official_events']}条去重成员事件；删除{source['affected_tickers']}个代码的{source['excluded_weekly_rows']}条不在成员期间的周观察。ABMD、TWTR、CDAY等不再从入选前进入样本。加入日包含、退出日不包含；双股类分别处理，Fox旧发行人删除与新发行人更名分开。每条事件都有官方来源。",
        "",
        "首次公告仅给TBA时不推测日期；以后正式公告覆盖。方法论/咨询/重复实施通知已逐项说明。无变更事件的代码保留指定面板已有周成员状态；这不是独立复原整份历史500只名册。",
        "",
        "**数据限制：已退出公司并未全部拥有可用价格/财报。历史成员池包含已退出公司，但仍有覆盖选择偏差，不能声称“全体历史标普无幸存者偏差”已得到完全验证。** 下表列出实际覆盖和缺失名单所在文件，相关统计只适用于可观测样本。",
        "",
        "|年份|有效周观察|有效公司|官方退出公司（非银行保险）|有有效m的退出公司|退出公司覆盖率%|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for year, row in sorted(audit["yearly"].items()):
        cov = audit["removed_coverage_by_year"][year]
        lines.append(
            f"|{year}|{row['valid_weekly_rows']}|{len(row['valid_names'])}|{cov['official_removed']}|{cov['with_valid_m']}|{num(cov['pct'])}|"
        )
    lines += [
        "",
        "银行、保险与健康保险公司按明确代码清单排除，支付网络和资产管理公司未一并排除。完整清单、各年缺失退出公司及官方期间在 `evidence/r1-corrected/data-audit.json`。周观察相互重叠，不是独立公司事件样本。",
        "",
        "|组别|后续周数|完整观察数|超额收益中位数%|低于−30%占比|低于−50%占比|回撤中位数%|回撤90分位%|",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in ("top_fifth", "rest"):
        for weeks in (52, 104):
            row = summary[f"{group}_{weeks}"]["all"]
            lines.append(
                f"|{group}|{weeks}|{row['n']}|{num(row['median_excess_pct'])}|{num(row['below_minus30_pct'])}|{num(row['below_minus50_pct'])}|{num(row['maxdd_median_pct'])}|{num(row['maxdd_p90_pct'])}|"
            )
    lines += [
        "",
        "超额收益为个股收益减SPY收益（百分点）；回撤列为正的损失幅度。只保留SPY已走完52/104周的窗口。个股提前终止报价时冻结最后报价为现金代理，不能当作取得了真实退市兑付。按年分列在 `individual-summary.json`，全部逐观察数值在 `individual.csv.gz`。",
        "",
        "A=可观测成员全等权；B=去掉最透支五分之一；C=该五分之一权重减半后整体归一化。缺失m的成员仍全权重纳入A/B/C，不把它们默认为透支或不存在。每月按首个交易日收盘再平衡，排名使用严格更早的周数据；当天已生效的官方成员变更也参与成员过滤。",
        "",
        "|2018年1月起|累计收益%|年化%|最大回撤%|年化波动%|年化收益/回撤|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant in ("A", "B", "C"):
        row = portfolios[f"2018-01-01-{variant}"]["metrics"]
        lines.append(
            f"|{variant}|{num(row['cumulative_pct'])}|{num(row['annualized_pct'])}|{num(row['maxdd_pct'])}|{num(row['annualized_vol_pct'])}|{num(row['return_over_maxdd'])}|"
        )
    lines += [
        "",
        "|相对A，12个月起点|最大回撤较小的起点数|年化收益差中位数pp|最大回撤差中位数pp|",
        "|---|---:|---:|---:|",
    ]
    for variant in ("B", "C"):
        pairs = [
            (portfolios[f"2018-{m:02d}-01-{variant}"]["metrics"], portfolios[f"2018-{m:02d}-01-A"]["metrics"])
            for m in range(1, 13)
        ]
        lines.append(
            f"|{variant}|{sum(a['maxdd_pct'] > b['maxdd_pct'] for a, b in pairs)}/12|{num(median(a['annualized_pct'] - b['annualized_pct'] for a, b in pairs))}|{num(median(a['maxdd_pct'] - b['maxdd_pct'] for a, b in pairs))}|"
        )
    first = portfolios["2018-01-01-A"]["rebalances"][0]["date"]
    lines += [
        "",
        f"初始周面板从2018-01-05开始，因此1月起点第一次建仓实际为{first}，此前保留现金，未伪造2017年末排名。其余月在首个交易日执行。样本末日2026-10-30。价格使用库存复权收盘，未单独计现金股息、费用或退市实际补偿。",
        "",
        f"36个组合的全部指标、逐年收益和每次再平衡成员数在 `portfolios-summary.json`，完整曲线在 `portfolios.csv.gz`。修正后实际{progress['elapsed']:.2f}秒，{progress['individual_rows']}个个股窗口观察。以上只报告数据，不作规则取舍。",
        "",
    ]
    start = text.index("## R1 数据质量")
    end = text.index("## TSM", start)
    text = text[:start] + "\n".join(lines) + "\n" + text[end:]
    text = text.replace(
        "R2 与 R3 数值计算已完成；R1 原输入发现成员日期错误，现有数值仅为暂定，正在按用户 UD-A-58 用标普官方公告修正。整单尚未完成验收。",
        "三项研究数值已完成，原输入的成员日期错误已按UD-A-58修正。历史退出公司覆盖仍不完整，R1全体无偏要求不能宣称完全满足；数据覆盖、原始数值和限制供需求方验收。",
    )
    text = text.replace(
        "网络恢复不等于已修复完整季度财务、汇率和ADR单位口径；保留真实缺口和逐日层级记录，不伪造当时可见数据。",
        "网络恢复不等于已修复完整季度财务、汇率和ADR单位口径。另外，TSM与ARM被规则A既有FOREIGN集合明确排除，TSM全期可交易日为0；这条资格限制不会因EPS补齐而自动消失。完整2018–2026逐日层级与财报期间在 `tsm-tier-history.csv`，未伪造当时可见数据。",
    )
    text = text.replace(
        "尚待：R1全体成员期间修正与正式重算、TSM历史层级/季度财务缺口的完整披露、自验清单、最终准确head CI与PR。A032按最新通知在A031验收关单后开始。",
        "交付边界：成员日期已修正、已退出公司纳入，但仍有历史数据覆盖缺口；不能以技术测试通过替代“完整无偏”验证。最终准确head CI与逐项自验见PR及ops/answers/A-031.md。A032在A031验收关单后开始。",
    )
    return text
