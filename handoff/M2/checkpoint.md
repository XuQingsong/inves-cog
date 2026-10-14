# M2 中期检查点

基线：main 4e217a0；原始失败测试提交 633d141a，汇率失败测试 2aab4c8。此检查点对应任务书 §4.1 第④步，提交早于最终验收。

## 输出和来源

全部状态字段、field_sources、filed、accession 和健康码在 [checkpoint-data.json](checkpoint-data.json)。LITE、BE、CEG、ASML 各有 legacy/fixed 两行，明确为手写夹具，仅证明标签补齐、D3 边界、行业非阻断和 IFRS 年度合同。ASML 示例使用合成 USD，不冒充真实 EUR 转换结果。AMD 两行来自 Muse 导出的真实 SEC companyfacts，哈希登记在输出中。

AMD/WDC 分部样例均来自手写实例和本地桩 schema，通过 Arelle 离线解析。业务维度 52+50、抵销 −2、合并 100，误差 0；产品维度 999 和混合维度 777 不参与合计。利润分别为 OperatingIncomeLoss 和公司自定义 SegmentAdjustedProfit；映射未确认，segment_std 为空。

## 独立 legacy 对照

[legacy-replay.json](legacy-replay.json)：30 只 × 3 日期 = 90 组，比较 Muse 返回的全部 2,255 个字段，数值相对容差 1e−9；差异 0。按 manifest 核对 companyfacts 原始哈希和 oracle gzip 哈希；未运行、导入或复制 Muse 代码，未修改冻结输入或标准答案。

## 尚待真实验证

真实 LITE/BE/CEG/ASML 最新申报、AMD/WDC 分部原文、59 只差异和分部覆盖、连续 5 日一致预期尚未形成验收证据。M1 合并前按 Q-M2-14 使用共享接口的测试替身，不在 M2 重建 SEC/LLM 客户端或共享运行表。检查点不代表这些真实验收项已经通过。
