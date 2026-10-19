# A012-Q01：恢复TSM正确估值需要上游最小输入例外

当前PR只在M5拒绝发布过时2024年度估值，尚未恢复TSM可估。其余核查、代码和五日/交易不变证据已提交PR #36。

已独立读本机原件：SEC accession `0001628280-26-025362`，`tsm-20251231.htm`，2025-01-01至2025-12-31，无维度的合并上下文：

| 标签 | 原币披露值 | 单位 |
|---|---:|---|
| ifrs-full:DilutedEarningsLossPerShare | 65.47 | TWD/普通股 |
| ifrs-full:CashFlowsFromUsedInOperatingActivities | 2,274,975.6 | 百万TWD |
| ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities | 1,272,410.5 | 百万TWD |
| ifrs-full:AdjustedWeightedAverageShares | 25,930.6 | 百万普通股 |

[原件](https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm)。不能把方便阅读的USD列直接替代既有FRED合同，也不能从净利润/EPS反推股本。ADS关系1:5复用既有已核实证据。

建议另开独立PR，仅为TSM新增估值专用年度状态与逐字段来源（原始期间/币种/稀释股本/现金流、FRED转换与已知时间）；M5读该可选对象。M2旧EPS、shares、FCF等规则A字段不变，不改表结构、参数、订单或其他标的。先补失败build用例，再实现并重出五日/11494行打分和完整计划不变证明。

这超出目前只读M1/M2的A线边界。依据ops/README.md §5的“会改变跨模块的表结构或接口”以及“要改不属于本线的代码包”必须停规则，尚未写这部分M2实现。已向用户提出一次选择：允许上述独立最小修复；或当前保持明确不估、由协调方另排上游修复。以用户答复为准，未将缺口登记为已解决。
