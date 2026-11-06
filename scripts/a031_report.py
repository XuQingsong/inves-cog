# ruff: noqa: E501
# Chinese report prose and table rows are intentionally stored as complete literals.
"""Assemble factual A031 research tables from completed evidence, without rule recommendations."""

import csv
import json
from pathlib import Path
from statistics import median

BASE = Path("handoff/A031")
E = BASE / "evidence"


def load(path):
    return json.loads((E / path).read_text())


def number(value):
    return "缺失" if value is None else f"{value:.2f}"


def main():
    rolling = load("r2/rolling.json")
    report = [
        "# A-031 策略研究",
        "",
        "本报告只给数据与观察，不提出或上线规则修改。全部在 Mac 本地 `inves_cog_bt` 只读运行，无模型调用。",
        "",
        "## 验收状态",
        "",
        "R2 与 R3 数值计算已完成；R1 原输入发现成员日期错误，现有数值仅为暂定，正在按用户 UD-A-58 用标普官方公告修正。整单尚未完成验收。",
        "",
        "## R2 破位卖出",
        "",
        "同一59只固定池，2018-01-02至2026-10-30；该池存在幸存者偏差，不能把R2外推为全部历史标普结论。新开关只在回测生效、默认关闭。",
        "",
        "v2仅在基本面恶化或fear≥3时保留M-55。v2b在仅市场风险触发时卖1/3，基本面恶化仍用原比例。缺失fear不当作≥3；其余保留F2的基本面判定。",
        "",
        "|版本|累计收益%|最大回撤%|M-55卖出次数|",
        "|---|---:|---:|---:|",
    ]
    sales = []
    for name in ("base", "F2", "v2", "v2b"):
        r = load(f"r2/{name}.json")
        m = r["metrics"]
        exits = [s for s in r["sales"] if "M-55" in s["rule_ids"]]
        report.append(f"|{name}|{number(m['return_pct'])}|{number(m['max_drawdown_pct'])}|{len(exits)}|")
        for sale in r["sales"]:
            if sale["requested_case"]:
                sales.append(
                    dict(
                        version=name,
                        ticker=sale["ticker"],
                        signal_date=sale["signal_date"],
                        trade_date=sale["trade_date"],
                        fill_price=sale["fill_price"],
                        qty=sale["qty"],
                        trigger=";".join(sale["rule_ids"]),
                        reason=sale["reason_zh"],
                        forward20=sale["forward_pct"]["20"],
                        forward60=sale["forward_pct"]["60"],
                    )
                )
    with (E / "r2/requested-sales.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sales[0]))
        w.writeheader()
        w.writerows(sales)
    report += [
        "",
        "28个季度起点（2018Q1至2024Q4）相对base；回撤为负数，回撤差为正表示损失较小。",
        "",
        "|版本|起点数|收益胜出占比%|收益差中位数pp|收益差Q25/Q75|回撤差中位数pp|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("F2", "v2", "v2b"):
        r = rolling[name]
        report.append(
            f"|{name}|{r['n_starts']}|{r['beats_baseline_pct']}|{number(r['ret_diff_median'])}|{number(r['ret_diff_q25'])}/{number(r['ret_diff_q75'])}|{number(r['dd_diff_median'])}|"
        )
    report += [
        "",
        "M-55后续股价表现以卖出当日复权收盘到之后第20/60个交易日计算，不把成交开盘价混作比较起点。上涨占比只表示卖出后股价上涨，不直接等于卖出错误。",
        "",
        "|版本|窗口|完整样本|后续收益中位数%|后续上涨占比%|",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("base", "F2", "v2", "v2b"):
        rows = [r for r in load(f"r2/{name}.json")["sales"] if "M-55" in r["rule_ids"]]
        for n in (20, 60):
            vals = [r["forward_pct"][str(n)] for r in rows if r["forward_pct"][str(n)] is not None]
            report.append(
                f"|{name}|{n}|{len(vals)}|{number(median(vals) if vals else None)}|{number(100 * sum(v > 0 for v in vals) / len(vals) if vals else None)}|"
            )
    report += [
        "",
        "完整起点统计、fear覆盖、信号对照与指定三只股票的全部卖出分别在 `evidence/r2/rolling.json`、`signals.json`、`requested-sales.csv`；逐笔M-55及触发规则在四版本JSON。",
        "",
        "## R3 漏选诊断",
        "",
        "窗口2024-01至2026-10；额外前十定义为此期间基线从未持有或形成买入意向的池内股票，按窗口内首末可用复权收盘涨幅排序。指定AMD/SNDK/MU/AMAT/TSM始终列入。卡点可同时出现，天数不相加为总天数。",
        "",
        "|股票|可诊断日数|评分门槛卡点天数|首次通过全部评分门槛|首次真实买入意向|",
        "|---|---:|---|---|---|",
    ]
    r3 = load("r3/baseline.json")
    for ticker, row in sorted(r3["gate_summary"].items()):

        def first(value):
            return f"{value['date']} / {number(value['price'])}" if value else "未出现"

        counts = "；".join(f"{k}:{v}" for k, v in row["gate_days"].items())
        report.append(
            f"|{ticker}|{row['days']}|{counts}|{first(row['first_score_pass'])}|{first(row['first_buy_intent'])}|"
        )
    report += [
        "",
        "逐日行同时保留实际执行器的名额/额度/冷却/回撤跳过理由、观察确认状态、持有评分和是否已持有；首次评分通过与真实买入意向分别列示，避免把评分通过误称可以成交。",
        "",
        "单门放宽使用当日全池该评分的60分位与原门槛的较低者。仅变更一道数值门槛，不补造缺失评分、不取消红线/M32/历史价格/可交易要求；估值使用规则A原M31调整值。",
        "",
        "|放宽门槛|额外买入数|20日中位数%/胜率%（n）|60日中位数%/胜率%（n）|120日中位数%/胜率%（n）|",
        "|---|---:|---:|---:|---:|",
    ]
    for book in ("quality", "growth", "valuation", "timing"):
        row = load(f"r3/{book}.json")["extra_summary"]
        cells = [
            f"{number(row[str(n)]['median_pct'])}/{number(row[str(n)]['win_pct'])} ({row[str(n)]['n']})"
            for n in (20, 60, 120)
        ]
        report.append(f"|{book}|{row['buys']}|" + "|".join(cells) + "|")
    report += [
        "",
        "quality的p60未低于实际层级门槛时不会强行放宽，因此新增数可以为0。完整额外买入股票/日期/20、60、120日表现及基线对照均在 `evidence/r3/<门槛>.json`。层级或数据缺失不能通过降低分数补造；红线、名额、观察确认等非评分卡点在逐日诊断中单列，没有伪称已做数值分位放宽。",
        "",
        "## R1 数据质量与待修正项",
        "",
        "指定面板把ABMD从2018-01-05纳入，官方入选日2018-05-31；SIVB也被提前纳入。原生成器对已退出公司只限制退出日，未限制加入日。证据在 `evidence/r1-source-audit.json`。用户已授权UD-A-58，正在用官方公告重建事件；全体成员期间核对前，不将现有R1结果作为正式风险证据。",
        "",
        "原始试算保留在 `evidence/r1/`：292477个个股/窗口观察和36个组合，完整数值已压缩保存。其成员日期错误尚未消除，不据此下正式结论。缺失退市实际兑付时只使用最后可用复权价格冻结为现金代理；未单独计现金股息。这些限制修正成员日期后仍会明确披露。",
        "",
        "## TSM",
        "",
        "既有含联系邮箱SEC User-Agent重试后，两份索引HTTP200；CompanyFacts也200但没有可直接使用的季度EPS事实行。已获取2026-10-15官方第三季盈利附件：普通股EPS为NT$29.43，对比2025Q3的17.44、2026Q2的27.25；不当成美元ADR EPS或直接填入生产。来源、原表行见 `evidence/tsm-quarter-filing.json`。",
        "",
        "本地最新部分TSM财务状态的期间回落到2024-12-31，健康码为annual_basis/stale_fundamentals；R3中705日无层级。网络恢复不等于已修复完整季度财务、汇率和ADR单位口径；保留真实缺口和逐日层级记录，不伪造当时可见数据。",
        "",
        "## 执行、验证与边界",
        "",
        "默认关闭的481笔交易hash为 `f56ffe611b7c029a8e55a59936fdb298b9ce902377c8a74ff39428d0e4a7e767`，提速前后均与A029基线完全一致。先失败测试/夹具提交后实现；专项与v18已在状态中分别记录，最终准确head CI待完整交付。",
        "",
        "R2首次批次达到限期停止；优化仅将历史价格排序移到循环外，按不规则日期前缀及隔离修改测试，并用完整基线核验后，剩余28起点评估303.54秒完成，最多4worker，112个检查点保留。R3单进程159.58秒；R1原试算单进程37.95秒。没有生产回测、模型、线上规则变更或自动合并。",
        "",
        "尚待：R1全体成员期间修正与正式重算、TSM历史层级/季度财务缺口的完整披露、自验清单、最终准确head CI与PR。A032按最新通知在A031验收关单后开始。",
    ]
    from a031_report_r1 import amend

    BASE.joinpath("report.md").write_text(amend("\n".join(report)) + "\n")


if __name__ == "__main__":
    main()
